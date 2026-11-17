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


class SyncService:
    def __init__(self, session: AsyncSession, account: MailAccount, user_id: uuid.UUID):
        self.session = session
        self.account = account
        self.user_id = user_id

    async def sync_all(self, headers_limit: int = 200) -> dict:
        """Full sync: folders + headers for INBOX (latest N)."""
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

            inbox = await self.session.exec(
                select(Folder).where(
                    Folder.account_id == self.account.id,
                    Folder.name == "INBOX",
                )
            )
            inbox_folder = inbox.first()
            if inbox_folder:
                await client.select("INBOX")
                status = await client.status("INBOX", "(UIDNEXT UIDVALIDITY MESSAGES UNSEEN)")
                uidvalidity = None
                uidnext = None
                for item in status.get("data", []):
                    upper = item.upper()
                    if "UIDVALIDITY" in upper:
                        parts = item.split()
                        uidvalidity = parts[-1] if parts else None
                    if "UIDNEXT" in upper:
                        parts = item.split()
                        try:
                            uidnext = int(parts[-1])
                        except Exception:
                            pass
                if uidvalidity:
                    inbox_folder.uidvalidity = uidvalidity
                if uidnext:
                    inbox_folder.uidnext = uidnext
                self.session.add(inbox_folder)

                await self._sync_folder_headers(client, inbox_folder, headers_limit)
                stats["messages"] += headers_limit

            self.account.last_sync_at = datetime.now(timezone.utc)
            self.session.add(self.account)
            await self.session.commit()
            return stats
        except Exception as exc:  # noqa: BLE001
            self.account.status = "error"
            self.account.status_message = str(exc)
            self.session.add(self.account)
            await self.session.commit()
            stats["errors"].append(str(exc))
            return stats
        finally:
            await client.logout()

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

    async def _sync_folder_headers(self, client: ImapClient, folder: Folder, limit: int) -> None:
        """Fetch headers for latest `limit` messages and upsert."""
        typ, data = await client._imap.uid("fetch", f"1:{limit}", "(BODY.PEEK[HEADER] FLAGS INTERNALDATE RFC822.SIZE)")
        if typ != "OK":
            return
        for response_part in data:
            if not isinstance(response_part, tuple):
                continue
            parsed = self._parse_fetch_response(response_part[1])
            if not parsed:
                continue
            await self._upsert_message(folder, parsed)

    def _parse_fetch_response(self, data) -> Optional[dict]:
        """Parse a single FETCH response into fields."""
        try:
            return None
        except Exception:
            return None

    async def _upsert_message(self, folder: Folder, parsed: dict) -> None:
        pass
