"""The bytes behind mail attachments: core.mail_file.

The message's JSON column describes each attachment; it cannot hold the
bytes, and a mailbox that stores every PDF in JSON is a mailbox that
fills the disk twice over. So the descriptions stay on the message and
the bytes live one row per file, here, in Postgres BYTEA.

Revision: 030
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_mail_files"
down_revision: Union[str, None] = "029_mail_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ("id", sa.Integer(), False, None),
    ("message_id", sa.Integer(), False, None),
    ("filename", sa.String(length=500), False, None),
    ("content_type", sa.String(length=255), True, None),
    ("size", sa.Integer(), False, "0"),
    ("data", sa.LargeBinary(), False, None),
    ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
)

INDEXES = (
    ("ix_mail_file_message", ["message_id"], False),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _table_exists() -> bool:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'core' AND table_name = 'mail_file'"
        )
    ).all()
    return bool(rows)


def upgrade() -> None:
    if not _is_postgres():
        return
    if _table_exists():
        return
    op.create_table(
        "mail_file",
        *[
            sa.Column(
                name,
                type_,
                nullable=nullable,
                server_default=default,
            )
            for name, type_, nullable, default in COLUMNS
        ],
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    for name, columns, unique in INDEXES:
        op.create_index(name, "mail_file", columns, unique=unique, schema="core")


def downgrade() -> None:
    if not _is_postgres():
        return
    if not _table_exists():
        return
    for name, _columns, _unique in reversed(INDEXES):
        op.drop_index(name, table_name="mail_file", schema="core")
    op.drop_table("mail_file", schema="core")
