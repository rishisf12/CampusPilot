from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey
import uuid


class ThreadBase(SQLModel):
    account_id: uuid.UUID
    subject: Optional[str] = Field(default=None, max_length=1000)
    message_count: int = Field(default=0)
    unread_count: int = Field(default=0)
    last_message_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class Thread(ThreadBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))

    user: "User" = Relationship(back_populates="messages")
    messages: list["Message"] = Relationship(back_populates="thread")


class ThreadRead(SQLModel):
    id: uuid.UUID
    account_id: uuid.UUID
    subject: Optional[str]
    message_count: int
    unread_count: int
    last_message_at: Optional[datetime]

    model_config = {"from_attributes": True}
