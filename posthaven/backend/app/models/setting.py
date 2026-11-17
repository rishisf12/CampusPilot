from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text
import uuid


class UserSettingBase(SQLModel):
    key: str = Field(max_length=100)
    value: str = Field(sa_column=Column(Text, nullable=False))


class UserSetting(UserSettingBase, table=True):
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

    user: "User" = Relationship(back_populates="settings")

    __table_args__ = (
        # unique (user_id, key)
    )


class UserSettingRead(SQLModel):
    id: uuid.UUID
    key: str
    value: str

    model_config = {"from_attributes": True}


class UserSettingUpsert(SQLModel):
    key: str = Field(max_length=100)
    value: str
