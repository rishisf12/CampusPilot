from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Integer, Boolean, Text, JSON, Index
import uuid


class MessageBase(SQLModel):
    account_id: uuid.UUID
    folder_id: uuid.UUID
    thread_id: Optional[uuid.UUID] = Field(default=None, index=True)
    uid: int
    message_id: Optional[str] = Field(default=None, max_length=512)
    in_reply_to: Optional[str] = Field(default=None, max_length=512)
    references: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    from_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))  # {name, address}
    to_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))
    cc_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))
    bcc_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))
    subject: Optional[str] = Field(default=None, max_length=1000)
    snippet: Optional[str] = Field(default=None, max_length=2000)
    body_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    body_html: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    search_vector: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))  # tsvector (PG)
    flags: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))  # [\Seen, \Flagged, ...]
    size: int = Field(default=0)
    has_attachments: bool = Field(default=False)
    internal_date: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    received_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class Message(MessageBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))

    user: "User" = Relationship(back_populates="messages")
    account: "MailAccount" = Relationship(back_populates="messages")
    folder: "Folder" = Relationship(back_populates="messages")
    thread: Optional["Thread"] = Relationship(back_populates="messages")
    attachments: list["Attachment"] = Relationship(back_populates="message", cascade_delete=True)
    labels: list["MessageLabel"] = Relationship(back_populates="message", cascade_delete=True)
    snoozes: list["Snooze"] = Relationship(back_populates="message", cascade_delete=True)
    reminders: list["Reminder"] = Relationship(back_populates="message", cascade_delete=True)

    __table_args__ = (
        Index("ix_message_account_folder_received", "account_id", "folder_id", "received_at"),
        Index("ix_message_uid_unique", "account_id", "folder_id", "uid", unique=True),
        Index("ix_message_search_vector", "search_vector", postgresql_using="gin"),
    )


class MessageRead(SQLModel):
    id: uuid.UUID
    account_id: uuid.UUID
    folder_id: uuid.UUID
    thread_id: Optional[uuid.UUID]
    uid: int
    message_id: Optional[str]
    in_reply_to: Optional[str]
    references: Optional[str]
    from_json: Optional[str]
    to_json: Optional[str]
    cc_json: Optional[str]
    bcc_json: Optional[str]
    subject: Optional[str]
    snippet: Optional[str]
    body_text: Optional[str]
    body_html: Optional[str]
    flags: Optional[str]
    size: int
    has_attachments: bool
    internal_date: Optional[datetime]
    received_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MessageListItem(SQLModel):
    id: uuid.UUID
    thread_id: Optional[uuid.UUID]
    uid: int
    message_id: Optional[str]
    from_json: Optional[str]
    to_json: Optional[str]
    subject: Optional[str]
    snippet: Optional[str]
    flags: Optional[str]
    size: int
    has_attachments: bool
    internal_date: Optional[datetime]
    received_at: Optional[datetime]

    model_config = {"from_attributes": True}
