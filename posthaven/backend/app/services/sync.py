import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.account import MailAccount
from app.models.folder import Folder
from app.models.message import Message
from app.services.imap_client import ImapClient
from app.services.mime_parser import parse_message
from app.core.crypto import decrypt_credential

_FETCH_RE = re.compile(
    r"FLAGS\s*\((?P<flags>[^)]*)\).*?"
    r"INTERNALDATE\s*\"(?P<internaldate>[^\"]+)\".*?"
    r"RFC822\.SIZE\s*(?P<size>\d+).*?"
    r"UID\s*(?P<uid>\d+)",
    re.I,
)
_INTERNALDATE_FMT = "%d-%b-%Y %H:%M:%S %z"


class SyncService:
    def __init__(self, session: AsyncSession, account: MailAccount, user_id: uuid.UUID):
        self.session = session
        self.account = account
        self.user_id = user_id

    async def sync_all(self, headers_limit: int = 200) -> dict:
        """Full sync: folders + messages for INBOX (latest N)."""
        password = decrypt_credential(self.account.encrypted_password) if self.account.encrypted_password else ""
        client = ImapClient(
            host=self.account.host,
            port=self.account.imap_port,
            username=self.account.username,
            password=password,
            security=self.account.imap_security,
        )
        stats = {"folders": 0, "messages": 0, "errors": []}
        try:
            await client.connect()
            caps = await client.capabilities()
            self.account.capabilities = ",".join(caps)
            self.account.status = "connected"
            self.account.status_message = None

            folders = await client.list_folders()
            for delim, name in folders:
                await self._upsert_folder(name, delim)
                stats["folders"] += 1

            result = await self.session.exec(
                select(Folder).where(
                    Folder.account_id == self.account.id,
                    Folder.name == "INBOX",
                )
            )
            inbox_folder = result.first()
            if inbox_folder:
                await client.select("INBOX")
                status = await client.status("INBOX", "(UIDNEXT UIDVALIDITY MESSAGES UNSEEN)")
                raw_status = " ".join(status.get("data", []))
                m = re.search(r"UIDVALIDITY\s+(\d+)", raw_status)
                if m:
                    inbox_folder.uidvalidity = m.group(1)
                m = re.search(r"UIDNEXT\s+(\d+)", raw_status)
                if m:
                    try:
                        inbox_folder.uidnext = int(m.group(1))
                    except ValueError:
                        pass
                self.session.add(inbox_folder)

                stats["messages"] = await self._sync_folder(client, inbox_folder, headers_limit)
                await self._update_folder_counts(inbox_folder)

            self.account.last_sync_at = datetime.now(timezone.utc)
            self.session.add(self.account)
            await self.session.commit()
            await self._publish("sync:complete", {"folders": stats["folders"], "messages": stats["messages"]})
            return stats
        except Exception as exc:  # noqa: BLE001
            self.account.status = "error"
            self.account.status_message = str(exc)
            self.session.add(self.account)
            await self.session.commit()
            stats["errors"].append(str(exc))
            await self._publish("sync:error", {"message": str(exc)})
            return stats
        finally:
            await client.logout()

    async def _publish(self, event_type: str, payload: dict) -> None:
        from app.core.notify import publish_user_event

        await publish_user_event(
            self.user_id,
            {"type": event_type, "account_id": str(self.account.id), **payload},
        )

    async def _upsert_folder(self, name: str, delimiter: Optional[str]) -> Folder:
        result = await self.session.exec(
            select(Folder).where(
                Folder.account_id == self.account.id,
                Folder.name == name,
            )
        )
        folder = result.first()
        if not folder:
            folder = Folder(
                user_id=self.user_id,
                account_id=self.account.id,
                name=name,
                delimiter=delimiter,
                subscribed=True,
            )
            self.session.add(folder)
            await self.session.flush()
        return folder

    async def _sync_folder(self, client: ImapClient, folder: Folder, limit: int) -> int:
        """Fetch the latest `limit` messages (headers + body) and upsert them."""
        assert client._imap is not None
        typ, data = await client._imap.search("ALL")
        if typ != "OK" or not data:
            return 0
        raw_uids = data[0].split()
        if not raw_uids:
            return 0
        last_uids = raw_uids[-limit:]
        uid_set = ",".join(u.decode() if isinstance(u, bytes) else str(u) for u in last_uids)
        typ, data = await client._imap.uid(
            "fetch", uid_set, "(UID FLAGS INTERNALDATE RFC822.SIZE BODY.PEEK[])"
        )
        if typ != "OK":
            return 0

        current: dict = {}
        parsed_count = 0
        for item in data:
            if isinstance(item, (bytes, str)):
                line = item.decode(errors="replace") if isinstance(item, bytes) else item
                match = _FETCH_RE.search(line)
                if match:
                    # flush previous pending message if body never arrived
                    if current:
                        await self._upsert_message(folder, current)
                        parsed_count += 1
                        current = {}
                    current = self._parse_fetch_header(match)
                elif line.strip() == ")":
                    if current.get("raw"):
                        await self._upsert_message(folder, current)
                        parsed_count += 1
                    current = {}
            elif isinstance(item, (bytearray, memoryview)) and current:
                current["raw"] = bytes(item)
        if current.get("raw") or current.get("uid"):
            await self._upsert_message(folder, current)
            parsed_count += 1
        await self.session.commit()
        return parsed_count

    def _parse_fetch_header(self, match: re.Match) -> dict:
        flags_raw = match.group("flags") or ""
        flags = [f for f in flags_raw.split() if f]
        try:
            internal_date = datetime.strptime(match.group("internaldate"), _INTERNALDATE_FMT)
        except Exception:
            internal_date = None
        return {
            "uid": int(match.group("uid")),
            "flags": flags,
            "internal_date": internal_date,
            "size": int(match.group("size")),
        }

    async def _upsert_message(self, folder: Folder, parsed: dict) -> None:
        raw = parsed.get("raw") or b""
        content = parse_message(raw) if raw else {}
        uid = parsed["uid"]

        result = await self.session.exec(
            select(Message).where(
                Message.account_id == self.account.id,
                Message.folder_id == folder.id,
                Message.uid == uid,
            )
        )
        msg = result.first()
        if not msg:
            msg = Message(
                user_id=self.user_id,
                account_id=self.account.id,
                folder_id=folder.id,
                uid=uid,
            )

        msg.uid = uid
        msg.flags = parsed.get("flags") or []
        msg.size = parsed.get("size") or 0
        msg.internal_date = parsed.get("internal_date")
        msg.received_at = parsed.get("internal_date")
        msg.message_id = content.get("message_id")
        msg.in_reply_to = content.get("in_reply_to")
        msg.references = content.get("references")
        msg.from_json = content.get("from")
        msg.to_json = content.get("to")
        msg.cc_json = content.get("cc")
        msg.bcc_json = content.get("bcc")
        msg.subject = content.get("subject")
        msg.snippet = content.get("snippet")
        msg.body_text = content.get("body_text")
        msg.body_html = content.get("body_html")
        msg.has_attachments = bool(content.get("has_attachments"))
        self.session.add(msg)

    async def _update_folder_counts(self, folder: Folder) -> None:
        result = await self.session.exec(
            select(Message).where(Message.folder_id == folder.id)
        )
        messages = result.all()

        def _is_seen(msg: Message) -> bool:
            flags = msg.flags or []
            return any("Seen" in str(f) for f in flags)

        folder.message_count = len(messages)
        folder.unread_count = sum(0 if _is_seen(m) else 1 for m in messages)
        folder.synced = True
        self.session.add(folder)
        await self.session.commit()


# kept for backwards compatibility with imports elsewhere
async def sync_account_now(*args, **kwargs):  # pragma: no cover
    raise NotImplementedError("Use SyncService")
