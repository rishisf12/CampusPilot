"""LLM egress auditing columns on telemetry.tool_call_audit.

Phase 4 (MCP migration plan): every outbound LLM request writes a row, and
that row must say which provider consumed what. Tool-call rows leave these
NULL; `llm.*` rows fill them:

- sent_to             - provider name the payload was sent to
- redactions_applied  - masks the egress gate applied to the outgoing prompt
- bytes_out           - redacted payload size (bytes on the wire)
- redaction_salt      - the per-scan-run salt the pseudonyms came from

Resilience note (house pattern from 0014): the historic monitoring baseline
created `tool_call_audit` *unqualified*, while the SQLModel model tags it
`schema="telemetry"`. Fresh databases get the telemetry-qualified mirror from
`SQLModel.metadata.create_all` (already carrying these columns, since the
model was written alongside this migration) - so adding columns to a table
that is not there yet must be skipped, not failed. Long-term fix remains a
squashed baseline migration.

Revision: 017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_tool_call_audit_egress"
down_revision: Union[str, None] = "016_oppfeed_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = {
    "sent_to": sa.Column("sent_to", sa.String(length=255), nullable=True),
    "redactions_applied": sa.Column("redactions_applied", sa.Integer(), nullable=True),
    "bytes_out": sa.Column("bytes_out", sa.Integer(), nullable=True),
    "redaction_salt": sa.Column("redaction_salt", sa.String(length=64), nullable=True),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tool_call_audit" not in inspector.get_table_names(schema="telemetry"):
        # The telemetry mirror does not exist yet in this database; create_all
        # will build it from the model, new columns included. Nothing to do.
        return
    present = {c["name"] for c in inspector.get_columns("tool_call_audit", schema="telemetry")}
    for name, column in _COLUMNS.items():
        if name not in present:
            op.add_column("tool_call_audit", column, schema="telemetry")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tool_call_audit" not in inspector.get_table_names(schema="telemetry"):
        return
    present = {c["name"] for c in inspector.get_columns("tool_call_audit", schema="telemetry")}
    for name in reversed(list(_COLUMNS)):
        if name in present:
            op.drop_column("tool_call_audit", name, schema="telemetry")
