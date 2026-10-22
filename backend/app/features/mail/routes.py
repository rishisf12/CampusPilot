"""
The mail API: a section's inbox, and the compose that fills it.

Every route here is for a signed-in student, and every read is scoped to
the student's **group**: the undergraduate mailbox and the postgraduate
mailbox are different mail, so a master's student never sees an
undergraduate notice and the other way round.

The one exception is the ingest endpoint, which the poller posts to. It is
guarded by the group's own secret, and the secret is what says which
group's mailbox is being filled.

Filing is sender-first: the college registers clusters of sender email ids
per section, and mail from a registered sender files there no matter which
receiving address it was posted to.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin, get_current_user
from models import User
from features.mail import service
from features.mail.models import MailCluster, MailMessage
from features.mail.schemas import (
    MailClusterCreateRequest,
    MailClusterMembersRequest,
    MailClusterResponse,
    MailClusterUpdateRequest,
    MailComposeRequest,
    MailFileInfo,
    MailIngestRequest,
    MailListResponse,
    MailMessageResponse,
    MailMoveRequest,
    MailSenderAssignRequest,
    MailSenderRuleCreateRequest,
    MailSenderRuleResponse,
    MailUnknownSender,
)
from features.mail.sections import (
    GROUP_IDS,
    GROUP_LABELS,
    SECTION_IDS,
    SECTION_LABELS,
    UNASSIGNED_LABEL,
    UNASSIGNED_SECTION,
    group_for_programme,
    is_group,
    is_section,
    is_storable_section,
    section_label,
)
from sqlmodel import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mail", tags=["Mail"])


def _section_label(section: str) -> str:
    """The label of a section, including the unassigned state."""
    return section_label(section)


def _cluster_names(session: Session, group: Optional[str] = None) -> Dict[int, str]:
    """The clusters' names, by id, so a row can say who filed it."""
    return {
        cluster.id: cluster.name
        for cluster in service.list_clusters(session, group)
        if cluster.id is not None
    }


def _to_response(
    message: MailMessage, cluster_names: Optional[Dict[int, str]] = None
) -> MailMessageResponse:
    names = cluster_names if cluster_names is not None else {}
    return MailMessageResponse(
        id=message.id or 0,
        message_id=message.message_id,
        group=message.group,
        group_label=GROUP_LABELS.get(message.group, ""),
        section=message.section,
        section_label=_section_label(message.section),
        cluster_id=message.cluster_id,
        cluster_name=names.get(message.cluster_id) if message.cluster_id else None,
        thread_id=message.thread_id,
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
        is_important=bool(message.is_important),
        is_archived=bool(message.is_archived),
        is_trashed=bool(message.is_trashed),
        is_quarantined=bool(message.is_quarantined),
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
                "label": _section_label(section),
                "count": counts.get(section, 0),
                "unread": unread.get(section, 0),
            }
            for section in list(SECTION_IDS) + [UNASSIGNED_SECTION]
        ],
    }


