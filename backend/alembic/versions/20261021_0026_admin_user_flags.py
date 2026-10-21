"""Say who is who: faculty and class representatives on the profile.

An account only ever carries the role "admin" or "student", so the admin's
question "who are the faculty" and "who are the CRs of ME sem 3" had
nothing to filter on. Two flags on the profile answer both without a second
table of memberships.

Revision: 026
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026_admin_user_flags"
down_revision: Union[str, None] = "025_batch_year"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: The columns this migration adds, with the default the model carries.
COLUMNS = (
    ("is_faculty", sa.Boolean(), sa.false()),
    ("is_class_representative", sa.Boolean(), sa.false()),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _existing() -> set:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'core' AND table_name = 'user_profile'"
        )
    ).all()
    return {row[0] for row in rows}


def upgrade() -> None:
    if not _is_postgres():
        return
    present = _existing()
    for name, type_, default in COLUMNS:
        if name in present:
            continue
        op.add_column(
            "user_profile",
            sa.Column(name, type_, nullable=False, server_default=default),
            schema="core",
        )


def downgrade() -> None:
    if not _is_postgres():
        return
    present = _existing()
    for name, _type, _default in reversed(COLUMNS):
        if name not in present:
            continue
        op.drop_column("user_profile", name, schema="core")
