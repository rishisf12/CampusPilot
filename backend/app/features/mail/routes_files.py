"""
Attachment file handling for the mail feature.

The message keeps a description of each attachment (filename, type, size)
in its JSON column; this module keeps what that description describes -
the bytes themselves, in core.mail_file.
"""
import base64
import binascii
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from features.mail.models import MailFile, MailMessage
from features.mail.sections import is_group

logger = logging.getLogger(__name__)


def store_files(
    session: Session, message: MailMessage, attachments: List[Dict[str, Any]]
) -> List[MailFile]:
    """
    File the bytes of an ingested message's attachments.

    An entry carrying base64 ``content`` becomes one row here; an entry
    without content is only described, because nothing arrived to keep.
    Duplicate content (same sha256) is stored once.
    """
    stored: List[MailFile] = []
    for attachment in attachments:
        raw = attachment.get("content")
        if not raw:
            continue
        try:
            data = base64.b64decode(raw)
        except (binascii.Error, ValueError) as exc:
            logger.warning(
                "Could not decode attachment %r for message %s: %s",
                attachment.get("filename"),
                message.message_id,
                exc,
            )
            continue
        digest = hashlib.sha256(data).hexdigest()
        existing = session.exec(
            select(MailFile).where(MailFile.sha256 == digest)
        ).first()
        if existing is not None:
            stored.append(existing)
            continue
        file = MailFile(
            message_id=message.id or 0,
            filename=(attachment.get("filename") or "attachment")[:500],
            content_type=attachment.get("content_type"),
            size=len(data),
            sha256=digest,
            section=message.section,
            data=data,
        )
        session.add(file)
        stored.append(file)
    if stored:
        session.commit()
        for file in stored:
            session.refresh(file)
    return stored


def list_files(
    session: Session, group: Optional[str] = None, limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Every attachment the group's mail carries, newest first.

    This is the Files (Downloads) view: the files are attached to messages
    that may be read years apart, so the view is one list, not one per
    conversation. Each row carries what the download button needs and what
    the row shows - the file's name, who sent its message, and when.
    """
    stmt = (
        select(MailFile, MailMessage)
        .join(
            MailMessage,
            MailFile.message_id == MailMessage.id,
        )
        .order_by(MailMessage.received_at.desc(), MailFile.filename)
        .limit(limit)
    )
    if is_group(group):
        stmt = stmt.where(MailMessage.group == group)
    rows: List[Dict[str, Any]] = []
    for file, message in session.exec(stmt).all():
        rows.append(
            {
                "id": file.id,
                "message_id": message.id,
                "filename": file.filename,
                "content_type": file.content_type,
                "size": file.size,
                "section": message.section,
                "group": message.group,
                "from_email": message.from_email,
                "from_name": message.from_name,
                "subject": message.subject,
                "received_at": message.received_at,
            }
        )
    return rows


def get_file(
    session: Session, group: Optional[str], message_id: int, file_id: int
) -> Optional[Tuple[MailFile, MailMessage]]:
    """
    One file, and its message, if the group may read it.
    """
    stmt = select(MailFile, MailMessage).where(
        MailFile.id == file_id,
        MailFile.message_id == MailMessage.id,
        MailMessage.id == message_id,
    )
    if is_group(group):
        stmt = stmt.where(MailMessage.group == group)
    return session.exec(stmt).first()
