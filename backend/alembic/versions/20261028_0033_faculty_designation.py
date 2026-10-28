"""Add the faculty designation to the profile.

Where a faculty member sits on the rolls: Professor, Associate Professor or
Assistant Professor. Signup now asks faculty to pick one, so the profile
needs somewhere to keep it.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Keep this id <= 32 characters: alembic_version.version_num is varchar(32).
revision: str = "033_faculty_designation"
down_revision: Union[str, None] = "032_faculty_timetable_notation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("designation", sa.String(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("user_profile", "designation", schema="core")
