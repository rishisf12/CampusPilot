"""Add the batch year to the profile.

The roll number carries the batch ("24BCS125" is the 2024 batch), but the
roll is a label: the batch year is the fact, and it is what tells one
batch's exam papers from another's.

Revision: 025
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025_batch_year"
down_revision: Union[str, None] = "024_reconcile_seating"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists() -> bool:
    row = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'core' AND table_name = 'user_profile' "
            "AND column_name = 'batch_year'"
        )
    ).first()
    return row is not None


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    if _column_exists():
        return
    op.add_column(
        "user_profile",
        sa.Column("batch_year", sa.Integer(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    if not _column_exists():
        return
    op.drop_column("user_profile", "batch_year", schema="core")
