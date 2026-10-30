"""Reconcile the table placement with the models.

Phase 10 preparation, and the fix for a real defect: a database built purely
from the Alembic history was **not usable by the app**.

The history's older migrations created the monitoring, academic and social
tables *unqualified* (`op.create_table('event', ...)`), so on a fresh install
they landed in the search path's first schema (`core`) while the models
declare them in `telemetry`, `academic` and `social`. The app queries
`telemetry.health_metric` by name, so on a fresh install those queries found
nothing - the deployment only worked because existing databases had been
built by `create_all`, which creates the schema-qualified tables.

This migration makes the two agree, without losing anything:

- a table the models declare in a schema, which exists only as an unqualified
  copy, is **moved** into that schema (`ALTER TABLE ... SET SCHEMA`), keeping
  its rows;
- a table that already exists in the right schema is left alone, and a
  leftover copy is dropped **only when it is empty** (a leftover with rows is
  kept and reported - merging two copies is a judgement call, not something a
  migration should do silently);
- a table the models declare and the history never created is created from
  the model metadata;
- the columns the models gained since are added to the tables the history
  built, and the enum columns are aligned with the types the models declare.

Two tables can share a name in different schemas - the application has
`core.security_event` and the monitoring bundle has
`telemetry.security_event` - so nothing here matches a table by name alone:
a candidate must carry the columns that are distinctive to *this* model. The
moves are recorded in a small log table, so the downgrade can undo exactly
those moves instead of guessing.

On a database that was built by `create_all` (every existing deployment)
this migration does nothing: there is nothing unqualified to move, and the
tables are already where the models want them.

Revision: 021
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021_reconcile_schema_placement"
down_revision: Union[str, None] = "020_monitoring_ro_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Where this migration moved a table from and to, so the downgrade can undo
#: exactly those moves - no guessing, and no confusion between two tables
#: that share a name in different schemas.
MOVE_LOG_SCHEMA = "telemetry"
MOVE_LOG_TABLE = "schema_move_log"
MOVE_LOG = f"{MOVE_LOG_SCHEMA}.{MOVE_LOG_TABLE}"

#: The tables the history never creates - migration 021 creates them, so its
#: downgrade has to drop them again.
CREATED_BY_021 = (
    "academic.reinforcement_pattern",
    "core.broadcast",
    "core.broadcast_delivery",
    "core.force_update_rule",
    "core.security_feed",
    "core.user_control_action",
    "telemetry.dependency_vulnerability",
    "telemetry.feedback_analysis",
    "telemetry.feedback_sentiment_snapshot",
    "telemetry.health_metric",
    "telemetry.revenue_snapshot",
    "telemetry.security_header_check",
    "telemetry.security_log",
    "telemetry.slow_endpoint",
    "telemetry.subscription",
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _model_tables():
    """Every table the models declare, with a schema, in dependency order."""
    from sqlmodel import SQLModel

    import models  # noqa: F401  - populates the metadata
    import features.oppfeed.models  # noqa: F401

    return [t for t in SQLModel.metadata.sorted_tables if t.schema]


def _schemas_with(bind, table_name: str) -> list[str]:
    """The schemas that hold a table with this name."""
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :name AND table_type = 'BASE TABLE'"
        ),
        {"name": table_name},
    ).all()
    return [row[0] for row in rows]


def _row_count(bind, schema: str, table: str) -> int:
    return int(
        bind.execute(
            sa.text(f'SELECT count(*) FROM "{schema}"."{table}"')
        ).scalar()
        or 0
    )


def _column_names(bind, schema: str, table: str) -> set[str]:
    rows = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    ).all()
    return {row[0] for row in rows}


def _column_type(bind, schema: str, table: str, column: str) -> str | None:
    """The Postgres type of a column, e.g. `security_event_kind`."""
    row = bind.execute(
        sa.text(
            "SELECT t.typname FROM information_schema.columns c "
            "JOIN pg_type t ON t.oid = c.udt_name::regtype::oid "
            "WHERE c.table_schema = :schema AND c.table_name = :table "
            "AND c.column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    ).first()
    return row[0] if row else None


def _enum_type_names(bind) -> set[str]:
    rows = bind.execute(
        sa.text("SELECT typname FROM pg_type WHERE typtype = 'e'")
    ).all()
    return {row[0] for row in rows}


def _best_match(bind, model_table, candidates: list[str], all_model_tables) -> str | None:
    """Which candidate is *this* model's table?

    Two different tables can share a name in two schemas - the application
    has `core.security_event` and the monitoring bundle has
    `telemetry.security_event`. Matching by name alone confuses them (and
    makes them swap schemas), so a candidate must carry the columns that are
    distinctive to this model: the ones no other same-named model has. The
    monitoring `security_event` has `kind` and `blocked`; the application's
    has `actor_id` and `category`. Only the right copy has them.
    """
    same_named = [t for t in all_model_tables if t.name == model_table.name]
    others: set[str] = set()
    for other in same_named:
        if other is not model_table:
            others |= {c.name for c in other.columns}
    wanted = {c.name for c in model_table.columns}
    distinctive = wanted - others
    best: str | None = None
    best_score = 0
    for candidate in candidates:
        have = _column_names(bind, candidate, model_table.name)
        if distinctive and not distinctive <= have:
            continue
        score = len(wanted & have)
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score else None


def _ensure_enum_type(bind, enum_type) -> None:
    """Create the enum type the model names, if the database lacks it."""
    name = enum_type.name
    if not name:
        return
    row = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"), {"name": name}
    ).first()
    if row is not None:
        return
    labels = ", ".join(f"'{label}'" for label in enum_type.enums)
    op.execute(f'CREATE TYPE "{name}" AS ENUM ({labels})')


def _align_enum_columns(bind, table, schema: str) -> list[str]:
    """Make the enum columns use the type the model declares.

    Two directions, because the history and the models disagree in both:

    - the history created a **native** enum where the model declares a
      VARCHAR-backed one (`native_enum=False`). The app then sends a string
      and Postgres refuses it: "column status is of type attendancestatus
      but expression is of type character varying". The column is widened
      to the model's form, keeping its values;
    - the history named an enum type differently from the model
      (`security_event_kind` vs the auto-named type). One type, one name -
      otherwise the same column holds two different types in two databases,
      and the reconciler cannot compare them.
    """
    aligned: list[str] = []
    for column in table.columns:
        enum_type = column.type
        if not isinstance(enum_type, sa.Enum):
            continue
        current = _column_type(bind, schema, table.name, column.name)
        if enum_type.native_enum:
            name = enum_type.name
            if not name:
                continue
            _ensure_enum_type(bind, enum_type)
            if current and current != name:
                op.execute(
                    f'ALTER TABLE "{schema}"."{table.name}" '
                    f'ALTER COLUMN "{column.name}" TYPE "{name}" '
                    f'USING "{column.name}"::text::"{name}"'
                )
                aligned.append(f"{table.name}.{column.name}")
        else:
            # The model wants a plain string column. If the database has a
            # native enum there, widen it.
            if current and current in _enum_type_names(bind):
                target = enum_type.compile(dialect=bind.dialect)
                op.execute(
                    f'ALTER TABLE "{schema}"."{table.name}" '
                    f'ALTER COLUMN "{column.name}" TYPE {target} '
                    f'USING "{column.name}"::text'
                )
                aligned.append(f"{table.name}.{column.name}")
    return aligned


def _add_missing_columns(bind, table, schema: str) -> list[str]:
    """Give the table the columns the models declare.

    The history's tables are older than the models: a column added to a
    model without a migration is missing from the table the history built.
    Adding a column is the safe direction - the rows that exist keep their
    values, and the new column starts empty (or at its default).
    """
    from sqlalchemy.schema import CreateColumn

    existing = _column_names(bind, schema, table.name)
    added: list[str] = []
    for column in table.columns:
        if column.name in existing:
            continue
        ddl = str(CreateColumn(column).compile(bind))
        op.execute(f'ALTER TABLE "{schema}"."{table.name}" ADD COLUMN {ddl}')
        added.append(column.name)
    return added


def _index_columns(bind, schema: str, table: str) -> list[tuple[str, ...]]:
    """The column sets of the table's indexes."""
    rows = bind.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": schema, "table": table},
    ).all()
    sets: list[tuple[str, ...]] = []
    for (name,) in rows:
        columns = bind.execute(
            sa.text(
                "SELECT a.attname FROM pg_index i "
                "JOIN pg_attribute a ON a.attrelid = i.indrelid "
                "AND a.attnum = ANY(i.indkey) "
                "WHERE i.indexrelid = to_regclass(:qualified) "
                "ORDER BY array_position(i.indkey, a.attnum)"
            ),
            {"qualified": f'"{schema}"."{name}"'},
        ).all()
        sets.append(tuple(row[0] for row in columns))
    return sets


