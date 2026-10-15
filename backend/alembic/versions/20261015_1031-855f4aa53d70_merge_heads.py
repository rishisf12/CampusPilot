"""merge heads

Revision ID: 855f4aa53d70
Revises: 003_user_profile_branch_id, 008_remote_config
Create Date: 2026-10-15 10:31:36.295563
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '855f4aa53d70'
down_revision: Union[str, None] = ('003_user_profile_branch_id', '008_remote_config')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass