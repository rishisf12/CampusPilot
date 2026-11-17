from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Integer
import uuid


class AttachmentBase(SQLModel):
    message_id: uuid.UUID = Field(sa_column=Column(ForeignKey("message.id", ondelete="CASCADE"), nullable=False, index=True))
    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=255)
    size: int = Field(default=0)
    content_id: Optional[str] = Field(default=None, max_length=512)  # for inline images (cid:)
    is_inline: bool = Field(default=False)
    # object storage path or local path (not the raw bytes)
    storage_path: str = Field(max_length=1024)


class Attachment(AttachmentBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))

    user: "User" = Relationship(back_populates="attachments")
    message: "Message" = Relationship(back_populates="attachments")

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )


class AttachmentRead(SQLModel):
    id: uuid.UUID
    message_id: uuid.UUID
    filename: str
    mime_type: str
    size: int
    content_id: Optional[str]
    is_inline: bool

    model_config = {"from_attributes": True}
