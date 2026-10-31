"""Add the core.task table: a student's 24-hour task tracker.

A task is editable and completable for 24 hours after creation, shows as
expired after that, and is deleted 48 hours after creation (the list read
purges rows past retention). The optional remind_at alarm may only point
into the upcoming 24 hours.
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as postgresql
from alembic import op

# Keep this id <= 32 characters: alembic_version.version_num is varchar(32).
revision: str = "034_task_models"
down_revision: Union[str, None] = "033_faculty_designation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS core.task ("
            "id SERIAL NOT NULL, "
            "user_id INTEGER, "
            "title VARCHAR(200) NOT NULL, "
            "remind_at TIMESTAMP WITH TIME ZONE, "
            "completed_at TIMESTAMP WITH TIME ZONE, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
            "expires_at TIMESTAMP WITH TIME ZONE, "
            "PRIMARY KEY (id), "
            "FOREIGN KEY(user_id) REFERENCES core.\"user\" (id)"
            ")"
        )
    )
    op.create_index(
        "ix_core_task_user_id",
        "task",
        ["user_id"],
        schema="core",
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_core_task_user_id", table_name="task", schema="core", if_exists=True)
    op.drop_table("task", schema="core")
