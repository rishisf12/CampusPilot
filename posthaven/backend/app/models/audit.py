from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text, Integer
import uuid


class AuditLogBase(SQLModel):
    action: str = Field(max_length=100)
    resource_type: Optional[str] = Field(default=None, max_length=100)
    resource_id: Optional[str] = Field(default=None, max_length=255)
    details: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    ip_address: Optional[str] = Field(default=None, max_length=64)
    user_agent: Optional[str] = Field(default=None, max_length=512)


class AuditLog(AuditLogBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    user: Optional["User"] = Relationship(back_populates="audit_logs")


class AuditLogRead(SQLModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
