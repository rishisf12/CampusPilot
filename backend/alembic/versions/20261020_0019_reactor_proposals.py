"""Add the reactor's proposal table and its audit columns.

Phase 6 of docs/MCP_MIGRATION_PLAN.md. Two changes:

- `telemetry.reactor_proposal` - the durable work item. One row per
  (scan, action, target), so a re-proposal is idempotent rather than a
  duplicate task in the operator's queue. The unique constraint is the
  idempotency guarantee, not a convention.
- `tool_call_audit` gains `proposal_state` (proposed | executed | rejected)
  and `proposal_id`, so every proposal invocation is visible in the same
  audit trail as the tool calls and the LLM requests that led to it.

Like migrations 017 and 018, the audit table's schema is resolved at run
time: the monitoring tables were created unqualified by 20261007_1523, so
where they live depends on how the database was built.

Revision: 019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019_reactor_proposals"
down_revision: Union[str, None] = "018_tool_call_audit_metric_value"
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
    if schema is not None:
        existing = _existing_columns(schema)
        if "proposal_state" not in existing:
            op.add_column(
                _TABLE,
                sa.Column("proposal_state", sa.String(length=32), nullable=True),
                schema=schema,
            )
        if "proposal_id" not in existing:
            op.add_column(
                _TABLE,
                sa.Column("proposal_id", sa.Integer(), nullable=True),
                schema=schema,
            )
        op.create_index(
            "ix_tool_call_audit_proposal_state", _TABLE, ["proposal_state"], schema=schema
        )
        op.create_index(
            "ix_tool_call_audit_proposal_id", _TABLE, ["proposal_id"], schema=schema
        )

    op.create_table(
        "reactor_proposal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_key", sa.String(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("procedure", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scan_id", "action", "target_key", name="uq_reactor_proposal"
        ),
        schema="telemetry",
    )
    op.create_index(
        "ix_reactor_proposal_scan_id", "reactor_proposal", ["scan_id"], schema="telemetry"
    )
    op.create_index(
        "ix_reactor_proposal_action", "reactor_proposal", ["action"], schema="telemetry"
    )
    op.create_index(
        "ix_reactor_proposal_target_key", "reactor_proposal", ["target_key"], schema="telemetry"
    )
    op.create_index(
        "ix_reactor_proposal_state", "reactor_proposal", ["state"], schema="telemetry"
    )


def downgrade() -> None:
    # The table may already be gone: migration 021 creates it on a database
    # the history never covered, and drops it again on the way down.
    op.execute("DROP TABLE IF EXISTS telemetry.reactor_proposal CASCADE")
    schema = _table_schema()
    if schema is None:
        return
    # The index names are not fixed: migration 021 renames them to the
    # schema-qualified names the models declare. Drop whichever exists.
    for name in (
        "ix_tool_call_audit_proposal_state",
        "ix_tool_call_audit_proposal_id",
        f"ix_{schema}_tool_call_audit_proposal_state",
        f"ix_{schema}_tool_call_audit_proposal_id",
    ):
        op.execute(f'DROP INDEX IF EXISTS "{schema}"."{name}"')
    if "proposal_id" in _existing_columns(schema):
        op.drop_column(_TABLE, "proposal_id", schema=schema)
    if "proposal_state" in _existing_columns(schema):
        op.drop_column(_TABLE, "proposal_state", schema=schema)
