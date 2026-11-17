"""phase-02 account models

Revision ID: 0002_phase_02_account_models
Revises: 0001_phase_01_auth_models
Create Date: 2026-11-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_phase_02_account_models"
down_revision = "0001_phase_01_auth_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mailaccount",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="465"),
        sa.Column("imap_security", sa.String(length=20), nullable=False, server_default="ssl"),
        sa.Column("smtp_security", sa.String(length=20), nullable=False, server_default="ssl"),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=True),
        sa.Column("encrypted_oauth_access_token", sa.Text(), nullable=True),
        sa.Column("encrypted_oauth_refresh_token", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("status_message", sa.String(length=500), nullable=True),
        sa.Column("capabilities", sa.Text(), nullable=True),
        sa.Column("special_use", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mailaccount_user_id"), "mailaccount", ["user_id"], unique=False)

    op.create_table(
        "identity",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("signature_html", sa.Text(), nullable=True),
        sa.Column("signature_plain", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["mailaccount.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_identity_user_id"), "identity", ["user_id"], unique=False)
    op.create_index(op.f("ix_identity_account_id"), "identity", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_identity_account_id"), table_name="identity")
    op.drop_index(op.f("ix_identity_user_id"), table_name="identity")
    op.drop_table("identity")
    op.drop_index(op.f("ix_mailaccount_user_id"), table_name="mailaccount")
    op.drop_table("mailaccount")
