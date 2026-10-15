"""permissions

Revision ID: 005_permissions
Revises: 004_audit_log
Create Date: 2026-10-15 00:00:01.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '005_permissions'
down_revision: Union[str, None] = '004_audit_log'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add permissions column to core.user
    op.add_column(
        'user',
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='core'
    )
    # Create index for permission lookups
    op.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_user_permissions ON core.user USING GIN (permissions)'))


def downgrade() -> None:
    op.drop_index('ix_user_permissions', table_name='user', schema='core')
    op.drop_column('user', 'permissions', schema='core')