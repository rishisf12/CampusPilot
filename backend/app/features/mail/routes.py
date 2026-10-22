"""
The mail API: a section's inbox, and the compose that fills it.

Every route here is for a signed-in student, and every read is scoped to
the student's **group**: the undergraduate mailbox and the postgraduate
mailbox are different mail, so a master's student never sees an
undergraduate notice and the other way round.

The one exception is the ingest endpoint, which the poller posts to. It is
guarded by the group's own secret, and the secret is what says which
group's mailbox is being filled.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_user
from core.config import get_settings
from models import User
from features.mail import service
from features.mail.models import MailMessage
from features.mail.schemas import (
    MailComposeRequest,
    MailFileInfo,
    MailIngestRequest,
    MailListResponse,
    MailMessageResponse,
)
from features.mail.sections import (
    GROUP_IDS,
    GROUP_LABELS,
    SECTION_IDS,
    SECTION_LABELS,
    group_for_programme,
    is_group,
    is_section,
)
from sqlmodel import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mail", tags=["Mail"])


def _to_response(message: MailMessage) -> MailMessageResponse:
    return MailMessageResponse(
        id=message.id or 0,
        message_id=message.message_id,
        group=message.group,
        group_label=GROUP_LABELS.get(message.group, ""),
        section=message.section,
        section_label=SECTION_LABELS.get(message.section, SECTION_LABELS["other"]),
        direction=message.direction,
        from_email=message.from_email,
        from_name=message.from_name,
        to_email=message.to_email,
        subject=message.subject,
        snippet=message.snippet,
        body_text=message.body_text,
        body_html=message.body_html,
        received_at=message.received_at,
        is_read=bool(message.is_read),
        is_starred=bool(message.is_starred),
        has_attachments=bool(message.has_attachments),
        attachments=message.attachments or [],
        labels=message.labels or [],
    )


def _readable_groups(user: User, session: Session) -> List[str]:
    """
    Which mailboxes this account may read.

    A student reads the one their programme's group gets. An administrator,
    who is nobody's student, may read both - and the screen offers the
    choice.
    """
    role = getattr(user.role, "value", user.role)
    if role == "admin":
        return list(GROUP_IDS)

    from features.profile.service import get_profile_for_user

    profile = get_profile_for_user(session, user)
    group = group_for_programme(profile.programme if profile else None)
    if group:
        return [group]
    # No programme on the profile: the group is unknown, so nothing is
    # readable. An empty inbox is better than the wrong one.
    return []


@router.get("/sections")
def list_sections(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """The sections, with how many messages each holds."""
    groups = _readable_groups(user, session)
    counts = service.section_counts(session, group=groups[0] if len(groups) == 1 else None)
    unread = service.unread_counts(session, group=groups[0] if len(groups) == 1 else None)
    return {
        "groups": [
            {"id": key, "label": GROUP_LABELS[key]} for key in groups
        ],
        "sections": [
            {
                "id": section,
                "label": SECTION_LABELS[section],
                "count": counts.get(section, 0),
                "unread": unread.get(section, 0),
            }
            for section in SECTION_IDS
        ],
    }


@router.get("/messages", response_model=MailListResponse)
def list_mail_messages(
    section: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    starred: Optional[bool] = Query(None),
    direction: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    The messages, newest first.

    ``search`` looks in the sender, the subject and the body. ``section``
    narrows to one section; without it every section is in view. The group
    comes from the account - a student cannot ask for another group's mail
    by passing a parameter.
    """
    if section and not is_section(section):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown section '{section}'. Use one of {list(SECTION_IDS)}.",
        )

    readable = _readable_groups(user, session)
    chosen = group if is_group(group) and group in readable else None
    if chosen is None:
        chosen = readable[0] if len(readable) == 1 else None
    if chosen is None and len(readable) > 1:
        # An administrator reading both: no group means both.
        chosen = None

    messages, total = service.list_messages(
        session,
        group=chosen,
        section=section,
        search=search,
        starred=starred,
        direction=direction,
        page=page,
        size=size,
    )
    counts = service.section_counts(session, group=chosen)
    unread = service.unread_counts(session, group=chosen)
    return MailListResponse(
        total=total,
        page=page,
        size=size,
        messages=[_to_response(message) for message in messages],
        groups=[{"id": key, "label": GROUP_LABELS[key]} for key in readable],
        sections=[
            {
                "id": key,
                "label": SECTION_LABELS[key],
                "count": counts.get(key, 0),
                "unread": unread.get(key, 0),
            }
            for key in SECTION_IDS
        ],
        unread=unread,
        starred_count=service.starred_count(session, group=chosen),
    )


