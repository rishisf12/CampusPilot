"""audit_log

Revision ID: 004_audit_log
Revises: 0322cb7c7877
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004_audit_log'
down_revision: Union[str, None] = '0322cb7c7877'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create audit_log table in core schema
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_email', sa.String(255), nullable=True),
        sa.Column('actor_role', sa.String(50), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('target_type', sa.String(100), nullable=True),
        sa.Column('target_id', sa.String(100), nullable=True),
        sa.Column('before_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_hash', sa.String(64), nullable=True),
        sa.Column('user_agent_hash', sa.String(64), nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index('ix_audit_log_actor_id', 'audit_log', ['actor_id'], schema='core')
    op.create_index('ix_audit_log_action', 'audit_log', ['action'], schema='core')
    op.create_index('ix_audit_log_target', 'audit_log', ['target_type', 'target_id'], schema='core')
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_audit_log_created_at', table_name='audit_log', schema='core')
    op.drop_index('ix_audit_log_target', table_name='audit_log', schema='core')
    op.drop_index('ix_audit_log_action', table_name='audit_log', schema='core')
    op.drop_index('ix_audit_log_actor_id', table_name='audit_log', schema='core')
    op.drop_table('audit_log', schema='core')