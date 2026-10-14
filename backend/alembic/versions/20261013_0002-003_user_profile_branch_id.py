"""user_profile_branch_id

Revision ID: 003_user_profile_branch_id
Revises: 0322cb7c7877
Create Date: 2026-10-13

Adds columns the UserProfile model has but the database lacks:
branch_id (+ FK to academic.branch), section, elective_codes,
attendance_target, skills, bio, contact, original_branch.
All ADD COLUMN IF NOT EXISTS so prod + fresh test rebuilds converge.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003_user_profile_branch_id'
down_revision: Union[str, None] = '0322cb7c7877'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS branch_id INTEGER'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS section VARCHAR'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS elective_codes JSON'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS attendance_target FLOAT DEFAULT 75.0'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS skills JSON'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS bio VARCHAR'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS contact VARCHAR'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS original_branch VARCHAR'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS original_branch_id INTEGER'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS branch_changed_at TIMESTAMP'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS branch_change_requested BOOLEAN DEFAULT false'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS requested_branch VARCHAR'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS requested_branch_id INTEGER'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS branch_change_reason VARCHAR'))
    op.execute(sa.text('ALTER TABLE core.user_profile ADD COLUMN IF NOT EXISTS branch_change_requested_at TIMESTAMP'))
    # The model declares branch Optional, but the original table made it
    # NOT NULL; JSON-only profile writes (skills/elective probes) fail on it.
    op.execute(sa.text('ALTER TABLE core.user_profile ALTER COLUMN branch DROP NOT NULL'))
    op.execute(sa.text(
        'DO $$ BEGIN '
        'IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = \'fk_user_profile_branch\') THEN '
        'ALTER TABLE core.user_profile ADD CONSTRAINT fk_user_profile_branch '
        'FOREIGN KEY (branch_id) REFERENCES academic.branch(id) ON DELETE SET NULL; '
        'END IF; END $$'
    ))
    op.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_user_profile_branch_id ON core.user_profile (branch_id)'))


def downgrade() -> None:
    op.execute(sa.text('ALTER TABLE core.user_profile DROP CONSTRAINT IF EXISTS fk_user_profile_branch'))
    op.execute(sa.text('ALTER TABLE core.user_profile DROP COLUMN IF EXISTS branch_id'))
    op.execute(sa.text('ALTER TABLE core.user_profile DROP COLUMN IF EXISTS section'))
