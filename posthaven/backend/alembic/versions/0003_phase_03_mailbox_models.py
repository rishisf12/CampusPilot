"""phase-03 mailbox models

Revision ID: 0003_phase_03_mailbox_models
Revises: 0002_phase_02_account_models
Create Date: 2026-11-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_phase_03_mailbox_models"
down_revision = "0002_phase_02_account_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "folder",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("delimiter", sa.String(length=10), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("special_use", sa.String(length=50), nullable=True),
        sa.Column("subscribed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("uidvalidity", sa.String(length=64), nullable=True),
        sa.Column("uidnext", sa.Integer(), nullable=True),
        sa.Column("highestmodseq", sa.BigInteger(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["account_id"], ["mailaccount.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["folder.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_folder_user_id"), "folder", ["user_id"], unique=False)
    op.create_index(op.f("ix_folder_account_id"), "folder", ["account_id"], unique=False)
    op.create_index(op.f("ix_folder_parent_id"), "folder", ["parent_id"], unique=False)

    op.create_table(
        "thread",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=1000), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index(op.f("ix_thread_user_id"), "thread", ["user_id"], unique=False)
    op.create_index(op.f("ix_thread_account_id"), "thread", ["account_id"], unique=False)

    op.create_table(
        "message",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=512), nullable=True),
        sa.Column("in_reply_to", sa.String(length=512), nullable=True),
        sa.Column("references", sa.Text(), nullable=True),
        sa.Column("from_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("to_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cc_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bcc_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("subject", sa.String(length=1000), nullable=True),
        sa.Column("snippet", sa.String(length=2000), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("search_vector", sa.Text(), nullable=True),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("internal_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["mailaccount.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["folder_id"], ["folder.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["thread.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_uid_unique",
        "message",
        ["account_id", "folder_id", "uid"],
        unique=True,
    )
    op.create_index(
        "ix_message_account_folder_received",
        "message",
        ["account_id", "folder_id", "received_at"],
        unique=False,
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_message_search_vector",
        "message",
        ["search_vector"],
        postgresql_using="gin",
        postgresql_ops={"search_vector": "gin_trgm_ops"},
    )
    op.create_index(op.f("ix_message_user_id"), "message", ["user_id"], unique=False)
    op.create_index(op.f("ix_message_thread_id"), "message", ["thread_id"], unique=False)

    op.create_table(
        "attachment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_id", sa.String(length=512), nullable=True),
        sa.Column("is_inline", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["message_id"], ["message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attachment_user_id"), "attachment", ["user_id"], unique=False)
    op.create_index(op.f("ix_attachment_message_id"), "attachment", ["message_id"], unique=False)

    op.create_table(
        "label",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="#6b7280"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_label_user_id"), "label", ["user_id"], unique=False)

    op.create_table(
        "messagelabel",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messagelabel_message_id"), "messagelabel", ["message_id"], unique=False)
    op.create_index(op.f("ix_messagelabel_label_id"), "messagelabel", ["label_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_messagelabel_label_id"), table_name="messagelabel")
    op.drop_index(op.f("ix_messagelabel_message_id"), table_name="messagelabel")
    op.drop_table("messagelabel")
    op.drop_index(op.f("ix_label_user_id"), table_name="label")
    op.drop_table("label")
    op.drop_index(op.f("ix_attachment_message_id"), table_name="attachment")
    op.drop_index(op.f("ix_attachment_user_id"), table_name="attachment")
    op.drop_table("attachment")
    op.drop_index(op.f("ix_message_thread_id"), table_name="message")
    op.drop_index(op.f("ix_message_user_id"), table_name="message")
    op.drop_index("ix_message_search_vector", table_name="message")
    op.drop_index("ix_message_account_folder_received", table_name="message")
    op.drop_index("ix_message_uid_unique", table_name="message")
    op.drop_table("message")
    op.drop_index(op.f("ix_thread_account_id"), table_name="thread")
    op.drop_index(op.f("ix_thread_user_id"), table_name="thread")
    op.drop_table("thread")
    op.drop_index(op.f("ix_folder_parent_id"), table_name="folder")
    op.drop_index(op.f("ix_folder_account_id"), table_name="folder")
    op.drop_index(op.f("ix_folder_user_id"), table_name="folder")
    op.drop_table("folder")
