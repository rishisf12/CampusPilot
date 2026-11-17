from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey
import uuid


class RefreshTokenBase(SQLModel):
    token_hash: str = Field(index=True, unique=True, max_length=512)
    expires_at: datetime
    revoked: bool = Field(default=False)
    replaced_by_token_hash: Optional[str] = Field(default=None, max_length=512)


class RefreshToken(RefreshTokenBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    user: "User" = Relationship(back_populates="refresh_tokens")


class RefreshTokenCreate(SQLModel):
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime


class TokenPair(SQLModel):
    access_token: str
    refresh_token: str  # raw, returned only at login/refresh
    token_type: str = "bearer"
    expires_in: int  # seconds
