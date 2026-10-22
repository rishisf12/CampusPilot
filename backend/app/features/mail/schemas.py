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
    #: The cluster that filed it, when a cluster did. A message from a
    #: sender nobody registered has none and waits in the unassigned state.
    cluster_id: Optional[int] = None
    cluster_name: Optional[str] = None
    #: The conversation it belongs to, so a thread stays in one place.
    thread_id: Optional[str] = None
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
    is_important: bool = False
    is_archived: bool = False
    is_trashed: bool = False
    is_quarantined: bool = False
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


class MailSenderRuleCreateRequest(BaseModel):
    """A sender email id (or domain or pattern) registered under one section."""

    group: str
    pattern: str
    section: str
    #: The cluster the sender joins, when there is one.
    cluster_id: Optional[int] = None


class MailSenderRuleResponse(BaseModel):
    """One registered sender rule, as the admin panel lists it."""

    id: int
    group: str
    group_label: str
    pattern: str
    kind: str = "exact"
    section: str
    section_label: str
    cluster_id: Optional[int] = None
    cluster_name: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class MailClusterCreateRequest(BaseModel):
    """A cluster of sender ids to register under one section."""

    group: str
    name: str
    section: str
    description: Optional[str] = None
    #: The sender ids, one per line or comma separated. A whole list may
    #: be pasted at once - that is how a cluster is built.
    members: List[str] = Field(default_factory=list)


class MailClusterUpdateRequest(BaseModel):
    """A cluster, renamed or moved to another section."""

    name: Optional[str] = None
    section: Optional[str] = None
    description: Optional[str] = None


class MailClusterMembersRequest(BaseModel):
    """Senders to add to a cluster."""

    members: List[str] = Field(default_factory=list)


class MailClusterResponse(BaseModel):
    """One cluster, with the senders registered in it."""

    id: int
    group: str
    group_label: str
    name: str
    section: str
    section_label: str
    description: Optional[str] = None
    members: List[MailSenderRuleResponse] = Field(default_factory=list)
    #: How much mail the cluster has filed.
    message_count: int = 0
    created_at: Optional[datetime] = None


class MailSenderAssignRequest(BaseModel):
    """
    A sender nobody registered, put into a cluster.

    This is the admin's answer to the worklist: the sender is registered
    and every message it wrote is filed at once.
    """

    group: str
    from_email: str
    #: The cluster to put the sender in. Without one, the sender is
    #: registered as a loose rule under the section given.
    cluster_id: Optional[int] = None
    section: Optional[str] = None


class MailUnknownSender(BaseModel):
    """A sender nobody registered, with how much mail it wrote."""

    from_email: str
    from_name: Optional[str] = None
    count: int = 0
    unread: int = 0
    last_seen: Optional[datetime] = None
    #: The section the words in its mail point at - a suggestion only.
    suggested_section: str = "other"
    suggested_section_label: str = "Other"


class MailMoveRequest(BaseModel):
    """A message moved to another section by hand."""

    section: Optional[str] = None
    cluster_id: Optional[int] = None


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
    #: The clusters that filed the mail, for the admin screen.
    clusters: List[MailClusterResponse] = Field(default_factory=list)


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
