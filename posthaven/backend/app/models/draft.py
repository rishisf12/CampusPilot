from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text, JSON
import uuid


class DraftBase(SQLModel):
    account_id: uuid.UUID
    identity_id: Optional[uuid.UUID] = Field(default=None, index=True)
    to_json: str = Field(sa_column=Column(JSON, nullable=False))
    cc_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))
    bcc_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))
    subject: str = Field(max_length=1000)
    body_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    body_html: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    reply_to_message_id: Optional[uuid.UUID] = Field(default=None, index=True)


class Draft(DraftBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )

    user: "User" = Relationship(back_populates="drafts")
    account: "MailAccount" = Relationship(back_populates="drafts")


class DraftRead(SQLModel):
    id: uuid.UUID
    account_id: uuid.UUID
    identity_id: Optional[uuid.UUID]
    to_json: str
    cc_json: Optional[str]
    bcc_json: Optional[str]
    subject: str
    body_text: Optional[str]
    body_html: Optional[str]
    updated_at: datetime

    model_config = {"from_attributes": True}


class DraftUpsert(SQLModel):
    account_id: uuid.UUID
    identity_id: Optional[uuid.UUID] = None
    to_json: str
    cc_json: Optional[str] = None
    bcc_json: Optional[str] = None
    subject: str = Field(max_length=1000)
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    reply_to_message_id: Optional[uuid.UUID] = None
