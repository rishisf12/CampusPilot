from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text
import uuid


class VacationResponderBase(SQLModel):
    account_id: uuid.UUID = Field(sa_column=Column(ForeignKey("mailaccount.id", ondelete="CASCADE"), nullable=False, index=True))
    enabled: bool = Field(default=False)
    subject: Optional[str] = Field(default=None, max_length=1000)
    body_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    body_html: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    start_date: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    end_date: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    once_per_sender: bool = Field(default=True)


class VacationResponder(VacationResponderBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))

    user: "User" = Relationship(back_populates="vacation_responders")
    account: "MailAccount" = Relationship(back_populates="vacation_responders")

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


class VacationResponderRead(SQLModel):
    id: uuid.UUID
    account_id: uuid.UUID
    enabled: bool
    subject: Optional[str]
    body_text: Optional[str]
    body_html: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    once_per_sender: bool

    model_config = {"from_attributes": True}


class VacationResponderUpsert(SQLModel):
    account_id: uuid.UUID
    enabled: bool = Field(default=False)
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    once_per_sender: bool = Field(default=True)
