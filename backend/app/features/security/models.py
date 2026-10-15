"""Security events models."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


class SecurityEvent(SQLModel, table=True):
    __tablename__ = "security_event"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    event_type: str = Field(max_length=50, index=True)  # failed_login, brute_force, new_admin, role_change, unusual_ip, rate_limit
    severity: str = Field(max_length=20)  # low, medium, high, critical
    actor_email: Optional[str] = Field(default=None, max_length=255)
    actor_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id"), index=True))
    details: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    ip_hash: Optional[str] = Field(default=None, max_length=64)
    user_agent_hash: Optional[str] = Field(default=None, max_length=64)
    request_id: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class SecurityFeed(SQLModel, table=True):
    """Aggregated security feed for dashboard."""
    __tablename__ = "security_feed"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    event_type: str = Field(max_length=50, index=True)
    severity: str = Field(max_length=20)
    count: int = Field(default=1)
    first_seen: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False))
    last_seen: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False))
    affected_users: List[str] = Field(default=[], sa_column=Column(postgresql.JSONB(astext_type=str)))
    status: str = Field(default="new", max_length=20)  # new, investigating, resolved, ignored
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))