"""create_monitoring_readonly_role

Revision ID: 0c60d501467d
Revises: 27f44ac2c78b
Create Date: 2026-10-08 09:53:55.416884
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '0c60d501467d'
down_revision: Union[str, None] = '27f44ac2c78b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONITORING_TABLES = [
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
]


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        # SQLite doesn't support roles; skip in tests
        return

    # Create read-only role for monitoring scans and dashboards
    op.execute("CREATE ROLE monitoring_ro NOINHERIT")
    op.execute("ALTER ROLE monitoring_ro SET default_transaction_read_only = on")

    # Grant SELECT on all monitoring tables
    for table in MONITORING_TABLES:
        op.execute(f"GRANT SELECT ON {table} TO monitoring_ro")

    # Grant USAGE on sequences for any serial/identity columns
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO monitoring_ro")


def downgrade() -> None:
    if not _is_postgres():
        return

    # Revoke grants
    for table in MONITORING_TABLES:
        op.execute(f"REVOKE SELECT ON {table} FROM monitoring_ro")
    op.execute("REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM monitoring_ro")

    # Drop role
    op.execute("DROP ROLE IF EXISTS monitoring_ro")