@router.get("/messages", response_model=MailListResponse)
def list_mail_messages(
    section: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    starred: Optional[bool] = Query(None),
    direction: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    cluster_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    The messages, newest first.

    ``search`` looks in the sender, the subject and the body, and reads
    the operators a mail app writes (``from:``, ``section:``,
    ``is:unread``, ``has:attachment``). ``section`` narrows to one label,
    ``state`` to one pile (inbox, sent, archived, trashed, all). The group
    comes from the account - a student cannot ask for another group's mail
    by passing a parameter.
    """
    if section and not is_storable_section(section):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown section '{section}'. Use one of "
                f"{list(SECTION_IDS)} or '{UNASSIGNED_SECTION}'."
            ),
        )
    if state and state not in ("inbox", "sent", "archived", "trashed", "all"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown state '{state}'. Use one of "
                "inbox, sent, archived, trashed, all."
            ),
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
        cluster_id=cluster_id,
        search=search,
        starred=starred,
        direction=direction,
        state=state,
        page=page,
        size=size,
    )
    counts = service.section_counts(session, group=chosen)
    unread = service.unread_counts(session, group=chosen)
    names = _cluster_names(session, chosen)
    return MailListResponse(
        total=total,
        page=page,
        size=size,
        messages=[_to_response(message, names) for message in messages],
        groups=[{"id": key, "label": GROUP_LABELS[key]} for key in readable],
        sections=[
            {
                "id": key,
                "label": _section_label(key),
                "count": counts.get(key, 0),
                "unread": unread.get(key, 0),
            }
            for key in list(SECTION_IDS) + [UNASSIGNED_SECTION]
        ],
        unread=unread,
        starred_count=service.starred_count(session, group=chosen),
        clusters=[
            _cluster_response(session, cluster, chosen)
            for cluster in service.list_clusters(session, chosen)
        ],
    )


@router.get("/messages/{message_id}", response_model=MailMessageResponse)
def get_mail_message(
    message_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """One message, opened."""
    message = service.get_message(session, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    return _to_response(message, _cluster_names(session, message.group))


@router.post("/messages/{message_id}/read", response_model=MailMessageResponse)
def set_mail_message_read(
    message_id: int,
    read: bool = Query(True),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Mark a message read or unread."""
    message = service.get_message(session, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    return _to_response(
        service.mark_read(session, message, read),
        _cluster_names(session, message.group),
    )


@router.post("/messages/{message_id}/star", response_model=MailMessageResponse)
def star_mail_message(
    message_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Star a message, or unstar it if it already was."""
    message = service.get_message(session, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    return _to_response(
        service.toggle_star(session, message),
        _cluster_names(session, message.group),
    )


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
        found = service.get_message(session, original_id)
        if found is None or found.group not in _readable_groups(user, session):
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
            if "---------- Forwarded message ----------" not in body:
                body = f"{body}\n\n{_quote(original)}".strip()
        if not subject.startswith(("Re:", "Fwd:")):
            prefix = "Re:" if payload.reply_of else "Fwd:"
            subject = f"{prefix} {subject}".strip()

    # Composing is stored only (no SMTP in dummy mode); real providers
    # plug in later via MAIL_PROVIDER.
    message = service.store_message(
        session,
        group=group,
        from_email=(user.email or "").lower(),
        from_name=user.full_name or user.username,
        to_email=to_address.lower(),
        to_emails=[to_address.lower()],
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
    return _to_response(message, _cluster_names(session, message.group))


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

    Filed by the sender first: the college registers the sender email ids
    each section's mail comes from, and mail from one of those is filed
    there no matter which receiving address it was posted to. A sender
    nobody registered waits in the unassigned state.
    """
    from core.config import get_settings

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

    # One message, filed by the sender first.
    filing = service.filing_for(session, group, payload.from_email)
    section = filing.section
    cluster_id = filing.cluster_id

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
        cluster_id=cluster_id,
        intake_address=payload.to,
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
        # must not duplicate the files.
        from features.mail.routes_files import store_files

        stored = store_files(session, message, payload.attachments)
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
    return {"id": message.id, "group": message.group, "section": message.section, "cluster_id": message.cluster_id}


@router.get("/files", response_model=List[MailFileInfo])
def list_files(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Every attachment the mailbox carries, newest first."""
    from features.mail.routes_files import list_files as svc_list_files

    readable = _readable_groups(user, session)
    chosen = readable[0] if len(readable) == 1 else None
    return svc_list_files(session, group=chosen)


@router.get("/messages/{message_id}/attachments/{file_id}")
def download_attachment(
    message_id: int,
    file_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """One attachment's bytes, as a file the browser saves."""
    from features.mail.routes_files import get_file as svc_get_file

    readable = _readable_groups(user, session)
    chosen = readable[0] if len(readable) == 1 else None
    found = svc_get_file(session, chosen, message_id, file_id)
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


# --------------------------------------------------------------------------
# The sender clusters. An administrator's job: the student only reads the
# file the rules produce.


def _rule_response(rule, cluster_names: Optional[Dict[int, str]] = None) -> MailSenderRuleResponse:
    names = cluster_names if cluster_names is not None else {}
    return MailSenderRuleResponse(
        id=rule.id or 0,
        group=rule.group,
        group_label=GROUP_LABELS.get(rule.group, rule.group),
        pattern=rule.pattern,
        section=rule.section,
        section_label=_section_label(rule.section),
        kind=rule.kind or "exact",
        cluster_id=rule.cluster_id,
        cluster_name=names.get(rule.cluster_id) if rule.cluster_id else None,
        priority=rule.priority,
        is_active=rule.is_active,
        notes=rule.notes,
        created_at=rule.created_at,
    )


def _cluster_response(
    session: Session, cluster: MailCluster, group: Optional[str] = None
) -> MailClusterResponse:
    """One cluster, with its senders and how much mail it filed."""
    names = {
        other.id: other.name
        for other in service.list_clusters(session, group)
        if other.id is not None
    }
    members = [
        _rule_response(rule, names)
        for rule in service.cluster_members(session, cluster.id or 0)
    ]
    filed = service.cluster_message_count(session, cluster.id or 0, group)
    return MailClusterResponse(
        id=cluster.id or 0,
        group=cluster.group,
        group_label=GROUP_LABELS.get(cluster.group, cluster.group),
        name=cluster.name,
        section=cluster.section,
        section_label=_section_label(cluster.section),
        description=cluster.description,
        members=members,
        message_count=filed,
        created_at=cluster.created_at,
    )


@router.get("/clusters", response_model=List[MailClusterResponse])
def list_clusters(
    group: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """The registered clusters, with the senders in each."""
    if group and not is_group(group):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mail group '{group}'.",
        )
    return [
        _cluster_response(session, cluster, group)
        for cluster in service.list_clusters(session, group)
    ]


@router.post("/clusters", response_model=MailClusterResponse, status_code=201)
def create_cluster(
    payload: MailClusterCreateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Register a cluster: a name, the section it files into, its senders.

    The senders may be a list pasted in one go - that is the normal way a
    cluster is built - and they are registered even if the mail they wrote
    has already arrived: that mail is filed as soon as the cluster exists.
    """
    try:
        cluster = service.create_cluster(
            session,
            group=payload.group,
            name=payload.name,
            section=payload.section,
            description=payload.description,
            members=payload.members,
            created_by=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    service.refile_all(session, cluster.group)
    return _cluster_response(session, cluster, cluster.group)


@router.patch("/clusters/{cluster_id}", response_model=MailClusterResponse)
def update_cluster(
    cluster_id: int,
    payload: MailClusterUpdateRequest,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    Rename a cluster, or move it to another section.

    Moving a cluster moves the mail it filed: the students' inbox keeps
    every message, under the section the cluster now names.
    """
    try:
        cluster = service.update_cluster(
            session,
            cluster_id,
            name=payload.name,
            section=payload.section,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such cluster.",
        )
    return _cluster_response(session, cluster, cluster.group)


@router.delete("/clusters/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cluster(
    cluster_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    A cluster, unregistered.

    Its senders go with it and the mail it filed goes back to the
    unassigned state, where it waits for a sender to be registered again.
    """
    if not service.delete_cluster(session, cluster_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such cluster.",
        )


@router.post("/clusters/{cluster_id}/members", response_model=MailClusterResponse)
def add_cluster_members(
    cluster_id: int,
    payload: MailClusterMembersRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Add senders to a cluster, and file the mail they wrote.

    A sender already registered moves into this cluster rather than being
    registered twice, and every message from that sender is filed under
    the cluster's section.
    """
    cluster = service.get_cluster(session, cluster_id)
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such cluster.",
        )
    try:
        service.add_cluster_members(
            session, cluster_id, payload.members, created_by=admin.id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    service.refile_all(session, cluster.group)
    cluster = service.get_cluster(session, cluster_id)
    return _cluster_response(session, cluster, cluster.group)


@router.delete(
    "/clusters/{cluster_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_cluster_member(
    cluster_id: int,
    member_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """One sender out of a cluster. The mail it filed goes back to unassigned."""
    member = next(
        (
            rule
            for rule in service.cluster_members(session, cluster_id)
            if rule.id == member_id
        ),
        None,
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such sender in this cluster.",
        )
    if not service.remove_cluster_member(session, member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such sender in this cluster.",
        )


@router.get("/senders/unknown", response_model=List[MailUnknownSender])
def list_unknown_senders(
    group: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    The senders nobody registered, with how much mail each wrote.

    This is the worklist: every row is a candidate for a cluster, and the
    suggested section is a hint from the words in the mail - the college
    decides, the words do not.
    """
    if group and not is_group(group):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mail group '{group}'.",
        )
    return [
        MailUnknownSender(
            from_email=row["from_email"],
            from_name=row["from_name"],
            count=row["count"],
            unread=row["unread"],
            last_seen=row["last_seen"],
            suggested_section=row["suggested_section"],
            suggested_section_label=_section_label(row["suggested_section"]),
        )
        for row in service.unknown_senders(session, group)
    ]


@router.post("/senders/assign", response_model=MailClusterResponse)
def assign_sender(
    payload: MailSenderAssignRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Put a sender nobody registered into a cluster.

    The sender is registered, and every message it wrote is filed under
    the cluster's section at once - the worklist empties itself.
    """
    if not is_group(payload.group):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mail group '{payload.group}'.",
        )
    address = (payload.from_email or "").strip().lower()
    if not address or "@" not in address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{payload.from_email}' is not a sender email id.",
        )
    if payload.cluster_id is not None:
        cluster = service.get_cluster(session, payload.cluster_id)
        if cluster is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No such cluster.",
            )
        try:
            service.add_cluster_members(
                session, cluster.id or 0, [address], created_by=admin.id
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        service.refile_all(session, cluster.group)
        cluster = service.get_cluster(session, payload.cluster_id)
        return _cluster_response(session, cluster, cluster.group)

    section = payload.section
    if not is_section(section):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mail section '{section}'.",
        )
    try:
        service.create_sender_rule(
            session,
            group=payload.group,
            pattern=address,
            section=section,
            created_by=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    service.refile_sender(session, payload.group, address)
    return MailClusterResponse(
        id=0,
        group=payload.group,
        group_label=GROUP_LABELS.get(payload.group, payload.group),
        name=address,
        section=section,
        section_label=_section_label(section),
    )


@router.post("/refile")
def refile_mail(
    group: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    File every message by the current rules.

    The button on the admin screen: after the college registers a new
    cluster, the mail that arrived before it is filed as well.
    """
    if group and not is_group(group):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mail group '{group}'.",
        )
    return {"refiled": service.refile_all(session, group)}


# --------------------------------------------------------------------------
# What a student can do with one message, the way a mail app does it.


@router.post("/messages/{message_id}/move", response_model=MailMessageResponse)
def move_message(
    message_id: int,
    payload: MailMoveRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Move a message to another section by hand.

    The "Move to" of a mail app: a student who knows a notice belongs
    elsewhere can put it there, and the move does not change who sent it.
    """
    message = service.get_message(session, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    if payload.section is not None:
        if not is_storable_section(payload.section):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown section '{payload.section}'.",
            )
        message.section = payload.section
    if payload.cluster_id is not None:
        cluster = service.get_cluster(session, payload.cluster_id)
        if cluster is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No such cluster.",
            )
        message.cluster_id = cluster.id
        message.section = cluster.section
    session.add(message)
    session.commit()
    session.refresh(message)
    return _to_response(message, _cluster_names(session, message.group))


@router.post("/messages/{message_id}/archive", response_model=MailMessageResponse)
def archive_message(
    message_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Archive a message: out of the inbox, not thrown away."""
    message = service.get_message(session, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    message.is_archived = True
    message.is_trashed = False
    session.add(message)
    session.commit()
    session.refresh(message)
    return _to_response(message, _cluster_names(session, message.group))


@router.post("/messages/{message_id}/trash", response_model=MailMessageResponse)
def trash_message(
    message_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Throw a message away. It can be brought back."""
    message = service.get_message(session, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    message.is_trashed = True
    session.add(message)
    session.commit()
    session.refresh(message)
    return _to_response(message, _cluster_names(session, message.group))


@router.post("/messages/{message_id}/restore", response_model=MailMessageResponse)
def restore_message(
    message_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Bring a message back from the trash."""
    message = service.get_message(session, message_id)
    if message is None or message.group not in _readable_groups(user, session):
        raise HTTPException(status_code=404, detail="Message not found")
    message.is_trashed = False
    message.is_archived = False
    session.add(message)
    session.commit()
    session.refresh(message)
    return _to_response(message, _cluster_names(session, message.group))
