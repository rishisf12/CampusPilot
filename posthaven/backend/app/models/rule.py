from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text, JSON
import uuid
import enum


class RuleActionType(str, enum.Enum):
    move = "move"
    label = "label"
    mark_read = "mark_read"
    star = "star"
    delete = "delete"
    forward = "forward"
    auto_reply = "auto_reply"
    stop = "stop_processing"


class RuleBase(SQLModel):
    name: str = Field(max_length=200)
    enabled: bool = Field(default=True)
    conditions: str = Field(sa_column=Column(JSON, nullable=False))  # list of {field, operator, value}
    actions: str = Field(sa_column=Column(JSON, nullable=False))  # list of {type, params}
    order: int = Field(default=0)
    stop_on_match: bool = Field(default=False)


class Rule(RuleBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )

    user: "User" = Relationship(back_populates="rules")


class RuleRead(SQLModel):
    id: uuid.UUID
    name: str
    enabled: bool
    conditions: str
    actions: str
    order: int
    stop_on_match: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuleCreate(SQLModel):
    name: str = Field(max_length=200)
    enabled: bool = Field(default=True)
    conditions: str
    actions: str
    order: int = Field(default=0)
    stop_on_match: bool = Field(default=False)


class RuleUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=200)
    enabled: Optional[bool] = None
    conditions: Optional[str] = None
    actions: Optional[str] = None
    order: Optional[int] = None
    stop_on_match: Optional[bool] = None
