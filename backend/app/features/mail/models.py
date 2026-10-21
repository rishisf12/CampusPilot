"""
The mail feature: a section's inbox.

The college runs several notice boards in one place - Academics, the
Placement Cell, the cultural and technical festivals, the sports season -
and until now each of them was a mailing list nobody could read from
inside the app. This is that: the mailbox, filed into the section it
belongs to, with the search, the star and the compose the college
actually uses.

The mailbox is shared, so a message is filed by who wrote it and what they
wrote about (see :func:`classify`). The section ids are the same ones the
student's "Important" navigation uses, so a section is one thing in the
nav and one thing in the inbox.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Index, func
from sqlmodel import Field, JSON, SQLModel


class MailDirection(str, Enum):
    """Which way a message went."""

    INBOX = "inbox"
    SENT = "sent"


class MailMessage(SQLModel, table=True):
    """One message in a section's inbox."""

    __tablename__ = "mail_message"
    __table_args__ = (
        # Named here on purpose: alembic 029 creates these very names, and an
        # index that SQLModel names by default ("ix_<schema>_<table>_<col>")
        # would make the two paths disagree and the downgrade fail.
        Index("ix_mail_message_section_received", "section", "received_at"),
        Index("ix_mail_message_message_id", "message_id", unique=True),
        Index("ix_mail_message_group", "group"),
        Index("ix_mail_message_section", "section"),
        Index("ix_mail_message_received_at", "received_at"),
        Index("ix_mail_message_created_by", "created_by"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The mail's own identifier, so the same message is never filed twice.
    message_id: str = Field(max_length=255)
    #: The mailbox it came from: ug or pg. The college sends the master's and
    #: the undergraduates their own mail, and each group reads only its own.
    group: str = Field(default="ug", max_length=16)
    #: The section it belongs to: academics, placement, cultural, technical,
    #: sports or other.
    section: str = Field(default="other", max_length=32)
    #: inbox or sent.
    direction: str = Field(default=MailDirection.INBOX.value, max_length=16)

    from_email: str = Field(max_length=255)
    from_name: Optional[str] = Field(default=None, max_length=255)
    to_email: Optional[str] = Field(default=None, max_length=255)
    subject: Optional[str] = Field(default=None, max_length=500)
    body_text: Optional[str] = Field(default=None)
    body_html: Optional[str] = Field(default=None)
    #: The first line or two of the body, for the list.
    snippet: Optional[str] = Field(default=None, max_length=500)

    received_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column("received_at", DateTime(timezone=True)),
    )
    is_read: bool = Field(default=False)
    is_starred: bool = Field(default=False)
    has_attachments: bool = Field(default=False)
    #: The attachments, as {filename, content_type, size} - the content
    #: itself is not kept, because a mailbox that stores every PDF is a
    #: mailbox that fills the disk.
    attachments: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    #: Free-form labels the mail carried (Gmail labels, mostly).
    labels: List[str] = Field(default=[], sa_column=Column(JSON))
    #: The account that composed it, for a sent message.
    created_by: Optional[int] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )
