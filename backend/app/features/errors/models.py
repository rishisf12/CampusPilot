"""Error tracking models."""
from __future__ import annotations
from typing import Optional, List, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


class ErrorFingerprint(SQLModel, table=True):
    """Grouped error by fingerprint."""
    __tablename__ = "error_fingerprint"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    fingerprint: str = Field(max_length=64, unique=True, index=True)
    error_type: str = Field(max_length=100, index=True)
    message: str = Field(max_length=500)
    stack_trace_hash: str = Field(max_length=64)
    first_seen: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    last_seen: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    count: int = Field(default=1)
    status: str = Field(default="new", max_length=20)  # new, investigating, resolved, ignored
    assignee_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    affected_users: int = Field(default=1)
    affected_releases: List[str] = Field(default=[], sa_column=Column(postgresql.JSONB(astext_type=str)))


class ErrorEvent(SQLModel, table=True):
    """Individual error occurrence."""
    __tablename__ = "error_event"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    fingerprint_id: int = Field(sa_column=Column(BigInteger, ForeignKey("core.error_fingerprint.id", ondelete="CASCADE"), nullable=False, index=True))
    request_id: Optional[str] = Field(default=None, max_length=64)
    user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id"), index=True))
    platform: str = Field(max_length=20)
    app_version: Optional[str] = Field(default=None, max_length=50)
    url: Optional[str] = Field(default=None, max_length=500)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    stack_trace: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    context_json: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))