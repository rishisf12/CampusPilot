"""Moderation models."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


class ModerationQueue(SQLModel, table=True):
    __tablename__ = "moderation_queue"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    content_type: str = Field(max_length=50, index=True)  # team, feedback, post, comment
    content_id: int = Field(index=True)
    reporter_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    reason: str = Field(max_length=200)
    details: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    status: str = Field(default="pending", max_length=20, index=True)  # pending, approved, removed, warned
    reviewer_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    reviewed_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    action_taken: Optional[str] = Field(default=None, max_length=50)
    action_reason: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))