def _ensure_indexes(bind, table, schema: str) -> list[str]:
    """Make sure the table has an index for every index the model declares.

    The indexes are matched by their **columns**, not by their names: the
    history created `ix_event_ts` where the model declares
    `ix_telemetry_event_ts`, and renaming them here would break the
    downgrade of every migration that drops an index by its old name. A
    renamed index is a naming debt for the baseline squash (Phase 10); a
    missing index is a real gap, and that is what this closes.
    """
    created: list[str] = []
    existing_sets = _index_columns(bind, schema, table.name)
    present = _column_names(bind, schema, table.name)
    for index in table.indexes:
        columns = tuple(column.name for column in index.columns)
        if not columns or not all(c in present for c in columns):
            # The index covers a column this table does not have (yet).
            continue
        if columns in existing_sets:
            continue
        unique = "UNIQUE " if index.unique else ""
        op.execute(
            f'CREATE {unique}INDEX "{index.name}" ON "{schema}"."{table.name}" '
            f'({", ".join(chr(34) + c + chr(34) for c in columns)})'
        )
        created.append(index.name)
    return created


def _model_schema_for(model_tables, name: str) -> str | None:
    """The schema the models declare for a table name, when it is unambiguous."""
    schemas = {t.schema for t in model_tables if t.name == name}
    if len(schemas) == 1:
        return schemas.pop()
    return None