@router.get("/messages/{message_id}", response_model=MailMessageResponse)
def get_mail_message(
    message_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """One message, opened."""
    message = service.get_message(session, None, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    return _to_response(message)


@router.post("/messages/{message_id}/read", response_model=MailMessageResponse)
def set_mail_message_read(
    message_id: int,
    read: bool = Query(True),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Mark a message read or unread."""
    message = service.get_message(session, None, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    return _to_response(service.mark_read(session, message, read))


@router.post("/messages/{message_id}/star", response_model=MailMessageResponse)
def star_mail_message(
    message_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Star a message, or unstar it if it already was."""
    message = service.get_message(session, None, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    return _to_response(service.toggle_star(session, message))


@router.post("/compose", response_model=MailMessageResponse)
def compose_mail(
    payload: MailComposeRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Send a message, and keep a copy of what was sent.

    The copy is the point: a sent message is filed under its section like
    any other, so the thread it belongs to is in one place. A reply or a
    forward carries the original with it - a reply answers the sender, a
    forward quotes it under what the user wrote.
    """
    readable = _readable_groups(user, session)
    group = readable[0] if readable else "ug"

    original: Optional[MailMessage] = None
    if payload.reply_of or payload.forward_of:
        original_id = payload.reply_of or payload.forward_of
        found = service.get_message(session, group=group, message_id=original_id)
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The message being answered is not in this mailbox.",
            )
        original = found

    to_address = (payload.to or "").strip()
    if not to_address and payload.reply_of is not None and original is not None:
        to_address = original.from_email or ""
    if not to_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Who is it for?",
        )
    if "@" not in to_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{to_address}' is not an email address.",
        )

    subject = (payload.subject or "").strip()
    body = payload.body or ""
    if original is not None:
        if payload.reply_of:
            subject = subject or _replied_subject(original.subject)
        else:
            subject = subject or _forwarded_subject(original.subject)
            # The composer pre-fills the quote; only add it when the user
            # deleted it, so a forward never carries two copies.
            if "---------- Forwarded message ----------" not in body:
                body = f"{body}\n\n{_quote(original)}".strip()
        if not subject.startswith(("Re:", "Fwd:")):
            prefix = "Re:" if payload.reply_of else "Fwd:"
            subject = f"{prefix} {subject}".strip()

    sent = _send(
        group,
        to_address,
        subject,
        body,
        in_reply_to=original.message_id if payload.reply_of and original else None,
    )

    message = service.store_message(
        session,
        group=group,
        from_email=(user.email or "").lower(),
        from_name=user.full_name or user.username,
        to_email=to_address.lower(),
        subject=subject,
        body_text=body,
        received_at=datetime.now(timezone.utc),
        section=(
            payload.section
            if is_section(payload.section)
            else (original.section if original else None)
        ),
        direction="sent",
        created_by=user.id,
    )
    if sent is not None:
        logger.info("Mail sent to %s: %s", to_address, sent)
    return _to_response(message)


def _replied_subject(subject: Optional[str]) -> str:
    """The subject a reply takes, with one, and only one, Re:."""
    text = (subject or "").strip()
    return text if text.lower().startswith("re:") else f"Re: {text}"


def _forwarded_subject(subject: Optional[str]) -> str:
    """The subject a forward takes, with one, and only one, Fwd:."""
    text = (subject or "").strip()
    return text if text.lower().startswith("fwd:") else f"Fwd: {text}"


def _quote(message: MailMessage) -> str:
    """The quoted body a forward carries under the user's words."""
    header = [
        "---------- Forwarded message ----------",
        f"From: {message.from_name or message.from_email} <{message.from_email}>",
        f"Subject: {message.subject or '(no subject)'}",
        f"Date: {message.received_at:%d %B %Y, %H:%M}" if message.received_at else None,
    ]
    lines = [line for line in header if line]
    body = message.body_text or "(no text)"
    quoted = "\n".join(f"> {line}" for line in body.splitlines() or [""])
    return "\n".join(lines) + "\n\n" + quoted


def _send(
    group: str,
    to_address: str,
    subject: str,
    body: str,
    in_reply_to: Optional[str] = None,
) -> Optional[str]:
    """
    Hand the message to the mail server.

    A failure here is not a reason to lose the message: the copy is filed
    either way, and the error is logged. The student is told the message
    was kept but not sent.
    """
    import smtplib
    from email.message import EmailMessage as MimeMessage

    settings = get_settings()
    sender = settings.mail_from or settings.SMTP_USER
    if not settings.SMTP_HOST or not settings.SMTP_USER or not sender:
        logger.warning(
            "No SMTP credentials configured; the message to %s was filed but not sent.",
            to_address,
        )
        return None

    message = MimeMessage()
    message["From"] = sender
    message["To"] = to_address
    message["Subject"] = subject or "(no subject)"
    if in_reply_to:
        # A reply quotes the thread, and its headers say so: a mail client
        # that reads this keeps the conversation in one place.
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(body or "")

    try:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=15
            ) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=15
            ) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)
        return "sent"
    except Exception as exc:  # noqa: BLE001 - a failed send must not lose the mail
        logger.warning("Could not send the message to %s: %s", to_address, exc)
        return None


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
def ingest_mail(
    payload: MailIngestRequest,
    session: Session = Depends(get_session),
    authorization: Optional[str] = Header(None),
):
    """
    A message arriving from one group's mailbox.

    The poller posts here with that group's own secret, and the secret is
    what says which group's mailbox is being filled - so a poller can only
    ever file into its own group's inbox.
    """
    settings = get_settings()
    presented = (authorization or "").removeprefix("Bearer ").strip()

    group = None
    for candidate in GROUP_IDS:
        secret = settings.mail_group_secret(candidate)
        if secret and presented == secret:
            group = candidate
            break
    if group is None:
        raise HTTPException(status_code=401, detail="Bad ingest secret")

    # The section comes from the list of receiving mail ids: content sent
    # to one of the group's section addresses is filed under that
    # section. An address that is not on the list falls back to the
    # keyword classification, which usually lands it in "Other".
    section = settings.mail_section_for_address(group, payload.to or "")

    attachments: List[Dict[str, Any]] = []
    for attachment in payload.attachments or []:
        attachments.append(
            {
                "filename": attachment.get("filename") or "attachment",
                "content_type": attachment.get("content_type"),
                "size": attachment.get("size"),
            }
        )

    existing = None
    if payload.message_id:
        existing = session.exec(
            select(MailMessage).where(
                MailMessage.message_id == payload.message_id,
                MailMessage.group == group,
            )
        ).first()

    message = service.store_message(
        session,
        group=group,
        section=section,
        from_email=payload.from_email,
        from_name=payload.from_name,
        to_email=payload.to,
        subject=payload.subject,
        body_text=payload.text,
        body_html=payload.html,
        received_at=payload.date,
        attachments=attachments,
        labels=payload.labels,
        message_id=payload.message_id,
    )
    if existing is None and payload.attachments:
        # A new message: its attachments' bytes ride with the post, and
        # this is where they are kept. A re-post (the poller retrying)
        # must not duplicate the files. The files' ids go back onto the
        # message's descriptions, so a download button knows what to ask
        # for.
        stored = service.store_files(session, message, payload.attachments)
        described = list(message.attachments or [])
        pointer = 0
        for index, entry in enumerate(payload.attachments):
            if not entry.get("content"):
                continue
            if pointer < len(stored):
                file = stored[pointer]
                pointer += 1
                if index < len(described):
                    described[index] = {**described[index], "id": file.id}
        message.attachments = described
        session.add(message)
        session.commit()
        session.refresh(message)
    return {"id": message.id, "group": message.group, "section": message.section}


@router.get("/files", response_model=List[MailFileInfo])
def list_files(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Every attachment the mailbox carries, newest first.

    The download icon on the inbox holds this: one list of the files the
    group's mail has brought in, each row with its own download button.
    """
    readable = _readable_groups(user, session)
    chosen = readable[0] if len(readable) == 1 else None
    return service.list_files(session, group=chosen)


@router.get("/messages/{message_id}/attachments/{file_id}")
def download_attachment(
    message_id: int,
    file_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """One attachment's bytes, as a file the browser saves."""
    readable = _readable_groups(user, session)
    chosen = readable[0] if len(readable) == 1 else None
    found = service.get_file(session, chosen, message_id, file_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That file is not part of the mail this account reads.",
        )
    file, message = found
    filename = file.filename.replace('"', "'")
    return Response(
        content=file.data or b"",
        media_type=file.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
