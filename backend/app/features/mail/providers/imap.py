"""IMAP inbound provider - stub.

Real IMAP support is configuration away: implement ``fetch_new`` against an
IMAP server and register it here. Until then the class exists so
``MAIL_PROVIDER=imap`` is a valid value that fails with a clear error at
runtime rather than import time.
"""
from __future__ import annotations

from typing import Any

from features.mail.providers.base import InboundProvider, RawMessage, register_provider


class ImapProvider(InboundProvider):
    """IMAP provider (stub)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "IMAP provider is not implemented yet. Set MAIL_PROVIDER=dummy "
            "for the simulated server, or implement ImapProvider.fetch_new."
        )

    async def fetch_new(self, since=None) -> list[RawMessage]:  # noqa: ARG002
        raise NotImplementedError("IMAP fetch_new is not implemented")

    async def mark_fetched(self, message_ids: list[str]) -> None:  # noqa: ARG002
        raise NotImplementedError("IMAP mark_fetched is not implemented")

    async def health(self) -> dict[str, Any]:  # noqa: ARG002
        return {"provider": "imap", "status": "not_implemented"}


register_provider("imap", ImapProvider)
