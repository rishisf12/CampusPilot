"""maintenance_mode

Revision ID: 007_maintenance_mode
Revises: 006_feature_flags
Create Date: 2026-10-15 00:00:03.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '007_maintenance_mode'
down_revision: Union[str, None] = '006_feature_flags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create maintenance_window table
    op.create_table(
        'maintenance_window',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('global_maintenance', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('target_features', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('allow_list_user_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('bypass_roles', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index('ix_maintenance_window_enabled', 'maintenance_window', ['enabled'], schema='core')
    op.create_index('ix_maintenance_window_scheduled', 'maintenance_window', ['scheduled_start', 'scheduled_end'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_maintenance_window_scheduled', table_name='maintenance_window', schema='core')
    op.drop_index('ix_maintenance_window_enabled', table_name='maintenance_window', schema='core')
    op.drop_table('maintenance_window', schema='core')