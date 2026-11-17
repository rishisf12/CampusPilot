from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, Boolean, Integer, String, Text
import uuid


class UserBase(SQLModel):
    email: str = Field(index=True, unique=True, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=100)
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    email_verified: bool = Field(default=False)


class User(UserBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    password_hash: str = Field(sa_column=Column(Text, nullable=False))
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

    # relationships
    refresh_tokens: list["RefreshToken"] = Relationship(back_populates="user", cascade_delete=True)
    mail_accounts: list["MailAccount"] = Relationship(back_populates="user", cascade_delete=True)
    identities: list["Identity"] = Relationship(back_populates="user", cascade_delete=True)
    folders: list["Folder"] = Relationship(back_populates="user", cascade_delete=True)
    messages: list["Message"] = Relationship(back_populates="user", cascade_delete=True)
    attachments: list["Attachment"] = Relationship(back_populates="user", cascade_delete=True)
    labels: list["Label"] = Relationship(back_populates="user", cascade_delete=True)
    threads: list["Thread"] = Relationship(back_populates="user", cascade_delete=True)
    contacts: list["Contact"] = Relationship(back_populates="user", cascade_delete=True)
    drafts: list["Draft"] = Relationship(back_populates="user", cascade_delete=True)
    scheduled_sends: list["ScheduledSend"] = Relationship(back_populates="user", cascade_delete=True)
    rules: list["Rule"] = Relationship(back_populates="user", cascade_delete=True)
    settings: list["UserSetting"] = Relationship(back_populates="user", cascade_delete=True)
    audit_logs: list["AuditLog"] = Relationship(back_populates="user", cascade_delete=True)
    saved_searches: list["SavedSearch"] = Relationship(back_populates="user", cascade_delete=True)
    snoozes: list["Snooze"] = Relationship(back_populates="user", cascade_delete=True)
    reminders: list["Reminder"] = Relationship(back_populates="user", cascade_delete=True)
    vacation_responders: list["VacationResponder"] = Relationship(back_populates="user", cascade_delete=True)
    templates: list["Template"] = Relationship(back_populates="user", cascade_delete=True)
    contact_groups: list["ContactGroup"] = Relationship(back_populates="user", cascade_delete=True)


class UserRead(SQLModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str] = None
    is_admin: bool
    is_active: bool
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(SQLModel):
    email: str
    display_name: Optional[str] = None
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(SQLModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None


class UserRegisterResponse(SQLModel):
    user: UserRead
    message: str = "Account created successfully"
