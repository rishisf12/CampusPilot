"""Broadcast models."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


class Broadcast(SQLModel, table=True):
    __tablename__ = "broadcast"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    title: str = Field(max_length=200)
    body: str = Field(sa_column=Column(postgresql.TEXT))
    channel: str = Field(max_length=20)  # in_app, push, email
    target_roles: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_user_ids: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_branches: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_semesters: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_segments: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    scheduled_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    sent_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    created_by: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class BroadcastDelivery(SQLModel, table=True):
    __tablename__ = "broadcast_delivery"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    broadcast_id: int = Field(sa_column=Column(BigInteger, ForeignKey("core.broadcast.id", ondelete="CASCADE"), nullable=False, index=True))
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False, index=True))
    channel: str = Field(max_length=20)
    status: str = Field(max_length=20)  # pending, sent, failed, read
    sent_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    read_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    error_message: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))