"""
The mail service: filing, listing, starring, composing.

Everything a section's inbox does, in one place, so the routes stay thin.
The list is the interesting part: a section's inbox is a search over
messages, so the query has to search the sender, the subject and the body,
and it has to page without counting the rows twice.

Every read is scoped to a **group** - the undergraduate mailbox and the
postgraduate mailbox are different mail, and a group never sees the
other's.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlmodel import Session, or_, select

from features.mail.models import MailDirection, MailMessage
from features.mail.sections import GROUP_IDS, classify, is_group, is_section

logger = logging.getLogger(__name__)

#: How long a snippet is.
SNIPPET_LENGTH = 220


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snippet(body: Optional[str]) -> str:
    """The first lines of a body, on one line."""
    if not body:
        return ""
    text = re.sub(r"\s+", " ", body).strip()
    return text[:SNIPPET_LENGTH]


def message_id_for(
    group: str, from_email: str, subject: str, received_at: Optional[datetime]
) -> str:
    """
    A stable identifier for a message.

    The mail protocol's own Message-ID is best, but a mailbox does not
    always carry one, so a hash of the group, the sender, the subject and
    the arrival time stands in. The group is in the hash because the two
    mailboxes are different mail: the same notice sent to both is two
    messages, and each group files its own copy.

    The point is that the same message is never filed twice: the poller runs
    every minute and the mailbox does not move.
    """
    stamp = received_at.isoformat() if received_at else ""
    digest = hashlib.sha256(
        f"{group}|{from_email.lower()}|{(subject or '').strip().lower()}|{stamp}".encode(
            "utf-8"
        )
    )
    return digest.hexdigest()[:40]


def list_messages(
    session: Session,
    group: Optional[str] = None,
    section: Optional[str] = None,
    search: Optional[str] = None,
    starred: Optional[bool] = None,
    direction: Optional[str] = None,
    page: int = 1,
    size: int = 30,
) -> Tuple[List[MailMessage], int]:
    """
    The messages, newest first.

    ``search`` looks in the sender, the subject and the body - a notice is
    found by who wrote it, what it says, or what is in it.
    """
    stmt = select(MailMessage)
    if is_group(group):
        stmt = stmt.where(MailMessage.group == group)
    if is_section(section):
        stmt = stmt.where(MailMessage.section == section)
    if starred is not None:
        stmt = stmt.where(MailMessage.is_starred == starred)
    if direction in ("inbox", MailDirection.SENT.value):
        stmt = stmt.where(MailMessage.direction == direction)
    term = (search or "").strip()
    if term:
        like = f"%{term.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(MailMessage.subject).like(like),
                func.lower(MailMessage.from_email).like(like),
                func.lower(MailMessage.from_name).like(like),
                func.lower(MailMessage.body_text).like(like),
                func.lower(MailMessage.snippet).like(like),
            )
        )

    rows = session.exec(stmt).all()
    total = len(rows)
    rows.sort(
        key=lambda m: (
            m.received_at is None,
            -(m.received_at.timestamp() if m.received_at else 0),
        )
    )
    page = max(1, page)
    size = max(1, min(size, 100))
    start = (page - 1) * size
    return rows[start : start + size], total


def get_message(session: Session, message_id: int) -> Optional[MailMessage]:
    """One message by its id."""
    return session.get(MailMessage, message_id)


def mark_read(session: Session, message: MailMessage, read: bool = True) -> MailMessage:
    """Mark a message read or unread."""
    message.is_read = read
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def toggle_star(session: Session, message: MailMessage) -> MailMessage:
    """Star a message, or unstar it if it already was."""
    message.is_starred = not message.is_starred
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def store_message(
    session: Session,
    *,
    group: str,
    from_email: str,
    from_name: Optional[str] = None,
    to_email: Optional[str] = None,
    subject: Optional[str] = None,
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
    received_at: Optional[datetime] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    labels: Optional[List[str]] = None,
    section: Optional[str] = None,
    message_id: Optional[str] = None,
    direction: str = MailDirection.INBOX.value,
    created_by: Optional[int] = None,
) -> MailMessage:
    """
    File a message.

    The same message is never filed twice: the identifier is checked first,
    so a poller that runs every minute over a mailbox that does not move
    costs one row, not one row a minute.
    """
    if not from_email:
        raise ValueError("A message needs a sender.")
    if not is_group(group):
        raise ValueError(f"Unknown mail group '{group}'.")
    if received_at is None:
        received_at = _now()

    identifier = message_id or message_id_for(
        group, from_email, subject or "", received_at
    )
    existing = session.exec(
        select(MailMessage).where(MailMessage.message_id == identifier)
    ).first()
    if existing is not None:
        return existing

    if not is_section(section):
        section = classify(
            from_name,
            from_email,
            subject,
            (body_text or "")[:400],
            " ".join(str(label) for label in (labels or [])),
        )

    message = MailMessage(
        message_id=identifier,
        group=group,
        section=section,
        direction=direction,
        from_email=from_email.lower(),
        from_name=from_name,
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        snippet=_snippet(body_text or body_html),
        received_at=received_at,
        has_attachments=bool(attachments),
        attachments=list(attachments or []),
        labels=list(labels or []),
        created_by=created_by,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def section_counts(session: Session, group: Optional[str] = None) -> Dict[str, int]:
    """How many messages each section holds."""
    counts = {section: 0 for section in _section_ids()}
    for message in _messages(session, group):
        if message.section in counts:
            counts[message.section] += 1
    return counts


def unread_counts(session: Session, group: Optional[str] = None) -> Dict[str, int]:
    """How many unread messages each section holds."""
    counts = {section: 0 for section in _section_ids()}
    for message in _messages(session, group):
        if message.is_read or message.section not in counts:
            continue
        counts[message.section] += 1
    return counts


def starred_count(session: Session, group: Optional[str] = None) -> int:
    """How many starred messages there are."""
    return sum(1 for message in _messages(session, group) if message.is_starred)


def _section_ids() -> Tuple[str, ...]:
    from features.mail.sections import SECTION_IDS

    return SECTION_IDS


def _messages(session: Session, group: Optional[str] = None) -> List[MailMessage]:
    stmt = select(MailMessage)
    if is_group(group):
        stmt = stmt.where(MailMessage.group == group)
    return list(session.exec(stmt).all())
