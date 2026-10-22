"""Add is_read to core.mail_message.

The Phase 2 foundation migration (029) created mail_message without a
per-message read flag; user message state lives in mail_user_message_state,
but the response schema still needs a top-level is_read for the common case
(single-user inbox). This adds it with a safe default of False.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_mail_message_is_read"
down_revision: Union[str, None] = "029_mail_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _column_exists(table: str, column: str) -> bool:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'core' AND table_name = :table "
            "AND column_name = :column"
        ),
        {"table": table, "column": column},
    ).all()
    return bool(rows)


def upgrade() -> None:
    if not _is_postgres():
        return
    for column in ("is_read", "is_starred", "is_important", "is_quarantined"):
        if not _column_exists("mail_message", column):
            op.add_column(
                "mail_message",
                sa.Column(column, sa.Boolean(), nullable=False, server_default=sa.false()),
                schema="core",
            )


def downgrade() -> None:
    if not _is_postgres():
        return
    for column in ("is_read", "is_starred", "is_important", "is_quarantined"):
        if _column_exists("mail_message", column):
            op.drop_column("mail_message", column, schema="core")
