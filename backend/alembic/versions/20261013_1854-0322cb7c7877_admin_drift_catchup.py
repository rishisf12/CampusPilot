"""admin_drift_catchup (NEUTRALIZED)

Revision ID: 0322cb7c7877
Revises: 002_admin_missing_tables

Autogenerate compared schemas incorrectly and tried to CREATE existing
tables. Neutralized to a no-op to preserve the revision chain.
See 003_user_profile_branch_id for the real targeted fix.
"""
from typing import Sequence, Union

revision: str = '0322cb7c7877'
down_revision: Union[str, None] = '002_admin_missing_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    return


def downgrade() -> None:
    return
