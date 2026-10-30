"""Align the columns with the models.

Phase 10 preparation, and the last of the model/migration drift. The models
were edited over time without a migration, so the database is stricter (or
looser) than the application expects:

- **29 columns** are `NOT NULL` in the database while the model allows null.
  The app writes a null there and Postgres refuses it - a failure that only
  shows up on the write path, never in a test that reads.
- `core.user.permissions` is a column the model dropped (the role enum
  replaced it) and nothing reads it any more.

The nullability is aligned from the model metadata, so a column the models
allow to be null stops being not-null, and a column the models require stays
required. The dropped column goes with the model that dropped it.

Revision: 022
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022_align_columns"
down_revision: Union[str, None] = "021_reconcile_schema_placement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Columns the models dropped and the database still carries. The application
#: does not read them; the rows are checked before the column goes.
DROPPED_COLUMNS = (("core", "user", "permissions"),)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _model_tables():
    """Every table the models declare, with a schema."""
    from sqlmodel import SQLModel

    import models  # noqa: F401  - populates the metadata
    import features.oppfeed.models  # noqa: F401

    return [t for t in SQLModel.metadata.sorted_tables if t.schema]


def _columns(bind, schema: str, table: str) -> dict[str, bool]:
    """The table's columns and whether each one is NOT NULL."""
    rows = bind.execute(
        sa.text(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    ).all()
    return {row[0]: row[1] == "NO" for row in rows}


def upgrade() -> None:
    if not _is_postgres():
        return

    bind = op.get_bind()
    for table in _model_tables():
        schema, name = table.schema, table.name
        existing = _columns(bind, schema, name)
        if not existing:
            continue
        for column in table.columns:
            if column.name not in existing:
                continue
            db_not_null = existing[column.name]
            model_nullable = bool(column.nullable)
            if model_nullable and db_not_null:
                # The model allows null here; the database does not. The app
                # would hit "null value violates not-null constraint".
                op.execute(
                    f'ALTER TABLE "{schema}"."{name}" '
                    f'ALTER COLUMN "{column.name}" DROP NOT NULL'
                )

    for schema, table, column in DROPPED_COLUMNS:
        if column in _columns(bind, schema, table):
            op.execute(f'ALTER TABLE "{schema}"."{table}" DROP COLUMN "{column}"')


def downgrade() -> None:
    if not _is_postgres():
        return
    # Not reversible on purpose: re-adding a NOT NULL constraint to a column
    # that may hold nulls would fail, and re-adding the dropped column would
    # resurrect a field the application no longer reads.
    pass
