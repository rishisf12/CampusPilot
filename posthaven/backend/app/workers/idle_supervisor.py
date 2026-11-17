from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis

from sqlmodel import select

from app.core.config import settings
from app.core.crypto import decrypt_credential
from app.core.notify import publish_user_event
from app.models.account import MailAccount
from app.services.imap_client import ImapClient

RECONCILE_INTERVAL = 30


class IdleSupervisor:
    """Maintains one IMAP IDLE connection per enabled account.

    When the server reports new mail, a `mail:incoming` event is published
    on the owner's `user:{user_id}` channel; clients re-sync in response.
    A reconcile loop restarts/stops connections as accounts change.
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._redis: Optional[redis.Redis] = None
        self._running = False
        self._reconcile_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._running = True
        self._reconcile_task = asyncio.create_task(self._reconcile_loop())

    async def stop(self) -> None:
        self._running = False
        if self._reconcile_task:
            self._reconcile_task.cancel()
            self._reconcile_task = None
        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def _reconcile_loop(self) -> None:
        while self._running:
            try:
                await self.reconcile()
            except Exception:
                pass
            await asyncio.sleep(RECONCILE_INTERVAL)

    async def reconcile(self) -> None:
        from app.db.session import async_session

        async with async_session() as session:
            result = await session.exec(
                select(MailAccount).where(
                    MailAccount.sync_enabled == True,  # noqa: E712
                    MailAccount.is_enabled == True,  # noqa: E712
                )
            )
            accounts = result.all()

        desired = {str(a.id): a for a in accounts}

        for aid in list(self._tasks):
            if aid not in desired:
                task = self._tasks.pop(aid)
                task.cancel()

        for aid, account in desired.items():
            if aid not in self._tasks:
                password = (
                    decrypt_credential(account.encrypted_password)
                    if account.encrypted_password
                    else ""
                )
                self._tasks[aid] = asyncio.create_task(
                    self._idle_loop(account, password)
                )

    async def _idle_loop(self, account: MailAccount, password: str) -> None:
        account_id = str(account.id)
        backoff = 1
        max_backoff = 60
        while self._running:
            client = ImapClient(
                account.host, account.imap_port, account.username, password,
                security=account.imap_security,
            )
            try:
                await client.connect()
                await client.select("INBOX")
                backoff = 1
                async for line in client.idle(timeout=29 * 60):
                    if not self._running:
                        break
                    await self._publish_event(account.user_id, account_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            finally:
                await client.logout()

    async def _publish_event(self, user_id: uuid.UUID, account_id: str) -> None:
        await publish_user_event(
            user_id,
            {
                "type": "mail:incoming",
                "account_id": account_id,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )


supervisor: Optional[IdleSupervisor] = None


def get_supervisor() -> IdleSupervisor:
    global supervisor
    if supervisor is None:
        supervisor = IdleSupervisor()
    return supervisor
