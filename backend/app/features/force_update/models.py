"""Force/Soft update models."""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


class ForceUpdateRule(SQLModel, table=True):
    __tablename__ = "force_update_rule"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    platform: str = Field(max_length=20, index=True)  # ios, android, web
    min_version: str = Field(max_length=20)  # minimum required version
    recommended_version: str = Field(max_length=20)  # recommended version
    store_url: str = Field(max_length=500)  # app store / play store URL
    message: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    is_active: bool = Field(default=True)
    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))