"""phase-08 contact models

Revision ID: 0006_phase_08_contact_models
Revises: 0005_phase_07_org_models
Create Date: 2026-11-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0006_phase_08_contact_models"
down_revision = "0005_phase_07_org_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contactgroup",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contactgroup_user_id"), "contactgroup", ["user_id"], unique=False)

    op.create_table(
        "contact",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["group_id"], ["contactgroup.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contact_user_id"), "contact", ["user_id"], unique=False)
    op.create_index(op.f("ix_contact_email"), "contact", ["email"], unique=False)
    op.create_index(op.f("ix_contact_group_id"), "contact", ["group_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_contact_group_id"), table_name="contact")
    op.drop_index(op.f("ix_contact_email"), table_name="contact")
    op.drop_index(op.f("ix_contact_user_id"), table_name="contact")
    op.drop_table("contact")
    op.drop_index(op.f("ix_contactgroup_user_id"), table_name="contactgroup")
    op.drop_table("contactgroup")
