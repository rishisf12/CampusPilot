"""Gmail API inbound provider - stub."""
from __future__ import annotations

from typing import Any

from features.mail.providers.base import InboundProvider, RawMessage, register_provider


class GmailProvider(InboundProvider):
    """Gmail API provider (stub)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "Gmail provider is not implemented yet. Set MAIL_PROVIDER=dummy "
            "for the simulated server, or implement GmailProvider.fetch_new."
        )

    async def fetch_new(self, since=None) -> list[RawMessage]:  # noqa: ARG002
        raise NotImplementedError("Gmail fetch_new is not implemented")

    async def mark_fetched(self, message_ids: list[str]) -> None:  # noqa: ARG002
        raise NotImplementedError("Gmail mark_fetched is not implemented")

    async def health(self) -> dict[str, Any]:  # noqa: ARG002
        return {"provider": "gmail", "status": "not_implemented"}


register_provider("gmail", GmailProvider)
