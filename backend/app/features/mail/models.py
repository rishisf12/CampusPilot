"""
The mail feature: a sender-routed college webmail.

The college runs several notice boards in one place - Academics, the
Placement Cell, the cultural and technical festivals, the sports season -
and until now each of them was a mailing list nobody could read from
inside the app. This is that: the mailbox, filed into the section its
sender belongs to, with the search, the star and the compose the college
actually uses.

A section is not a receiving address. Six receiving ids
(ug-placement@, registrar@, ug-cultural@, ug-technical@, ug-sports@,
ug-other@iiitdmj.ac.in) are aliases of ONE common intake; the address a
notice came through is stored (intake_address) and shown, but it never
decides the section. The section comes from who wrote the notice: the
college registers clusters of sender email ids per section, and mail from
a registered sender files there no matter which alias it was posted to.
A sender nobody registered waits in the unassigned state until an admin
puts it in a cluster.

The mailbox is shared, so a message is filed by who wrote it (see
:func:`features.mail.sections.classify` for the admin's filing hint).
The section ids are the same ones the student's "Important" navigation
uses, so a section is one thing in the nav and one thing in the inbox.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Index, Integer, LargeBinary, func
from sqlmodel import Field, JSON, SQLModel


class MailDirection(str, Enum):
    """Which way a message went."""

    INBOX = "inbox"
    SENT = "sent"


class MailSection(SQLModel, table=True):
    """
    One of the sections a group's mail is filed under.

    The sections are rows rather than a constant because the admin console
    edits them, and the navigation reads the same table: a section is one
    thing in the nav and one thing in the mailbox.
    """

    __tablename__ = "mail_section"
    __table_args__ = (
        # One section per key per group.
        Index("uq_mail_section_group_key", "group", "key", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The bundle the section belongs to: ug or pg.
    group: str = Field(default="ug", max_length=16)
    #: The section id, the one the navigation uses: academics, placement...
    key: str = Field(max_length=32)
    #: The label the students see.
    label: str = Field(max_length=64)
    #: What the section is for, shown on the admin screen.
    description: Optional[str] = Field(default=None, max_length=255)
    #: The order the sections are listed in.
    sort_order: int = Field(default=0)
    #: Whether students may read the section's mail.
    is_public: bool = Field(default=True)
    #: The administrator who created it, for the audit trail.
    created_by: Optional[int] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailSectionAccess(SQLModel, table=True):
    """
    Who may read a section, and who may moderate it.

    This is the "section admin" of the product: the same person may
    moderate the placement section and only read the academics one. A
    student with no row here reads the public sections, and nobody else.
    """

    __tablename__ = "mail_section_access"
    __table_args__ = (
        # One grant per account per section.
        Index(
            "uq_mail_section_access_user_section", "user_id", "section_id", unique=True
        ),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The account the grant is for.
    user_id: int = Field(index=False)
    #: The section the grant is about.
    section_id: int = Field(index=False)
    #: Whether the account may read the section's mail.
    can_read: bool = Field(default=True)
    #: Whether the account may moderate the section: its clusters, its mail.
    can_manage: bool = Field(default=False)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailThread(SQLModel, table=True):
    """
    A conversation.

    A notice and the answer to it are two messages and one thread, so the
    reading pane can show the exchange together the way a mail app does.
    """

    __tablename__ = "mail_thread"
    __table_args__ = (
        Index("ix_mail_thread_group_last", "group", "last_message_at"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The bundle the thread belongs to.
    group: str = Field(default="ug", max_length=16)
    #: The normalised subject the thread is about.
    subject_key: str = Field(max_length=255)
    #: The subject as it was first written.
    subject: Optional[str] = Field(default=None, max_length=500)
    #: How many messages the thread holds.
    message_count: int = Field(default=0)
    #: When the last message arrived.
    last_message_at: Optional[datetime] = Field(
        default=None, sa_column=Column("last_message_at", DateTime(timezone=True))
    )

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailLabel(SQLModel, table=True):
    """
    A label an account puts on its own mail.

    Labels are not folders: a message carries several of them, and they
    may be nested and coloured. The college's sections are folders, not
    labels - the sections are where a message is filed.
    """

    __tablename__ = "mail_label"
    __table_args__ = (
        # One label per name per account.
        Index("uq_mail_label_user_name", "user_id", "name", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The account the label belongs to.
    user_id: int = Field(index=False)
    #: The label's name.
    name: str = Field(max_length=64)
    #: The colour it is shown in.
    color: str = Field(default="cp-accent", max_length=32)
    #: The label this one sits under, for a nested list.
    parent_id: Optional[int] = Field(default=None)
    #: Whether the label is one of the app's own.
    is_system: bool = Field(default=False)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailMessageLabel(SQLModel, table=True):
    """One label on one message."""

    __tablename__ = "mail_message_label"
    __table_args__ = (
        Index("uq_mail_message_label", "message_id", "label_id", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The message the label is on.
    message_id: int = Field(index=False)
    #: The label it is.
    label_id: int = Field(index=False)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailUserMessageState(SQLModel, table=True):
    """
    What one account has done with one message.

    Read, starred, important, archived, trashed and snoozed are per
    account, not per message: one student may have read a notice that
    another has not.
    """

    __tablename__ = "mail_user_message_state"
    __table_args__ = (
        # One state row per account per message.
        Index(
            "uq_mail_user_message_state_user_message",
            "user_id",
            "message_id",
            unique=True,
        ),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The account the state belongs to.
    user_id: int = Field(index=False)
    #: The message it is about.
    message_id: int = Field(index=False)
    is_read: bool = Field(default=False)
    is_starred: bool = Field(default=False)
    is_important: bool = Field(default=False)
    is_archived: bool = Field(default=False)
    is_trashed: bool = Field(default=False)
    #: When a snoozed message comes back.
    snoozed_until: Optional[datetime] = Field(
        default=None, sa_column=Column("snoozed_until", DateTime(timezone=True))
    )

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailCluster(SQLModel, table=True):
    """
    A named cluster of sender email ids, filed under one section.

    This is what the college registers: "the Placement Cell writes to us
    from these addresses" - one cluster per section, or several when one
    section has more than one office writing to it. A cluster holds many
    sender ids; each of them is a row in :class:`MailSenderRule` pointing
    back here.

    A cluster is the only thing that files mail. A message from a sender
    no cluster names waits in the unassigned state until an admin puts the
    sender in a cluster.
    """

    __tablename__ = "mail_cluster"
    __table_args__ = (
        # One cluster per name per group: "Placement Cell" is one cluster,
        # not two with the same name.
        Index("uq_mail_cluster_group_name", "group", "name", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The bundle the cluster files into: ug or pg.
    group: str = Field(default="ug", max_length=16)
    #: The cluster's name, as the admin wrote it.
    name: str = Field(max_length=120)
    #: The section mail from this cluster is filed under.
    section: str = Field(default="other", max_length=32)
    #: A note about the cluster, shown on the admin screen.
    description: Optional[str] = Field(default=None, max_length=500)
    #: The administrator who registered it, for the audit trail.
    created_by: Optional[int] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailSenderRule(SQLModel, table=True):
    """
    The senders a section is written by.

    A section is defined by who writes to it, not by which mailbox id the
    notice lands in. The college registers the sender email ids each
    section's mail comes from - a cluster of them per section - and a
    message from one of those is filed there no matter which receiving
    address it was sent to. A rule holds either one sender's full address
    (``tnp@iiitdmj.ac.in``) or everyone on a domain (``@iiitdmj.ac.in``)
    or a pattern (``notice-*@iiitdmj.ac.in``).

    A rule without a cluster is a loose registration: it still files mail,
    it just has no name on the admin screen.
    """

    __tablename__ = "mail_sender_rule"
    __table_args__ = (
        # One rule per group and sender: the same id registered twice is
        # the same cluster, so the second POST is a lookup, not a copy.
        Index("uq_mail_sender_rule_group_pattern", "group", "pattern", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The bundle the rule files into: ug or pg.
    group: str = Field(default="ug", max_length=16)
    #: The sender email id, or ``@domain``/pattern for several senders.
    pattern: str = Field(max_length=255)
    #: exact, domain or pattern: what the pattern names.
    kind: str = Field(default="exact", max_length=16)
    #: The section mail from this sender is filed under.
    section: str = Field(default="other", max_length=32)
    #: The cluster this sender belongs to, when it is registered in one.
    cluster_id: Optional[int] = Field(default=None)
    #: Higher wins when two rules of the same kind match; the older rule
    #: wins a tie, so the first registration is the stable one.
    priority: int = Field(default=0)
    #: A disabled rule never matches and never routes.
    is_active: bool = Field(default=True)
    #: Why the rule exists, in the admin's words.
    notes: Optional[str] = Field(default=None, max_length=500)
    #: The administrator who registered it, for the audit trail.
    created_by: Optional[int] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailMessage(SQLModel, table=True):
    """One message in a section's inbox."""

    __tablename__ = "mail_message"
    __table_args__ = (
        Index("ix_mail_message_message_id", "message_id", unique=True),
        Index("ix_mail_message_group", "group"),
        Index("ix_mail_message_section", "section"),
        Index("ix_mail_message_received_at", "received_at"),
        Index("ix_mail_message_created_by", "created_by"),
        Index("ix_mail_message_from_email", "from_email"),
        Index(
            "ix_mail_message_group_section_received",
            "group",
            "section",
            "received_at",
        ),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The mail's own identifier, so the same message is never filed twice.
    message_id: str = Field(max_length=255)
    #: The mailbox it came from: ug or pg. The college sends the master's and
    #: the undergraduates their own mail, and each group reads only its own.
    group: str = Field(default="ug", max_length=16)
    #: The section it belongs to: academics, placement, cultural, technical,
    #: sports or other - or "unassigned", when the sender is not registered.
    section: str = Field(default="other", max_length=32)
    #: The cluster that filed it, when a cluster did.
    cluster_id: Optional[int] = Field(default=None)
    #: The conversation it belongs to, so a thread stays in one place.
    thread_id: Optional[str] = Field(default=None, max_length=255)
    #: inbox or sent.
    direction: str = Field(default=MailDirection.INBOX.value, max_length=16)
    #: Archived and trashed are the two piles a mail app keeps out of sight.
    is_archived: bool = Field(default=False)
    is_trashed: bool = Field(default=False)
    is_read: bool = Field(default=False)
    is_starred: bool = Field(default=False)
    is_important: bool = Field(default=False)
    is_quarantined: bool = Field(default=False)

    from_email: str = Field(max_length=255)
    from_name: Optional[str] = Field(default=None, max_length=255)
    to_email: Optional[str] = Field(default=None, max_length=255)
    #: The full recipient lists, the way a mail app shows them.
    to_emails: List[str] = Field(default=[], sa_column=Column(JSON))
    cc_emails: List[str] = Field(default=[], sa_column=Column(JSON))
    bcc_emails: List[str] = Field(default=[], sa_column=Column(JSON))
    reply_to: Optional[str] = Field(default=None, max_length=255)
    reply_to_name: Optional[str] = Field(default=None, max_length=255)
    in_reply_to: Optional[str] = Field(default=None, max_length=255)
    references: Optional[str] = Field(default=None, max_length=500)
    subject: Optional[str] = Field(default=None, max_length=500)
    body_text: Optional[str] = Field(default=None)
    body_html: Optional[str] = Field(default=None)
    #: The first line or two of the body, for the list.
    snippet: Optional[str] = Field(default=None, max_length=500)
    #: Which of the intake addresses the mail came through. It says which
    #: door the mail came in by; it never decides the section.
    intake_address: Optional[str] = Field(default=None, max_length=255)
    #: When the message arrived, as stamped by the sender's mail server.
    received_at: Optional[datetime] = Field(
        default=None, sa_column=Column("received_at", DateTime(timezone=True))
    )
    #: The rule that filed it, and why: the "why is this here?" the reading
    #: pane shows.
    matched_rule_id: Optional[int] = Field(default=None)
    routing_reason: Optional[str] = Field(default=None, max_length=255)
    routed_at: Optional[datetime] = Field(
        default=None, sa_column=Column("routed_at", DateTime(timezone=True))
    )
    #: system, or the administrator who re-routed it by hand.
    routed_by: Optional[str] = Field(default=None, max_length=64)
    #: The authentication verdicts, when the provider supplies them.
    auth_spf: Optional[str] = Field(default=None, max_length=32)
    auth_dkim: Optional[str] = Field(default=None, max_length=32)
    auth_dmarc: Optional[str] = Field(default=None, max_length=32)
    auth_summary: Optional[str] = Field(default=None, max_length=255)
    #: Held back because it failed authentication.
    is_quarantined: bool = Field(default=False)
    #: Marked important by a rule or by a person.
    is_important: bool = Field(default=False)
    #: Whether the message carries attachments.
    has_attachments: bool = Field(default=False)
    #: The attachments, as {filename, content_type, size} - the content
    #: itself is kept in core.mail_file.
    attachments: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    #: Free-form labels the mail carried (Gmail labels, mostly).
    labels: List[str] = Field(default=[], sa_column=Column(JSON))
    #: The account that composed it, for a sent message.
    created_by: Optional[int] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailFile(SQLModel, table=True):
    """The bytes of one attachment.

    The message keeps a description of each attachment (a filename, a type,
    a size) in its own JSON column; this table keeps what that description
    describes, so a student can actually download the file. Talking about a
    file the app never kept would be a mock feature, so ingest and a
    forward both file the bytes here.
    """

    __tablename__ = "mail_file"
    __table_args__ = (
        Index("ix_mail_file_message", "message_id"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The message it arrived with.
    message_id: int = Field(
        sa_column=Column("message_id", Integer, nullable=False)
    )
    #: What the file was called in the mail.
    filename: str = Field(max_length=500)
    #: The MIME type, as the mail claimed it.
    content_type: Optional[str] = Field(default=None, max_length=255)
    #: The size in bytes, of what actually arrived.
    size: int = Field(default=0)
    #: The hash of the bytes, so the same file twice is one file.
    sha256: Optional[str] = Field(default=None, max_length=64)
    #: Whether the file has been looked at: pending, clean, blocked.
    scan_status: str = Field(default="pending", max_length=16)
    #: The section the file's message was filed under.
    section: Optional[str] = Field(default=None, max_length=32)
    #: The bytes themselves.
    data: bytes = Field(default=b"", sa_column=Column("data", LargeBinary))

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailAuditLog(SQLModel, table=True):
    """
    Who changed what in the mail app.

    A rule registered, a message re-routed, a cluster moved: the trail is
    what makes an admin console trustworthy, and it is written by the code
    that does the change, never by the screen that asks for it.
    """

    __tablename__ = "mail_audit_log"
    __table_args__ = (
        Index("ix_mail_audit_log_group_created", "group", "created_at"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The bundle the action happened in.
    group: str = Field(default="ug", max_length=16)
    #: The account that did it, or None for the system itself.
    actor_user_id: Optional[int] = Field(default=None)
    #: What was done: rule.created, message.rerouted, cluster.moved...
    action: str = Field(max_length=64)
    #: What it was done to: rule, cluster, message, footer...
    target_type: Optional[str] = Field(default=None, max_length=32)
    #: Which one, as text (an id, an address).
    target_id: Optional[str] = Field(default=None, max_length=255)
    #: The rest: the before and after, in the system's own words.
    detail: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailFooterTemplate(SQLModel, table=True):
    """
    The institute's automatic footer.

    Every outgoing mail carries one: the institute, the section, who sent
    it, the portal link and the disclaimer. A section may have its own
    wording; the empty section key is the group's default.
    """

    __tablename__ = "mail_footer_template"
    __table_args__ = (
        Index(
            "uq_mail_footer_template_group_section", "group", "section", unique=True
        ),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The bundle the template belongs to.
    group: str = Field(default="ug", max_length=16)
    #: The section it is for; empty means the group's default.
    section: str = Field(default="", max_length=32)
    #: The footer's text, with the placeholders the sender fills in.
    body_text: str = Field(default="")
    #: The footer's HTML, when the section wants one.
    body_html: Optional[str] = Field(default=None)
    #: Whether this is the group's fallback.
    is_default: bool = Field(default=False)
    #: The administrator who wrote it.
    created_by: Optional[int] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailSignature(SQLModel, table=True):
    """
    An account's own signature.

    It sits above the institute's official footer, which no one may
    remove: a student may add their name, the college's line stays.
    """

    __tablename__ = "mail_signature"
    __table_args__ = (
        # One signature per account.
        Index("uq_mail_signature_user", "user_id", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The account the signature belongs to.
    user_id: int = Field(index=False)
    body_text: Optional[str] = Field(default=None)
    body_html: Optional[str] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )


class MailUserSettings(SQLModel, table=True):
    """
    An account's mail settings.

    The density, the reading pane's place, the undo-send delay, the
    keyboard shortcuts on or off: the small choices that make a mail app
    somebody's own.
    """

    __tablename__ = "mail_user_settings"
    __table_args__ = (
        # One settings row per account.
        Index("uq_mail_user_settings_user", "user_id", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    #: The account the settings belong to.
    user_id: int = Field(index=False)
    #: The settings themselves, as the app understands them.
    settings: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "created_at", DateTime(timezone=True), server_default=func.now()
        ),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            "updated_at", DateTime(timezone=True), server_default=func.now()
        ),
    )
