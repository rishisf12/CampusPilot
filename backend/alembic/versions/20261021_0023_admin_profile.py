"""Create the admin_profile table.

The administrator's own profile - an operator's, not a student's. See the
model for what it carries and why.

Revision: 023
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_admin_profile"
down_revision: Union[str, None] = "022_align_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists() -> bool:
    """Is the table already there?

    It can be: migration 021 reconciles the placement with the models and
    creates any table the history never made - including this one, since the
    model exists by the time 021 runs. So this migration creates the table
    only when it is missing, and always makes sure the index is there.
    """
    row = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'core' AND table_name = 'admin_profile'"
        )
    ).first()
    return row is not None


def upgrade() -> None:
    if not _table_exists():
        op.create_table(
            "admin_profile",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("display_name", sa.String(length=120), nullable=True),
            sa.Column("job_title", sa.String(length=120), nullable=True),
            sa.Column("team", sa.String(length=120), nullable=True),
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
            sa.Column("locale", sa.String(length=16), nullable=False, server_default="en-IN"),
            sa.Column("theme", sa.String(length=16), nullable=False, server_default="system"),
            sa.Column("density", sa.String(length=16), nullable=False, server_default="comfortable"),
            sa.Column("default_subsection", sa.String(length=32), nullable=True),
            sa.Column("default_window_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("pinned_panels", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("notify_email", sa.String(length=255), nullable=True),
            sa.Column("notify_channels", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("quiet_hours", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["user_id"], ["core.user.id"]),
            sa.PrimaryKeyConstraint("id"),
            schema="core",
        )
    # `unique=True, index=True` on the model is a unique *index*, named the
    # way SQLAlchemy names a schema-qualified one.
    op.create_index(
        "ix_core_admin_profile_user_id",
        "admin_profile",
        ["user_id"],
        unique=True,
        schema="core",
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_admin_profile_user_id",
        table_name="admin_profile",
        schema="core",
        if_exists=True,
    )
    op.drop_table("admin_profile", schema="core")
