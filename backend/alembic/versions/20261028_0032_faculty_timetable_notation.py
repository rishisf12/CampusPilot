"""Add the faculty timetable notation to the profile.

A faculty member appears in the published timetable under a short name
notation (e.g. "ARR"), not a roll number. The column stores exactly that,
so the account can be matched to the slots it owns.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Keep this id <= 32 characters: alembic_version.version_num is varchar(32).
revision: str = "032_faculty_timetable_notation"
down_revision: Union[str, None] = "031_user_role_faculty"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS timetable_notation VARCHAR")
    )


def downgrade() -> None:
    op.drop_column("user_profile", "timetable_notation", schema="core")
