"""The mail app's own table: core.mail_message.

The mail app keeps the message; the feedback feed turns a message into a
feedback row and throws the rest away. So this table carries the mail
itself - sender, subject, body, attachments, the star - and the group it
came from, because the undergraduate and postgraduate mailboxes are
different mail.

Revision: 029
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_mail_messages"
down_revision: Union[str, None] = "028_max_drafts_per_run"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ("id", sa.Integer(), False, None),
    ("message_id", sa.String(length=255), False, None),
    ("group", sa.String(length=16), False, "ug"),
    ("section", sa.String(length=32), False, "other"),
    ("direction", sa.String(length=16), False, "inbox"),
    ("from_email", sa.String(length=255), False, None),
    ("from_name", sa.String(length=255), True, None),
    ("to_email", sa.String(length=255), True, None),
    ("subject", sa.String(length=500), True, None),
    ("body_text", sa.Text(), True, None),
    ("body_html", sa.Text(), True, None),
    ("snippet", sa.String(length=500), True, None),
    ("received_at", sa.DateTime(timezone=True), True, None),
    ("is_read", sa.Boolean(), False, sa.false()),
    ("is_starred", sa.Boolean(), False, sa.false()),
    ("has_attachments", sa.Boolean(), False, sa.false()),
    ("attachments", sa.JSON(), False, None),
    ("labels", sa.JSON(), False, None),
    ("created_by", sa.Integer(), True, None),
    ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
)

INDEXES = (
    ("ix_mail_message_message_id", ["message_id"], True),
    ("ix_mail_message_group", ["group"], False),
    ("ix_mail_message_section", ["section"], False),
    ("ix_mail_message_received_at", ["received_at"], False),
    ("ix_mail_message_created_by", ["created_by"], False),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _existing() -> set:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'core' AND table_name = 'mail_message'"
        )
    ).all()
    return {row[0] for row in rows}


def upgrade() -> None:
    if not _is_postgres():
        return
    if "id" in _existing():
        return
    op.create_table(
        "mail_message",
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
        op.create_index(name, "mail_message", columns, unique=unique, schema="core")
    op.create_index(
        "ix_mail_message_section_received",
        "mail_message",
        ["section", "received_at"],
        schema="core",
    )


def downgrade() -> None:
    if not _is_postgres():
        return
    if "id" not in _existing():
        return
    op.drop_index(
        "ix_mail_message_section_received", table_name="mail_message", schema="core"
    )
    for name, _columns, _unique in reversed(INDEXES):
        op.drop_index(name, table_name="mail_message", schema="core")
    op.drop_table("mail_message", schema="core")
