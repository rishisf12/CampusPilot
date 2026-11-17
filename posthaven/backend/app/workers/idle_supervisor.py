from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis

from app.core.config import settings
from app.services.imap_client import ImapClient

USER_CHANNEL_PREFIX = "user:"
LEASE_TTL = 60
LEASE_RENEW_INTERVAL = 30


class IdleSupervisor:
    def __init__(self):
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}
        self._redis: Optional[redis.Redis] = None
        self._running = False

    async def start(self) -> None:
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._running = True
        asyncio.create_task(self._lease_renewer())

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        if self._redis:
            await self._redis.aclose()

    async def _lease_renewer(self) -> None:
        while self._running:
            await asyncio.sleep(LEASE_RENEW_INTERVAL)

    async def _idle_loop(self, account_id: uuid.UUID, host: str, port: int,
                         username: str, password: str, security: str) -> None:
        backoff = 1
        max_backoff = 60
        while self._running:
            client = ImapClient(host, port, username, password, security=security)
            try:
                await client.connect()
                await client.select("INBOX")
                backoff = 1
                async for line in client.idle(timeout=29 * 60):
                    if not self._running:
                        break
                    await self._publish_event(account_id, line)
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            finally:
                await client.logout()

    async def _publish_event(self, account_id: uuid.UUID, line: str) -> None:
        if not self._redis:
            return
        event = {
            "type": "message.new",
            "account_id": str(account_id),
            "payload": {"raw": line},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await self._redis.publish(f"user:{account_id}", str(event))

    def start_account(self, account_id: uuid.UUID, host: str, port: int,
                      username: str, password: str, security: str) -> None:
        if account_id in self._tasks:
            return
        task = asyncio.create_task(
            self._idle_loop(account_id, host, port, username, password, security)
        )
        self._tasks[account_id] = task

    def stop_account(self, account_id: uuid.UUID) -> None:
        task = self._tasks.pop(account_id, None)
        if task:
            task.cancel()


supervisor: Optional[IdleSupervisor] = None


def get_supervisor() -> IdleSupervisor:
    global supervisor
    if supervisor is None:
        supervisor = IdleSupervisor()
    return supervisor
