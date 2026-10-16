"""core.user_settings - per-user settings storage

Revision ID: 011_user_settings
Revises: 010_system_settings
Create Date: 2026-10-16

The Settings page (Phase 0, frontend) stored every preference in localStorage,
so a setting did not follow the student to another device and the admin could
not see what anyone had chosen. This gives each user one row of JSON settings.

The document is deliberately schemaless. The key names and their types live in
the frontend registry (`SETTINGS_REGISTRY`), which the server never imports; a
column per setting would mean a migration every time a switch is added.

No seed rows: a user with nothing saved simply has no row, and the client falls
back to its registry defaults.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '011_user_settings'
down_revision: Union[str, None] = '010_system_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        # CASCADE: settings are derived data, so deleting a user takes them with
        # it rather than leaving rows nothing can reach. The primary key already
        # indexes user_id, which is the only column this table is read by.
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("core.user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("user_settings", schema="core")