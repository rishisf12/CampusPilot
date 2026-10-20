"""feature_flags

Revision ID: 006_feature_flags
Revises: 005_permissions
Create Date: 2026-10-15 00:00:02.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '006_feature_flags'
down_revision: Union[str, None] = '005_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create feature_flag table
    op.create_table(
        'feature_flag',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False, unique=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('rollout_percentage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('target_roles', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('target_user_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('target_platforms', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('target_app_versions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index('ix_feature_flag_key', 'feature_flag', ['key'], schema='core', unique=True)
    op.create_index('ix_feature_flag_enabled', 'feature_flag', ['enabled'], schema='core')

    # Create flag_target table for complex targeting rules
    op.create_table(
        'flag_target',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('flag_id', sa.Integer(), sa.ForeignKey('core.feature_flag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('attribute', sa.String(50), nullable=False),
        sa.Column('operator', sa.String(20), nullable=False),
        sa.Column('values', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index('ix_flag_target_flag_id', 'flag_target', ['flag_id'], schema='core')


def _drop_index_if_present(index_name: str, table_name: str, schema: str | None = None) -> None:
    """Drop an index only when the database still has it.

    A later migration may have dropped the column the index belonged to
    (and the index with it), and a downgrade must not fail because of it.
    """
    import sqlalchemy as sa

    bind = op.get_bind()
    if schema:
        bind.execute(sa.text(f'DROP INDEX IF EXISTS "{schema}"."{index_name}"'))
    else:
        bind.execute(sa.text(f'DROP INDEX IF EXISTS "{index_name}"'))


def downgrade() -> None:
    _drop_index_if_present('ix_flag_target_flag_id', 'flag_target', schema='core')
    op.drop_table('flag_target', schema='core')
    _drop_index_if_present('ix_feature_flag_enabled', 'feature_flag', schema='core')
    _drop_index_if_present('ix_feature_flag_key', 'feature_flag', schema='core')
    op.drop_table('feature_flag', schema='core')