from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey
import uuid


class ReminderBase(SQLModel):
    message_id: uuid.UUID
    due_at: datetime
    fired: bool = Field(default=False)


class Reminder(ReminderBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))

    user: "User" = Relationship(back_populates="reminders")
    message: "Message" = Relationship(back_populates="reminders")

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )


class ReminderRead(SQLModel):
    id: uuid.UUID
    message_id: uuid.UUID
    due_at: datetime
    fired: bool

    model_config = {"from_attributes": True}


class ReminderCreate(SQLModel):
    message_id: uuid.UUID
    due_at: datetime
