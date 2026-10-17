"""Add `uploaded_by` to the exam tables for personal (per-account) uploads.

Exam uploads were admin-only writes into one global store: a student was
refused with 403, and an admin's file defined the timetable everybody saw.

The rule now is:
* an admin's upload stays public - every account reads it;
* an individual's upload lives in that one account only.

The rows carry their uploader's user id, ``NULL`` meaning an admin's public
upload. Nothing is backfilled: every row already stored is the admin's public
data, and ``NULL`` reads exactly as public.

Schema note. The models place these tables in ``academic``; production's
``create_all`` copies carry their own constraint and index names. The baseline
Alembic migration instead creates unqualified copies that land in ``core``
through the configured search path. Both shapes legitimately coexist - a
database may hold either or both - so this migration works per schema: it
attaches the column wherever the table exists without it, and undo removes
exactly what it added, identified via the inspector rather than assumed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_exam_personal_uploads"
down_revision: Union[str, None] = "013_drop_moderation_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Ordinary tables; ``uploaded_by`` means the same thing on all three, so one
# loop keeps the shapes in step.
TABLES = ("mid_sem_schedule", "exam_seating", "exam_upload")
SCHEMAS = ("core", "academic")
COLUMN = "uploaded_by"
# The `core` catch-up copies predate this column; the academic copy in a
# create_all-first database is older than this revision.
FOUNDATION = ("core", "academic")


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        located = _locate(bind, table)
        if not located:
            raise RuntimeError(
                f"Table `{table}` exists in neither `core` nor `academic`. It "
                "is created either by this project's migration baseline or by "
                "the app's create_all - one of those has to run first."
            )
        for schema in FOUNDATION:
            if table not in _tables(bind, schema) or _has_column(bind, schema, table, COLUMN):
                continue
            op.add_column(
                table,
                sa.Column(COLUMN, sa.Integer(), nullable=True),
                schema=schema,
            )
            op.create_foreign_key(
                f"fk_{schema}_{table}_{COLUMN}_user",
                table,
                "user",
                [COLUMN],
                ["id"],
                source_schema=schema,
                referent_schema="core",
                # The uploader (the person) leaving must not leave their
                # private paper list floating in the public store.
                ondelete="CASCADE",
            )
            op.create_index(
                f"ix_{schema}_{table}_{COLUMN}",
                table,
                [COLUMN],
                schema=schema,
            )


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        for schema in FOUNDATION:
            if not _has_column(bind, schema, table, COLUMN):
                continue
            _drop_index_if_present(bind, schema, table, f"ix_{schema}_{table}_{COLUMN}")
            _drop_fk_if_present(bind, schema, table, f"fk_{schema}_{table}_{COLUMN}_user")
            op.drop_column(table, COLUMN, schema=schema)


def _locate(bind, table: str) -> bool:
    """Whether the table exists under any name the project recognises."""
    return any(table in _tables(bind, schema) for schema in SCHEMAS)


def _tables(bind, schema: str) -> set:
    try:
        return set(sa.inspect(bind).get_table_names(schema=schema))
    except Exception:  # noqa: BLE001 - schema missing on older databases
        return set()


def _has_column(bind, schema: str, table: str, column: str) -> bool:
    try:
        columns = {c["name"] for c in sa.inspect(bind).get_columns(table, schema=schema)}
    except Exception:  # noqa: BLE001 - table missing in this schema
        return False
    return column in columns


def _drop_index_if_present(bind, schema: str, table: str, index_name: str) -> None:
    try:
        names = {ix["name"] for ix in sa.inspect(bind).get_indexes(table, schema=schema)}
    except Exception:  # noqa: BLE001
        return
    if index_name in names:
        op.drop_index(index_name, table_name=table, schema=schema)


def _drop_fk_if_present(bind, schema: str, table: str, fk_name: str) -> None:
    try:
        names = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys(table, schema=schema)}
    except Exception:  # noqa: BLE001
        return
    if fk_name in names:
        op.drop_constraint(fk_name, table, type_="foreignkey", schema=schema)
