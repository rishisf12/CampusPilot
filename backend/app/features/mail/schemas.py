"""Request and response shapes for the mail feature."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MailAttachment(BaseModel):
    """One attachment, described but not carried."""

    filename: str
    content_type: Optional[str] = None
    size: Optional[int] = None
    #: Set when the file's bytes are stored (see core.mail_file): the id a
    #: download endpoint asks for. A metadata-only entry has none.
    id: Optional[int] = None


class MailMessageResponse(BaseModel):
    """A message, as the list and the reading pane show it."""

    id: int
    message_id: str
    group: str
    group_label: str
    section: str
    section_label: str
    direction: str
    from_email: str
    from_name: Optional[str] = None
    to_email: Optional[str] = None
    subject: Optional[str] = None
    snippet: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    received_at: Optional[datetime] = None
    is_read: bool = False
    is_starred: bool = False
    has_attachments: bool = False
    attachments: List[MailAttachment] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)


class MailFileInfo(BaseModel):
    """One attachment as the Files (Downloads) view shows it."""

    id: int
    message_id: int
    filename: str
    content_type: Optional[str] = None
    size: int = 0
    section: str
    group: str
    from_email: str
    from_name: Optional[str] = None
    subject: Optional[str] = None
    received_at: Optional[datetime] = None


class MailListResponse(BaseModel):
    """A page of messages, and the counts the navigation shows."""

    total: int
    page: int
    size: int
    messages: List[MailMessageResponse]
    groups: List[Dict[str, Any]] = Field(default_factory=list)
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    unread: Dict[str, int] = Field(default_factory=dict)
    starred_count: int = 0


class MailComposeRequest(BaseModel):
    """A message to send, or a reply or forward of one already in the inbox."""

    to: str = ""
    subject: str = ""
    body: str = ""
    section: Optional[str] = None
    #: The message this one replies to: its sender becomes the recipient and
    #: the subject gains "Re:" unless it is already there.
    reply_of: Optional[int] = None
    #: The message this one forwards on: the recipient stays as given and the
    #: subject gains "Fwd:"; the original's body rides along quoted.
    forward_of: Optional[int] = None


class MailIngestRequest(BaseModel):
    """A message arriving from the mailbox (the poller posts this)."""

    from_email: str
    from_name: Optional[str] = None
    to: Optional[str] = None
    subject: Optional[str] = None
    text: Optional[str] = None
    html: Optional[str] = None
    message_id: Optional[str] = None
    date: Optional[datetime] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
