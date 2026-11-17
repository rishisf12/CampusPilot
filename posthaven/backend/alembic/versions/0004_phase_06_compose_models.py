"""phase-06 compose models

Revision ID: 0004_phase_06_compose_models
Revises: 0003_phase_03_mailbox_models
Create Date: 2026-11-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_phase_06_compose_models"
down_revision = "0003_phase_03_mailbox_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "draft",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cc_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bcc_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("subject", sa.String(length=1000), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("reply_to_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["mailaccount.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["identity_id"], ["identity.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reply_to_message_id"], ["message.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_draft_user_id"), "draft", ["user_id"], unique=False)
    op.create_index(op.f("ix_draft_account_id"), "draft", ["account_id"], unique=False)
    op.create_index(op.f("ix_draft_identity_id"), "draft", ["identity_id"], unique=False)
    op.create_index(op.f("ix_draft_reply_to_message_id"), "draft", ["reply_to_message_id"], unique=False)

    op.create_table(
        "scheduledsend",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cc_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bcc_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("subject", sa.String(length=1000), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("queued", "sending", "sent", "failed", "undone", name="sendstatus"), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["mailaccount.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["identity_id"], ["identity.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scheduledsend_user_id"), "scheduledsend", ["user_id"], unique=False)
    op.create_index(op.f("ix_scheduledsend_account_id"), "scheduledsend", ["account_id"], unique=False)
    op.create_index(op.f("ix_scheduledsend_identity_id"), "scheduledsend", ["identity_id"], unique=False)
    op.create_index(op.f("ix_scheduledsend_idempotency_key"), "scheduledsend", ["idempotency_key"], unique=True)
    op.create_index("ix_scheduledsend_send_at_status", "scheduledsend", ["send_at", "status"], unique=False)

    op.create_table(
        "template",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=1000), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
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
    op.create_index(op.f("ix_template_user_id"), "template", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_template_user_id"), table_name="template")
    op.drop_table("template")
    op.drop_index(op.f("ix_scheduledsend_idempotency_key"), table_name="scheduledsend")
    op.drop_index("ix_scheduledsend_send_at_status", table_name="scheduledsend")
    op.drop_index(op.f("ix_scheduledsend_identity_id"), table_name="scheduledsend")
    op.drop_index(op.f("ix_scheduledsend_account_id"), table_name="scheduledsend")
    op.drop_index(op.f("ix_scheduledsend_user_id"), "scheduledsend")
    op.drop_table("scheduledsend")
    op.drop_index(op.f("ix_draft_reply_to_message_id"), table_name="draft")
    op.drop_index(op.f("ix_draft_identity_id"), table_name="draft")
    op.drop_index(op.f("ix_draft_account_id"), table_name="draft")
    op.drop_index(op.f("ix_draft_user_id"), table_name="draft")
    op.drop_table("draft")
