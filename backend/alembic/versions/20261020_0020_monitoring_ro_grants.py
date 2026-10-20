"""Extend the monitoring read-only role over the telemetry schema.

Phase 7 of docs/MCP_MIGRATION_PLAN.md. The role `monitoring_ro` was created
by migration 0c60d501467d with grants on *unqualified* table names, which
predate the monitoring tables' move into the `telemetry` schema. This
migration grants it properly:

- USAGE on the `telemetry` schema;
- SELECT on the allowlist - the tables the scan tools read - and nothing
  else;
- the role keeps `default_transaction_read_only = on`, so even a mistake
  cannot write.

The allowlist is the SQL_ALLOWLIST from SCAN-AGENT.md rule 4: the tables a
scan may read. `tool_call_audit` is in it (a scan reads its own trail) but
the role still cannot write to it - the audit rows are written by the
application role, which the scan worker uses for the write and the read-only
role for the analysis.

Revision: 020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020_monitoring_ro_grants"
down_revision: Union[str, None] = "019_reactor_proposals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: The tables a scan may read. This is the SQL_ALLOWLIST.
TELEMETRY_ALLOWLIST = [
    "event",
    "event_hourly",
    "monitoring_session",
    "purchase",
    "ad_event",
    "crash_report",
    "security_event",
    "scan_result",
    "status_transition",
    "tool_call_audit",
    "health_metric",
    "slow_endpoint",
    "security_log",
    "dependency_vulnerability",
    "security_header_check",
    "feedback_analysis",
    "feedback_sentiment_snapshot",
    "subscription",
    "revenue_snapshot",
    "reactor_proposal",
]


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _table_exists(schema: str, table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names(schema=schema)


def upgrade() -> None:
    if not _is_postgres():
        return

    op.execute(
        "DO $$ "
        "BEGIN "
        "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitoring_ro') THEN "
        "    CREATE ROLE monitoring_ro NOINHERIT; "
        "  END IF; "
        "END $$;"
    )
    op.execute("ALTER ROLE monitoring_ro SET default_transaction_read_only = on")

    if not _table_exists("telemetry", "health_metric"):
        # The telemetry schema is not there yet (a fresh database that has
        # not run create_all); the grants are for the next pass.
        return

    op.execute("GRANT USAGE ON SCHEMA telemetry TO monitoring_ro")
    for table in TELEMETRY_ALLOWLIST:
        if _table_exists("telemetry", table):
            op.execute(f'GRANT SELECT ON telemetry."{table}" TO monitoring_ro')
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA telemetry TO monitoring_ro")


def downgrade() -> None:
    if not _is_postgres():
        return
    if not _table_exists("telemetry", "health_metric"):
        return
    for table in TELEMETRY_ALLOWLIST:
        if _table_exists("telemetry", table):
            op.execute(f'REVOKE SELECT ON telemetry."{table}" FROM monitoring_ro')
    op.execute("REVOKE USAGE ON ALL SEQUENCES IN SCHEMA telemetry FROM monitoring_ro")
