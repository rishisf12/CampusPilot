from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text, JSON, Enum
import uuid
import enum


class SendStatus(str, enum.Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    undone = "undone"


class ScheduledSendBase(SQLModel):
    account_id: uuid.UUID = Field(sa_column=Column(ForeignKey("mailaccount.id", ondelete="CASCADE"), nullable=False, index=True))
    identity_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column(ForeignKey("identity.id", ondelete="SET NULL"), nullable=True, index=True))
    to_json: str = Field(sa_column=Column(JSON, nullable=False))
    cc_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))
    bcc_json: Optional[str] = Field(default=None, sa_column=Column(JSON, nullable=True))
    subject: str = Field(max_length=1000)
    body_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    body_html: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    send_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    status: SendStatus = Field(default=SendStatus.queued, sa_column=Column(Enum(SendStatus), nullable=False, server_default="queued"))
    error_message: Optional[str] = Field(default=None, max_length=1000)
    idempotency_key: str = Field(max_length=255)


class ScheduledSend(ScheduledSendBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    user: "User" = Relationship(back_populates="scheduled_sends")
    account: "MailAccount" = Relationship()


class ScheduledSendRead(SQLModel):
    id: uuid.UUID
    status: SendStatus
    send_at: datetime
    subject: str
    error_message: Optional[str]

    model_config = {"from_attributes": True}
