"""remote_config

Revision ID: 008_remote_config
Revises: 007_maintenance_mode
Create Date: 2026-10-15 00:00:04.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '008_remote_config'
down_revision: Union[str, None] = '007_maintenance_mode'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create remote_config table
    op.create_table(
        'remote_config',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False, unique=True),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('value_type', sa.String(20), nullable=False, server_default='json'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('schema_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('schema_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index('ix_remote_config_key', 'remote_config', ['key'], schema='core', unique=True)
    op.create_index('ix_remote_config_is_public', 'remote_config', ['is_public'], schema='core')

    # Create remote_config_history table for version history and rollback
    op.create_table(
        'remote_config_history',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('config_key', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('value_type', sa.String(20), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index('ix_remote_config_history_config_key', 'remote_config_history', ['config_key'], schema='core')
    op.create_index('ix_remote_config_history_created_at', 'remote_config_history', ['created_at'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_remote_config_history_created_at', table_name='remote_config_history', schema='core')
    op.drop_index('ix_remote_config_history_config_key', table_name='remote_config_history', schema='core')
    op.drop_table('remote_config_history', schema='core')
    op.drop_index('ix_remote_config_is_public', table_name='remote_config', schema='core')
    op.drop_index('ix_remote_config_key', table_name='remote_config', schema='core')
    op.drop_table('remote_config', schema='core')