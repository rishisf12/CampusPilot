"""system settings table + user suspension columns

Revision ID: 010_system_settings
Revises: 009_admin_feature_tables
Create Date: 2026-10-16

Two things the Phase 4 contract alignment needs:

1. `core.system_setting`: the Settings tab reads `GET /admin/settings` and
   writes per key, so it needs a key/value store. Seeded with the defaults the
   UI falls back to, so a fresh install and an upgraded one behave the same.
2. `core.user.is_suspended`, `suspended_until`, `is_banned`: the admin
   suspend/ban actions wrote these attributes, but the columns did not exist,
   so every call raised ValueError. Login now enforces them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '010_system_settings'
down_revision: Union[str, None] = '009_admin_feature_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULTS: list[tuple[str, object]] = [
    ("rate_limiting_enabled", True),
    ("brute_force_protection", True),
    ("password_min_length", 8),
    ("auto_vacuum", True),
    ("query_timeout", 30),
    ("default_rollout_percentage", 0),
    ("default_maintenance_message", "Service temporarily unavailable. Please try again later."),
    ("alert_email", ""),
    ("slack_webhook_url", ""),
    ("ios_app_store_url", ""),
    ("android_play_store_url", ""),
]


def upgrade() -> None:
    op.create_table(
        "system_setting",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="core",
    )
    op.add_column("user", sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()), schema="core")
    op.add_column("user", sa.Column("suspended_until", postgresql.TIMESTAMP(timezone=True), nullable=True), schema="core")
    op.add_column("user", sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()), schema="core")

    for key, value in DEFAULTS:
        op.execute(
            sa.text(
                "INSERT INTO core.system_setting (key, value) VALUES (:key, CAST(:value AS JSONB)) "
                "ON CONFLICT (key) DO NOTHING"
            ).bindparams(key=key, value=__import__("json").dumps(value))
        )


def downgrade() -> None:
    op.drop_column("user", "is_banned", schema="core")
    op.drop_column("user", "suspended_until", schema="core")
    op.drop_column("user", "is_suspended", schema="core")
    op.drop_table("system_setting", schema="core")
