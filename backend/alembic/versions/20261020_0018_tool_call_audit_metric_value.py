"""Add metric_value to tool_call_audit.

Phase 5 of docs/MCP_MIGRATION_PLAN.md. The reconciler needs to check a
model's cited number against what the tool actually returned, so the audit
row keeps the answer next to the claim about it. Without this column the
reconciler could only check *that* a tool ran, not *what it said* - and a
model that cited a plausible number from nowhere would pass.

The column holds the tool's redacted answer (the egress gate has already
run), so it carries aggregates, never raw rows.

Like migration 017, this resolves the table's real schema first: the
monitoring tables were created unqualified by 20261007_1523, so where
`tool_call_audit` lives depends on how the database was built.

Revision: 018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018_tool_call_audit_metric_value"
down_revision: Union[str, None] = "017_llm_egress_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "tool_call_audit"
_CANDIDATE_SCHEMAS = ("telemetry", "core")


def _table_schema() -> str | None:
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
    if "metric_value" not in _existing_columns(schema):
        op.add_column(
            _TABLE,
            sa.Column("metric_value", sa.JSON(), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    schema = _table_schema()
    if schema is None:
        return
    if "metric_value" in _existing_columns(schema):
        op.drop_column(_TABLE, "metric_value", schema=schema)
