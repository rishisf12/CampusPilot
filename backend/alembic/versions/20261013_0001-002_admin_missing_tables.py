"""admin_missing_tables

Revision ID: 002_admin_missing_tables
Revises: phase3_001_academic_core
Create Date: 2026-10-13

Creates tables that existed via create_all but never via Alembic:
- academic.reinforcement_pattern (admin pattern CRUD)
- academic.academic_term columns already covered by phase3; model added for metadata parity.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_admin_missing_tables'
down_revision: Union[str, None] = 'phase3_001_academic_core'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('CREATE SCHEMA IF NOT EXISTS "academic"'))
    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS academic.reinforcement_pattern (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            pattern VARCHAR NOT NULL,
            replacement VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT true,
            created_at VARCHAR
        )
    '''))
    op.execute(sa.text(
        'CREATE INDEX IF NOT EXISTS ix_academic_reinforcement_pattern_name '
        'ON academic.reinforcement_pattern (name)'
    ))


def downgrade() -> None:
    op.execute(sa.text('DROP INDEX IF EXISTS ix_academic_reinforcement_pattern_name'))
    op.execute(sa.text('DROP TABLE IF EXISTS academic.reinforcement_pattern'))
