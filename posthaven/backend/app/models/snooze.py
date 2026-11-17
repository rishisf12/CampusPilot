from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey
import uuid


class SnoozeBase(SQLModel):
    message_id: uuid.UUID
    wake_at: datetime
    woke: bool = Field(default=False)


class Snooze(SnoozeBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))

    user: "User" = Relationship(back_populates="snoozes")
    message: "Message" = Relationship(back_populates="snoozes")

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )


class SnoozeRead(SQLModel):
    id: uuid.UUID
    message_id: uuid.UUID
    wake_at: datetime
    woke: bool

    model_config = {"from_attributes": True}


class SnoozeCreate(SQLModel):
    message_id: uuid.UUID
    wake_at: datetime
