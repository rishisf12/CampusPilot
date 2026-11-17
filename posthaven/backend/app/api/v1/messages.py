import re
from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, cast, String

from app.models.message import Message, MessageRead, MessageListItem
from app.models.folder import Folder
from app.models.account import MailAccount
from app.core.deps import CurrentUser, SessionDep
from app.core.crypto import decrypt_credential
from app.core.notify import publish_user_event
from app.services.imap_client import ImapClient

import aiosmtplib
from email.message import EmailMessage

router = APIRouter(prefix="/messages", tags=["messages"])


# ---------- request models ----------

class FlagsUpdate(BaseModel):
    add: list[str] = []
    remove: list[str] = []


class MoveRequest(BaseModel):
    destination: str


# Lenient address: local@domain, any TLD or dotless host (internal/dev servers).
EmailAddr = Annotated[str, Field(pattern=r"^[^@\s,]{1,64}@[^@\s,]{1,255}$")]


class SendMessageRequest(BaseModel):
    account_id: UUID
    to: list[EmailAddr]
    cc: list[EmailAddr] = []
    bcc: list[EmailAddr] = []
    subject: str
    body_text: str = ""
    body_html: Optional[str] = None


# ---------- helpers ----------

async def _get_owned_message(session: AsyncSession, user, message_id: UUID) -> Message:
    msg = await session.get(Message, message_id)
    if not msg or msg.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return msg


