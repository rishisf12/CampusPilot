from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Integer
import uuid


class FolderBase(SQLModel):
    account_id: uuid.UUID = Field(sa_column=Column(ForeignKey("mailaccount.id", ondelete="CASCADE"), nullable=False, index=True))
    name: str = Field(max_length=255)
    delimiter: Optional[str] = Field(default=None, max_length=10)
    parent_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column(ForeignKey("folder.id", ondelete="SET NULL"), nullable=True, index=True))
    special_use: Optional[str] = Field(default=None, max_length=50)  # \Inbox, \Sent, \Drafts, \Trash, \Junk, \Archive
    subscribed: bool = Field(default=True)
    # IMAP state
    uidvalidity: Optional[str] = Field(default=None, max_length=64)
    uidnext: Optional[int] = Field(default=None)
    highestmodseq: Optional[int] = Field(default=None)
    # cached counts
    message_count: int = Field(default=0)
    unread_count: int = Field(default=0)
    # synced flag
    synced: bool = Field(default=False)


class Folder(FolderBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )

    user: "User" = Relationship(back_populates="folders")
    account: "MailAccount" = Relationship(back_populates="folders")
    messages: list["Message"] = Relationship(back_populates="folder", cascade_delete=True)


class FolderRead(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    name: str
    delimiter: Optional[str]
    parent_id: Optional[uuid.UUID]
    special_use: Optional[str]
    subscribed: bool
    uidvalidity: Optional[str]
    uidnext: Optional[int]
    highestmodseq: Optional[int]
    message_count: int
    unread_count: int
    synced: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FolderCreate(SQLModel):
    account_id: uuid.UUID
    name: str = Field(max_length=255)
    delimiter: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    special_use: Optional[str] = None
    subscribed: bool = Field(default=True)


class FolderUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=255)
    subscribed: Optional[bool] = None
    special_use: Optional[str] = None
