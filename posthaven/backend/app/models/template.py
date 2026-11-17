from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text
import uuid


class TemplateBase(SQLModel):
    name: str = Field(max_length=200)
    subject: Optional[str] = Field(default=None, max_length=1000)
    body_html: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    body_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


class Template(TemplateBase, table=True):
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

    user: "User" = Relationship(back_populates="templates")



class TemplateRead(SQLModel):
    id: uuid.UUID
    name: str
    subject: Optional[str]
    body_html: Optional[str]
    body_text: Optional[str]

    model_config = {"from_attributes": True}


class TemplateCreate(SQLModel):
    name: str = Field(max_length=200)
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
