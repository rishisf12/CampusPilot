"""Health check models."""
from __future__ import annotations
from typing import Optional, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


class HealthCheck(SQLModel, table=True):
    """Health check result for a component."""
    __tablename__ = "health_check"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    component: str = Field(max_length=100, index=True)
    status: str = Field(max_length=20)  # healthy, warning, critical, unknown
    message: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    details_json: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    latency_ms: Optional[float] = Field(default=None)
    checked_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class HealthHistory(SQLModel, table=True):
    """Historical health checks for trends."""
    __tablename__ = "health_history"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    component: str = Field(max_length=100, index=True)
    status: str = Field(max_length=20)
    latency_ms: Optional[float] = Field(default=None)
    checked_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))