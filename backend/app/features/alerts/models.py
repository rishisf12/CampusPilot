"""Alert rules models."""
from __future__ import annotations
from typing import Optional, List, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


class AlertChannel(SQLModel, table=True):
    """Notification channel for alerts."""
    __tablename__ = "alert_channel"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    name: str = Field(max_length=100)
    channel_type: str = Field(max_length=20)  # email, slack, telegram, discord
    config_json: dict = Field(sa_column=Column(postgresql.JSONB(astext_type=str)))
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class AlertRule(SQLModel, table=True):
    """Alert rule definition."""
    __tablename__ = "alert_rule"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    metric: str = Field(max_length=100)  # error_rate, p95_latency, crash_free_rate, etc.
    condition: str = Field(max_length=20)  # gt, lt, gte, lte, eq
    threshold: float = Field()
    window_minutes: int = Field(default=5)
    severity: str = Field(default="warning", max_length=20)  # info, warning, critical
    channels: List[int] = Field(default=[], sa_column=Column(postgresql.JSONB(astext_type=str)))
    cooldown_minutes: int = Field(default=15)
    enabled: bool = Field(default=True)
    created_by: Optional[int] = Field(default=None)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class AlertIncident(SQLModel, table=True):
    """Active or resolved alert incident."""
    __tablename__ = "alert_incident"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    rule_id: int = Field(sa_column=Column(BigInteger, ForeignKey("core.alert_rule.id", ondelete="CASCADE"), nullable=False, index=True))
    status: str = Field(default="firing", max_length=20)  # firing, acknowledged, resolved
    value: float = Field()
    threshold: float = Field()
    started_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    acknowledged_at: Optional[datetime] = Field(default=None)
    acknowledged_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    resolved_at: Optional[datetime] = Field(default=None)
    resolved_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))