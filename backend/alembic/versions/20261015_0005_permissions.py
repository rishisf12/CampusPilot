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
    _drop_index_if_present('ix_user_permissions', 'user', schema='core')
    # Migration 022 dropped this column with the model that dropped it, so
    # the downgrade must not insist on dropping it again.
    op.execute('ALTER TABLE core."user" DROP COLUMN IF EXISTS permissions')