"""phase1_6_enum_types

Revision ID: ffba99886aaf
Revises: 8e1fa85035dc
Create Date: 2026-10-10 06:22:52.480729
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'ffba99886aaf'
down_revision: Union[str, None] = '8e1fa85035dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _alter(table: str, column: str, target_type: str, using: str) -> None:
    """Alter a column where the table actually is.

    The tables live in schemas (`telemetry.security_event`,
    `academic.exam_upload`, ...), so an unqualified ALTER only finds them
    when the search path happens to point at the right schema.
    """
    import sqlalchemy as sa

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column "
            "ORDER BY table_schema"
        ),
        {"table": table, "column": column},
    ).all()
    if not rows:
        return
    for (schema,) in rows:
        op.execute(
            f'ALTER TABLE "{schema}"."{table}" ALTER COLUMN "{column}" '
            f"TYPE {target_type} USING {column}::{using}"
        )


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE user_role AS ENUM ('student', 'admin')")
    op.execute("CREATE TYPE join_request_status AS ENUM ('pending', 'accepted', 'rejected')")
    op.execute("CREATE TYPE exam_upload_kind AS ENUM ('timetable', 'seating')")
    op.execute("CREATE TYPE purchase_kind AS ENUM ('one_time', 'subscription', 'consumable', 'restore')")
    op.execute("CREATE TYPE crash_report_kind AS ENUM ('crash', 'anr')")
    op.execute("CREATE TYPE security_event_kind AS ENUM ('failed_login', 'brute_force', 'token_misuse', 'api_abuse', 'root_detected', 'emulator_detected', 'tamper_detected', 'rate_limited', 'waf_blocked')")
    op.execute("CREATE TYPE scan_result_status AS ENUM ('healthy', 'warning', 'critical', 'error')")
    op.execute("CREATE TYPE hackathon_source AS ENUM ('email', 'manual')")

    # Migrate columns to enum types
    # user.role
    _alter("user", "role", "user_role", "user_role")

    # join_request.status
    _alter("join_request", "status", "join_request_status", "join_request_status")

    # exam_upload.kind
    _alter("exam_upload", "kind", "exam_upload_kind", "exam_upload_kind")

    # purchase.kind
    _alter("purchase", "kind", "purchase_kind", "purchase_kind")

    # crash_report.kind
    _alter("crash_report", "kind", "crash_report_kind", "crash_report_kind")

    # security_event.kind
    _alter("security_event", "kind", "security_event_kind", "security_event_kind")

    # scan_result.status
    _alter("scan_result", "status", "scan_result_status", "scan_result_status")

    # hackathon.source
    _alter("hackathon", "source", "hackathon_source", "hackathon_source")


def downgrade() -> None:
    # Revert columns to varchar
    _alter("hackathon", "source", "VARCHAR", "text")
    _alter("scan_result", "status", "VARCHAR", "text")
    _alter("security_event", "kind", "VARCHAR", "text")
    _alter("crash_report", "kind", "VARCHAR", "text")
    _alter("purchase", "kind", "VARCHAR", "text")
    _alter("exam_upload", "kind", "VARCHAR", "text")
    _alter("join_request", "status", "VARCHAR", "text")
    _alter("user", "role", "VARCHAR", "text")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS hackathon_source")
    op.execute("DROP TYPE IF EXISTS scan_result_status")
    op.execute("DROP TYPE IF EXISTS security_event_kind")
    op.execute("DROP TYPE IF EXISTS crash_report_kind")
    op.execute("DROP TYPE IF EXISTS purchase_kind")
    op.execute("DROP TYPE IF EXISTS exam_upload_kind")
    op.execute("DROP TYPE IF EXISTS join_request_status")
    op.execute("DROP TYPE IF EXISTS user_role")