def _repoint_foreign_keys(bind, model_tables, table, schema: str) -> list[str]:
    """Re-point the table's foreign keys at where their references now live.

    `ALTER TABLE ... SET SCHEMA` moves the table but leaves its foreign keys
    pointing at the old copy - which is then an empty leftover, and every
    insert through the moved table fails with a foreign key violation. The
    keys are dropped and recreated against the schema the reference actually
    lives in now.
    """
    inspector = sa.inspect(bind)
    repointed: list[str] = []
    for fk in inspector.get_foreign_keys(table.name, schema=schema):
        referred = fk.get("referred_table")
        referred_schema = fk.get("referred_schema")
        constrained = list(fk.get("constrained_columns") or [])
        referred_columns = list(fk.get("referred_columns") or [])
        if not referred or not constrained or not referred_columns:
            continue
        target = _model_schema_for(model_tables, referred) or referred_schema
        if not target or target == referred_schema:
            continue
        if target not in _schemas_with(bind, referred):
            continue
        op.drop_constraint(
            fk["name"], table.name, schema=schema, type_="foreignkey"
        )
        op.create_foreign_key(
            fk["name"],
            table.name,
            referred,
            constrained,
            referred_columns,
            source_schema=schema,
            referent_schema=target,
        )
        repointed.append(f"{table.name}.{fk['name']}")
    return repointed


def _create_move_log(bind) -> None:
    op.execute(
        f'CREATE TABLE IF NOT EXISTS "{MOVE_LOG_SCHEMA}"."{MOVE_LOG_TABLE}" ('
        "table_name TEXT NOT NULL, source_schema TEXT NOT NULL, "
        "target_schema TEXT NOT NULL, "
        "PRIMARY KEY (table_name, source_schema, target_schema))"
    )


