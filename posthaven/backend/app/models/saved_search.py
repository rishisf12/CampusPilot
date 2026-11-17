from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text
import uuid


class SavedSearchBase(SQLModel):
    name: str = Field(max_length=200)
    query: str = Field(sa_column=Column(Text, nullable=False))


class SavedSearch(SavedSearchBase, table=True):
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

    user: "User" = Relationship(back_populates="saved_searches")


class SavedSearchRead(SQLModel):
    id: uuid.UUID
    name: str
    query: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SavedSearchCreate(SQLModel):
    name: str = Field(max_length=200)
    query: str
