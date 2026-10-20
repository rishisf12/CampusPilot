"""Add LLM egress columns to tool_call_audit.

Phase 4 of docs/MCP_MIGRATION_PLAN.md. The audit table grows four columns so
one table answers "what left the building, to whom, how big, and how much of
it was masked":

- sent_to            - which provider consumed the request (null for tool calls)
- redactions_applied - how many masks the egress gate applied to the payload
- bytes_out          - size of the outbound payload in bytes (the redacted one)
- redaction_salt     - the run's salt, so a reviewer can reproduce pseudonyms

The last three default to zero/null so existing rows stay valid: a tool call
never sends anything, and an old row predates the concept.

Why this migration resolves the table's schema instead of hard-coding one
------------------------------------------------------------------------
Migration 20261007_1523 created the monitoring tables *unqualified*, so where
`tool_call_audit` lives depends on how the database was built:

- a production/dev database created by `create_all` has it in `telemetry`
  (the schema the model declares);
- a database built purely from the Alembic history has it in the search
  path's first schema, because that is where an unqualified CREATE TABLE
  lands.

Rather than assume, the migration looks the table up and alters it where it
actually is. If the table does not exist at all yet, there is nothing to
alter - `create_all` builds it from the models, which already carry the
columns.

Revision: 017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_llm_egress_audit"
down_revision: Union[str, None] = "016_oppfeed_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "tool_call_audit"
_CANDIDATE_SCHEMAS = ("telemetry", "core")


def _table_schema() -> str | None:
    """The schema the audit table actually lives in, or None if it is absent."""
    rows = op.get_bind().execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :table AND table_schema = ANY(:schemas)"
        ),
        {"table": _TABLE, "schemas": list(_CANDIDATE_SCHEMAS)},
    ).all()
    if not rows:
        return None
    schemas = {row[0] for row in rows}
    for preferred in _CANDIDATE_SCHEMAS:
        if preferred in schemas:
            return preferred
    return sorted(schemas)[0]


def _existing_columns(schema: str) -> set[str]:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": _TABLE},
    ).all()
    return {row[0] for row in rows}


def upgrade() -> None:
    schema = _table_schema()
    if schema is None:
        # No table yet: create_all builds it from the models, columns included.
        return

    existing = _existing_columns(schema)
    if "sent_to" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("sent_to", sa.String(length=100), nullable=True),
            schema=schema,
        )
    if "redactions_applied" not in existing:
        op.add_column(
            _TABLE,
            sa.Column(
                "redactions_applied", sa.Integer(), nullable=False, server_default="0"
            ),
            schema=schema,
        )
    if "bytes_out" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("bytes_out", sa.Integer(), nullable=False, server_default="0"),
            schema=schema,
        )
    if "redaction_salt" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("redaction_salt", sa.String(length=64), nullable=True),
            schema=schema,
        )
    op.create_index(
        "ix_tool_call_audit_sent_to", _TABLE, ["sent_to"], schema=schema
    )


def downgrade() -> None:
    schema = _table_schema()
    if schema is None:
        return
    existing = _existing_columns(schema)
    op.drop_index("ix_tool_call_audit_sent_to", table_name=_TABLE, schema=schema)
    for column in ("redaction_salt", "bytes_out", "redactions_applied", "sent_to"):
        if column in existing:
            op.drop_column(_TABLE, column, schema=schema)
