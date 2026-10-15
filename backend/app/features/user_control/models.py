"""User control models."""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey, func
from sqlalchemy.dialects import postgresql


class UserControlAction(SQLModel, table=True):
    """Record of admin actions on users: suspend, ban, force_logout, etc."""
    __tablename__ = "user_control_action"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    admin_id: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False, index=True))
    target_user_id: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False, index=True))
    action: str = Field(max_length=50)  # suspend, ban, force_logout, revoke_tokens, reset_verification, impersonate_start, impersonate_end
    reason: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    # server_default=func.now(), not the string "CURRENT_TIMESTAMP": Postgres
    # would try to cast that literal as a timestamptz value and reject the
    # whole CREATE TABLE.
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))