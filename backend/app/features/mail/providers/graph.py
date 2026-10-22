"""Microsoft Graph inbound provider - stub."""
from __future__ import annotations

from typing import Any

from features.mail.providers.base import InboundProvider, RawMessage, register_provider


class GraphProvider(InboundProvider):
    """Microsoft Graph provider (stub)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "Graph provider is not implemented yet. Set MAIL_PROVIDER=dummy "
            "for the simulated server, or implement GraphProvider.fetch_new."
        )

    async def fetch_new(self, since=None) -> list[RawMessage]:  # noqa: ARG002
        raise NotImplementedError("Graph fetch_new is not implemented")

    async def mark_fetched(self, message_ids: list[str]) -> None:  # noqa: ARG002
        raise NotImplementedError("Graph mark_fetched is not implemented")

    async def health(self) -> dict[str, Any]:  # noqa: ARG002
        return {"provider": "graph", "status": "not_implemented"}


register_provider("graph", GraphProvider)
