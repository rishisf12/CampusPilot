"""Analytics models."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


class AnalyticsEvent(SQLModel, table=True):
    """Raw analytics event."""
    __tablename__ = "analytics_event"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    event_name: str = Field(max_length=100, index=True)
    user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id"), index=True))
    session_id: Optional[str] = Field(default=None, max_length=64, index=True)
    platform: str = Field(max_length=20)
    app_version: Optional[str] = Field(default=None, max_length=50)
    properties_json: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class AnalyticsDailyAggregate(SQLModel, table=True):
    """Pre-aggregated daily metrics."""
    __tablename__ = "analytics_daily_aggregate"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    date: datetime = Field(sa_column=Column(postgresql.DATE, nullable=False, index=True))
    metric_name: str = Field(max_length=100, index=True)
    dimension: Optional[str] = Field(default=None, max_length=100, index=True)
    dimension_value: Optional[str] = Field(default=None, max_length=200, index=True)
    count: int = Field(default=0)
    unique_users: int = Field(default=0)
    sum_value: float = Field(default=0.0)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class AnalyticsSegment(SQLModel, table=True):
    """Saved user segments."""
    __tablename__ = "analytics_segment"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    name: str = Field(max_length=200, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    criteria_json: dict = Field(sa_column=Column(postgresql.JSONB(astext_type=str)))
    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class AnalyticsFunnel(SQLModel, table=True):
    """Funnel definition."""
    __tablename__ = "analytics_funnel"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    name: str = Field(max_length=200, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    steps_json: List[str] = Field(sa_column=Column(postgresql.JSONB(astext_type=str)))
    window_hours: int = Field(default=24)
    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class AnalyticsAnomaly(SQLModel, table=True):
    """Detected anomalies."""
    __tablename__ = "analytics_anomaly"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    metric_name: str = Field(max_length=100, index=True)
    dimension: Optional[str] = Field(default=None, max_length=100, index=True)
    dimension_value: Optional[str] = Field(default=None, max_length=200, index=True)
    expected_value: float = Field()
    actual_value: float = Field()
    deviation_pct: float = Field()
    severity: str = Field(max_length=20)  # warning, critical
    description: str = Field(max_length=500)
    status: str = Field(default="new", max_length=20)  # new, acknowledged, resolved
    detected_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    acknowledged_at: Optional[datetime] = Field(default=None)
    acknowledged_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))