def _record_move(bind, table_name: str, source: str, target: str) -> None:
    op.execute(
        f'INSERT INTO "{MOVE_LOG_SCHEMA}"."{MOVE_LOG_TABLE}" '
        "(table_name, source_schema, target_schema) "
        f"VALUES ('{table_name}', '{source}', '{target}') "
        "ON CONFLICT (table_name, source_schema, target_schema) DO NOTHING"
    )


def _move_log_rows(bind) -> list[tuple[str, str, str]]:
    rows = bind.execute(
        sa.text(
            f'SELECT table_name, source_schema, target_schema '
            f'FROM "{MOVE_LOG_SCHEMA}"."{MOVE_LOG_TABLE}"'
        )
    ).all()
    return [(row[0], row[1], row[2]) for row in rows]


def upgrade() -> None:
    if not _is_postgres():
        return

    bind = op.get_bind()
    model_tables = _model_tables()
    _create_move_log(bind)

    # The schemas the models claim for each table name. Two models can share
    # a name (the application has `core.security_event` and the monitoring
    # bundle has `telemetry.security_event`), and each schema belongs to
    # exactly one of them - so a table in a claimed schema is never a leftover
    # of another one.
    claimed: dict[str, set[str]] = {}
    for model_table in model_tables:
        claimed.setdefault(model_table.name, set()).add(model_table.schema)

    for table in model_tables:
        schema = table.schema
        if not schema:
            continue
        schemas = _schemas_with(bind, table.name)
        if schema in schemas:
            # The table is where the models want it. A table with the same
            # name in a schema another model claims is that model's table -
            # leave it alone. Anything else is a leftover copy: dropped when
            # it is empty, kept (and reported) when it holds rows.
            for other in schemas:
                if other == schema:
                    continue
                if other in claimed.get(table.name, set()):
                    continue
                if _row_count(bind, other, table.name) == 0:
                    op.execute(f'DROP TABLE "{other}"."{table.name}" CASCADE')
                else:
                    print(
                        f"[021] kept {other}.{table.name}: it holds rows and "
                        f"{schema}.{table.name} already exists - merge by hand"
                    )
            _add_missing_columns(bind, table, schema)
            _align_enum_columns(bind, table, schema)
            _repoint_foreign_keys(bind, model_tables, table, schema)
            _ensure_indexes(bind, table, schema)
            continue

        # The table is not in its schema yet. A copy of it may exist in a
        # schema no other model claims for that name - the history created
        # several tables unqualified.
        legacy = next(
            (s for s in schemas if s not in claimed.get(table.name, set())),
            None,
        )
        if legacy:
            # Move it: the rows come with it.
            op.execute(
                f'ALTER TABLE "{legacy}"."{table.name}" SET SCHEMA "{schema}"'
            )
            _record_move(bind, table.name, legacy, schema)
            _add_missing_columns(bind, table, schema)
            _align_enum_columns(bind, table, schema)
            _repoint_foreign_keys(bind, model_tables, table, schema)
            _ensure_indexes(bind, table, schema)
            continue

        # The models declare a table the history never created.
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    if not _is_postgres():
        return

    bind = op.get_bind()

    # Undo exactly the moves this migration made - the log says which table
    # went from where to where, so nothing has to be guessed (and two tables
    # that share a name in different schemas stay apart). The move goes back
    # the other way: from where the table ended up to where it started.
    for table_name, source, target in _move_log_rows(bind):
        if target in _schemas_with(bind, table_name) and source not in _schemas_with(
            bind, table_name
        ):
            op.execute(
                f'ALTER TABLE "{target}"."{table_name}" SET SCHEMA "{source}"'
            )

    # The tables this migration created go away again.
    for qualified in CREATED_BY_021:
        schema, _, name = qualified.partition(".")
        if schema in _schemas_with(bind, name):
            op.execute(f'DROP TABLE IF EXISTS "{schema}"."{name}" CASCADE')

    op.execute(f'DROP TABLE IF EXISTS "{MOVE_LOG_SCHEMA}"."{MOVE_LOG_TABLE}" CASCADE')
