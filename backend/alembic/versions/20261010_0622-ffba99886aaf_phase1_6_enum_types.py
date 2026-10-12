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
    op.execute("ALTER TABLE \"user\" ALTER COLUMN role TYPE user_role USING role::user_role")

    # join_request.status
    op.execute("ALTER TABLE join_request ALTER COLUMN status TYPE join_request_status USING status::join_request_status")

    # exam_upload.kind
    op.execute("ALTER TABLE exam_upload ALTER COLUMN kind TYPE exam_upload_kind USING kind::exam_upload_kind")

    # purchase.kind
    op.execute("ALTER TABLE purchase ALTER COLUMN kind TYPE purchase_kind USING kind::purchase_kind")

    # crash_report.kind
    op.execute("ALTER TABLE crash_report ALTER COLUMN kind TYPE crash_report_kind USING kind::crash_report_kind")

    # security_event.kind
    op.execute("ALTER TABLE security_event ALTER COLUMN kind TYPE security_event_kind USING kind::security_event_kind")

    # scan_result.status
    op.execute("ALTER TABLE scan_result ALTER COLUMN status TYPE scan_result_status USING status::scan_result_status")

    # hackathon.source
    op.execute("ALTER TABLE hackathon ALTER COLUMN source TYPE hackathon_source USING source::hackathon_source")


def downgrade() -> None:
    # Revert columns to varchar
    op.execute("ALTER TABLE hackathon ALTER COLUMN source TYPE VARCHAR USING source::VARCHAR")
    op.execute("ALTER TABLE scan_result ALTER COLUMN status TYPE VARCHAR USING status::VARCHAR")
    op.execute("ALTER TABLE security_event ALTER COLUMN kind TYPE VARCHAR USING kind::VARCHAR")
    op.execute("ALTER TABLE crash_report ALTER COLUMN kind TYPE VARCHAR USING kind::VARCHAR")
    op.execute("ALTER TABLE purchase ALTER COLUMN kind TYPE VARCHAR USING kind::VARCHAR")
    op.execute("ALTER TABLE exam_upload ALTER COLUMN kind TYPE VARCHAR USING kind::VARCHAR")
    op.execute("ALTER TABLE join_request ALTER COLUMN status TYPE VARCHAR USING status::VARCHAR")
    op.execute("ALTER TABLE \"user\" ALTER COLUMN role TYPE VARCHAR USING role::VARCHAR")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS hackathon_source")
    op.execute("DROP TYPE IF EXISTS scan_result_status")
    op.execute("DROP TYPE IF EXISTS security_event_kind")
    op.execute("DROP TYPE IF EXISTS crash_report_kind")
    op.execute("DROP TYPE IF EXISTS purchase_kind")
    op.execute("DROP TYPE IF EXISTS exam_upload_kind")
    op.execute("DROP TYPE IF EXISTS join_request_status")
    op.execute("DROP TYPE IF EXISTS user_role")