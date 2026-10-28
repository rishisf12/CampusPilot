"""Add the 'faculty' value to the core user_role enum.

Faculty accounts can now be created and sign in. The role column is a native
PostgreSQL enum created with ('student', 'admin'), so the new label has to be
added to the type itself before any row or query can use it.

PostgreSQL 12+ allows ALTER TYPE ... ADD VALUE inside a transaction as long as
the type was not created in the same one - it was not, so a plain execute is
enough. IF NOT EXISTS keeps the migration idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Keep this id <= 32 characters: alembic_version.version_num is varchar(32).
revision: str = "031_user_role_faculty"
down_revision: Union[str, None] = "030_mail_message_is_read"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite stores the column as VARCHAR; nothing to alter.
    bind.execute(sa.text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'faculty'"))


def downgrade() -> None:
    """Deliberately a no-op: Postgres cannot remove an enum value in place,
    and downgrading a database that may already hold faculty rows would be
    destructive. Leaving the value in place is harmless."""
    pass