async def _get_owned_account(session: AsyncSession, user, account_id: UUID) -> MailAccount:
    account = await session.get(MailAccount, account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


async def _imap_for(account: MailAccount) -> ImapClient:
    password = decrypt_credential(account.encrypted_password) if account.encrypted_password else ""
    client = ImapClient(
        host=account.host,
        port=account.imap_port,
        username=account.username,
        password=password,
        security=account.imap_security,
    )
    await client.connect()
    return client


async def _ensure_folder(session: AsyncSession, account: MailAccount, user_id: UUID,
                         name: str, special_use: Optional[str]) -> Folder:
    """Return DB folder row for (account, name); create folder row if missing."""
    result = await session.exec(
        select(Folder).where(Folder.account_id == account.id, Folder.name == name)
    )
    folder = result.first()
    if folder:
        if special_use and not folder.special_use:
            folder.special_use = special_use
            session.add(folder)
        return folder
    folder = Folder(
        user_id=user_id,
        account_id=account.id,
        name=name,
        special_use=special_use,
        subscribed=True,
    )
    session.add(folder)
    await session.flush()
    return folder


def _flags_add(current: list[str] | None, flags: list[str]) -> list[str]:
    current = list(current or [])
    for f in flags:
        if f not in current:
            current.append(f)
    return current


def _flags_remove(current: list[str] | None, flags: list[str]) -> list[str]:
    return [f for f in (current or []) if f not in flags]


# ---------- endpoints ----------

@router.get("", response_model=dict)
async def list_messages(
    current_user: CurrentUser,
    session: SessionDep,
    folder_id: UUID = Query(...),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    unread_only: bool = Query(default=False),
):
    folder = await session.get(Folder, folder_id)
    if not folder or folder.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    q = select(Message).where(Message.folder_id == folder_id)
    if unread_only:
        seen_match = cast(Message.flags, String).ilike("%seen%")
        q = q.where(Message.flags.is_(None) | ~seen_match)
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            q = q.where(Message.received_at < cursor_dt)
        except ValueError:
            pass  # ignore malformed cursor, return first page

    q = q.order_by(Message.received_at.desc().nulls_last()).limit(limit)
    result = await session.exec(q)
    messages = result.all()

    next_cursor = None
    if messages:
        last = messages[-1]
        if last.received_at:
            next_cursor = last.received_at.isoformat()

    return {
        "messages": [MessageListItem.model_validate(m) for m in messages],
        "next_cursor": next_cursor,
        "count": len(messages),
    }


@router.get("/{message_id}", response_model=MessageRead)
async def get_message(
    current_user: CurrentUser,
    session: SessionDep,
    message_id: UUID,
):
    msg = await _get_owned_message(session, current_user, message_id)
    return msg


@router.patch("/{message_id}/flags")
async def update_flags(
    message_id: UUID,
    payload: FlagsUpdate,
    current_user: CurrentUser,
    session: SessionDep,
):
    msg = await _get_owned_message(session, current_user, message_id)
    folder = await session.get(Folder, msg.folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    account = await _get_owned_account(session, current_user, folder.account_id)

    # push flags to IMAP first so server stays source of truth
    client = await _imap_for(account)
    try:
        await client.select(folder.name)
        ok = await client.store_uids(
            str(msg.uid), add_flags=payload.add or None, remove_flags=payload.remove or None
        )
    finally:
        await client.logout()
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IMAP STORE failed")

    flags = _flags_remove(_flags_add(msg.flags, payload.add), payload.remove)
    msg.flags = flags
    session.add(msg)
    await session.commit()
    return {"flags": flags}


@router.post("/{message_id}/move")
async def move_message(
    message_id: UUID,
    payload: MoveRequest,
    current_user: CurrentUser,
    session: SessionDep,
):
    msg = await _get_owned_message(session, current_user, message_id)
    folder = await session.get(Folder, msg.folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    account = await _get_owned_account(session, current_user, folder.account_id)

    destination = payload.destination.strip()
    if not re.fullmatch(r"[^\r\n'\"]{1,100}", destination):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid folder name")

    client = await _imap_for(account)
    try:
        await client.select(folder.name)
        try:
            await client.create_folder(destination)
        except Exception:
            pass  # already exists is fine
        ok = await client.move_uids(str(msg.uid), destination)
    finally:
        await client.logout()
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IMAP move failed")

    dest_folder = await _ensure_folder(session, account, current_user.id, destination, None)
    msg.folder_id = dest_folder.id
    session.add(msg)
    await session.commit()
    return {"ok": True, "destination": destination}


@router.post("/send")
async def send_message(
    payload: SendMessageRequest,
    current_user: CurrentUser,
    session: SessionDep,
):
    account = await _get_owned_account(session, current_user, payload.account_id)

    from_addr = account.username
    display = current_user.display_name or ""
    from_header = f"{display} <{from_addr}>" if display else from_addr

    msg = EmailMessage()
    msg["From"] = from_header
    msg["To"] = ", ".join(str(a) for a in payload.to)
    if payload.cc:
        msg["Cc"] = ", ".join(str(a) for a in payload.cc)
    if payload.bcc:
        msg["Bcc"] = ", ".join(str(a) for a in payload.bcc)
    msg["Subject"] = payload.subject
    msg.set_content(payload.body_text or "")
    if payload.body_html:
        msg.add_alternative(payload.body_html, subtype="html")
    raw = msg.as_bytes()

    # ---- send via SMTP ----
    timeout = 30
    try:
        if account.smtp_security == "ssl":
            smtp = aiosmtplib.SMTP(hostname=account.host, port=account.smtp_port,
                                   use_tls=True, timeout=timeout)
        elif account.smtp_security == "starttls":
            smtp = aiosmtplib.SMTP(hostname=account.host, port=account.smtp_port,
                                   use_tls=False, timeout=timeout)
        else:  # none
            smtp = aiosmtplib.SMTP(hostname=account.host, port=account.smtp_port,
                                   use_tls=False, timeout=timeout)
        await smtp.connect()
        if account.smtp_security == "starttls":
            await smtp.starttls()
        password = decrypt_credential(account.encrypted_password) if account.encrypted_password else ""
        if account.username and password:
            await smtp.login(account.username, password)
        await smtp.send_message(msg)
        await smtp.quit()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"SMTP send failed: {exc}") from exc

    # ---- copy to Sent on the server (best effort) ----
    appended = False
    client = None
    try:
        client = await _imap_for(account)
        try:
            await client.create_folder("Sent")
        except Exception:
            pass
        appended = await client.append("Sent", raw, ["\\Seen"])
    except Exception:
        appended = False
    finally:
        if client:
            await client.logout()

    # ---- persist in DB Sent folder ----
    sent_folder = await _ensure_folder(
        session, account, current_user.id, "Sent", "\\Sent"
    )
    result = await session.exec(
        select(Message.uid)
        .where(Message.account_id == account.id, Message.folder_id == sent_folder.id)
        .order_by(Message.uid.desc())
    )
    max_uid = result.first()
    uid = (max_uid + 1) if max_uid else 1
    now = datetime.now(timezone.utc)

    db_msg = Message(
        user_id=current_user.id,
        account_id=account.id,
        folder_id=sent_folder.id,
        uid=uid,
        message_id=msg.get("Message-ID"),
        from_json={"name": display, "address": from_addr},
        to_json=[{"name": "", "address": str(a)} for a in payload.to],
        cc_json=[{"name": "", "address": str(a)} for a in payload.cc],
        subject=payload.subject,
        snippet=(payload.body_text or "").strip()[:200],
        body_text=payload.body_text,
        body_html=payload.body_html,
        flags=["\\Seen"],
        size=len(raw),
        has_attachments=False,
        internal_date=now,
        received_at=now,
    )
    session.add(db_msg)
    sent_folder.message_count = (sent_folder.message_count or 0) + 1
    session.add(sent_folder)
    await session.commit()

    # ---- notify recipients that have this mailbox connected (demo real-time) ----
    recipients = [str(a) for a in (*payload.to, *payload.cc, *payload.bcc)]
    if recipients:
        result = await session.exec(
            select(MailAccount).where(MailAccount.username.in_(recipients))
        )
        for acct in result.all():
            await publish_user_event(
                acct.user_id,
                {"type": "mail:incoming", "account_id": str(acct.id)},
            )

    return {"ok": True, "appended_to_sent": appended}
