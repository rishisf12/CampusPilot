from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Integer
import uuid


class LabelBase(SQLModel):
    name: str = Field(max_length=100)
    color: str = Field(default="#6b7280", max_length=20)  # hex


class Label(LabelBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    user: "User" = Relationship(back_populates="labels")
    message_links: list["MessageLabel"] = Relationship(back_populates="label", cascade_delete=True)


class MessageLabelBase(SQLModel):
    message_id: uuid.UUID = Field(sa_column=Column(ForeignKey("message.id", ondelete="CASCADE"), nullable=False, index=True))
    label_id: uuid.UUID = Field(sa_column=Column(ForeignKey("label.id", ondelete="CASCADE"), nullable=False, index=True))


class MessageLabel(MessageLabelBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    message: "Message" = Relationship(back_populates="labels")
    label: "Label" = Relationship(back_populates="message_links")

    __table_args__ = (
        # unique (message_id, label_id)
    )


class LabelRead(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    color: str

    model_config = {"from_attributes": True}
