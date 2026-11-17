"""phase-07 organization models

Revision ID: 0005_phase_07_org_models
Revises: 0004_phase_06_compose_models
Create Date: 2026-11-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005_phase_07_org_models"
down_revision = "0004_phase_06_compose_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "savedsearch",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
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
    op.create_index(op.f("ix_savedsearch_user_id"), "savedsearch", ["user_id"], unique=False)

    op.create_table(
        "snooze",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wake_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("woke", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    op.create_index(op.f("ix_snooze_user_id"), "snooze", ["user_id"], unique=False)
    op.create_index(op.f("ix_snooze_message_id"), "snooze", ["message_id"], unique=False)
    op.create_index("ix_snooze_wake_at_woke", "snooze", ["wake_at", "woke"], unique=False)

    op.create_table(
        "reminder",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    op.create_index(op.f("ix_reminder_user_id"), "reminder", ["user_id"], unique=False)
    op.create_index(op.f("ix_reminder_message_id"), "reminder", ["message_id"], unique=False)
    op.create_index("ix_reminder_due_at_fired", "reminder", ["due_at", "fired"], unique=False)

    op.create_table(
        "rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stop_on_match", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    op.create_index(op.f("ix_rule_user_id"), "rule", ["user_id"], unique=False)

    op.create_table(
        "vacationresponder",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("subject", sa.String(length=1000), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("once_per_sender", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vacationresponder_user_id"), "vacationresponder", ["user_id"], unique=False)
    op.create_index(op.f("ix_vacationresponder_account_id"), "vacationresponder", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_vacationresponder_account_id"), table_name="vacationresponder")
    op.drop_index(op.f("ix_vacationresponder_user_id"), table_name="vacationresponder")
    op.drop_table("vacationresponder")
    op.drop_index(op.f("ix_rule_user_id"), table_name="rule")
    op.drop_table("rule")
    op.drop_index("ix_reminder_due_at_fired", table_name="reminder")
    op.drop_index(op.f("ix_reminder_message_id"), table_name="reminder")
    op.drop_index(op.f("ix_reminder_user_id"), table_name="reminder")
    op.drop_table("reminder")
    op.drop_index("ix_snooze_wake_at_woke", table_name="snooze")
    op.drop_index(op.f("ix_snooze_message_id"), table_name="snooze")
    op.drop_index(op.f("ix_snooze_user_id"), table_name="snooze")
    op.drop_table("snooze")
    op.drop_index(op.f("ix_savedsearch_user_id"), table_name="savedsearch")
    op.drop_table("savedsearch")
