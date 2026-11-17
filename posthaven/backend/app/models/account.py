from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func, String, ForeignKey, Text, Integer, Boolean
import uuid


class MailAccountBase(SQLModel):
    provider: str = Field(max_length=50)  # gmail, outlook, yahoo, fastmail, custom, greenmail
    host: str = Field(max_length=255)
    imap_port: int = Field(default=993)
    smtp_port: int = Field(default=465)
    imap_security: str = Field(default="ssl")  # ssl, starttls, none
    smtp_security: str = Field(default="ssl")
    username: str = Field(max_length=255)
    # password and oauth tokens are ENCRYPTED at rest — never returned by API
    encrypted_password: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    encrypted_oauth_access_token: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    encrypted_oauth_refresh_token: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    is_enabled: bool = Field(default=True)
    sync_enabled: bool = Field(default=True)
    # sync state
    last_sync_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="pending")  # pending, connected, error, disabled
    status_message: Optional[str] = Field(default=None, max_length=500)
    # capability detection results (JSON)
    capabilities: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))  # JSON string
    # special-use folder mapping (JSON)
    special_use: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))  # JSON string


class MailAccount(MailAccountBase, table=True):
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

    user: "User" = Relationship(back_populates="mail_accounts")
    folders: list["Folder"] = Relationship(back_populates="account", cascade_delete=True)
    identities: list["Identity"] = Relationship(back_populates="account", cascade_delete=True)
    messages: list["Message"] = Relationship(back_populates="account", cascade_delete=True)
    vacation_responders: list["VacationResponder"] = Relationship(back_populates="account", cascade_delete=True)


class MailAccountRead(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    host: str
    imap_port: int
    smtp_port: int
    imap_security: str
    smtp_security: str
    username: str
    is_enabled: bool
    sync_enabled: bool
    last_sync_at: Optional[datetime]
    status: str
    status_message: Optional[str]
    capabilities: Optional[str]
    special_use: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MailAccountCreate(SQLModel):
    provider: str = Field(max_length=50)
    host: str = Field(max_length=255)
    imap_port: int = Field(default=993, ge=1, le=65535)
    smtp_port: int = Field(default=465, ge=1, le=65535)
    imap_security: str = Field(default="ssl")
    smtp_security: str = Field(default="ssl")
    username: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=1000)
    is_enabled: bool = Field(default=True)
    sync_enabled: bool = Field(default=True)


class MailAccountUpdate(SQLModel):
    is_enabled: Optional[bool] = None
    sync_enabled: Optional[bool] = None


class MailAccountTestResult(SQLModel):
    ok: bool
    imap_capabilities: Optional[list[str]] = None
    message: str


class IdentityBase(SQLModel):
    email: str = Field(max_length=255)
    name: Optional[str] = Field(default=None, max_length=100)
    signature_html: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    signature_plain: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    is_default: bool = Field(default=False)


class Identity(IdentityBase, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    account_id: uuid.UUID = Field(sa_column=Column(ForeignKey("mailaccount.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    user: "User" = Relationship(back_populates="identities")
    account: "MailAccount" = Relationship(back_populates="identities")


class IdentityRead(SQLModel):
    id: uuid.UUID
    email: str
    name: Optional[str]
    signature_html: Optional[str]
    signature_plain: Optional[str]
    is_default: bool

    model_config = {"from_attributes": True}


class IdentityCreate(SQLModel):
    email: str = Field(max_length=255)
    name: Optional[str] = None
    signature_html: Optional[str] = None
    signature_plain: Optional[str] = None
    is_default: bool = False


class IdentityUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=100)
    signature_html: Optional[str] = None
    signature_plain: Optional[str] = None
    is_default: Optional[bool] = None
