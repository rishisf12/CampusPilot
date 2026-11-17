from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text, Integer
import uuid


class ContactBase(SQLModel):
    name: Optional[str] = Field(default=None, max_length=200)
    email: str = Field(max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    company: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    group_id: Optional[uuid.UUID] = Field(default=None, index=True)


class Contact(ContactBase, table=True):
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

    user: "User" = Relationship(back_populates="contacts")
    group: Optional["ContactGroup"] = Relationship(back_populates="members")


class ContactRead(SQLModel):
    id: uuid.UUID
    name: Optional[str]
    email: str
    phone: Optional[str]
    company: Optional[str]
    notes: Optional[str]
    avatar_url: Optional[str]
    group_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactCreate(SQLModel):
    name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    group_id: Optional[uuid.UUID] = None


class ContactUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    company: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    group_id: Optional[uuid.UUID] = None


class ContactGroupBase(SQLModel):
    name: str = Field(max_length=200)


class ContactGroup(ContactGroupBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    user: "User" = Relationship(back_populates="contact_groups")
    members: list["Contact"] = Relationship(back_populates="group")


class ContactGroupRead(SQLModel):
    id: uuid.UUID
    name: str
    member_count: int = 0

    model_config = {"from_attributes": True}


class ContactGroupCreate(SQLModel):
    name: str = Field(max_length=200)
