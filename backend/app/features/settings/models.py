"""Per-user settings storage.

One row per user holding their settings as a JSON object. A column per setting
would mean a migration for every new switch, and the set of settings is owned by
the frontend registry - the server does not know the key names in advance, so it
stores what it is given rather than rejecting keys it has not seen.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, ForeignKey, Integer, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel


class UserSettings(SQLModel, table=True):
    """A user's saved settings, or absent if they have changed none."""

    __tablename__ = "user_settings"
    __table_args__ = {"schema": "core", "extend_existing": True}

    user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("core.user.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    #: Setting key -> value. The frontend registry owns the keys and their types;
    #: the server stores them verbatim and validates nothing about them.
    values: Any = Field(
        default_factory=dict,
        sa_column=Column(
            postgresql.JSONB(astext_type=text),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
        ),
    )