"""Webhook inbound provider - stub.

A webhook provider receives pushed mail via an HTTP endpoint. The FastAPI
route lives in routes.py; this class is the inbound provider implementation
that the pipeline calls. Until the webhook route is wired up, this is a stub.
"""
from __future__ import annotations

from typing import Any

from features.mail.providers.base import InboundProvider, RawMessage, register_provider


class WebhookProvider(InboundProvider):
    """Webhook provider (stub)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "Webhook provider is not implemented yet. Set MAIL_PROVIDER=dummy "
            "for the simulated server, or implement WebhookProvider.fetch_new."
        )

    async def fetch_new(self, since=None) -> list[RawMessage]:  # noqa: ARG002
        raise NotImplementedError("Webhook fetch_new is not implemented")

    async def mark_fetched(self, message_ids: list[str]) -> None:  # noqa: ARG002
        raise NotImplementedError("Webhook mark_fetched is not implemented")

    async def health(self) -> dict[str, Any]:  # noqa: ARG002
        return {"provider": "webhook", "status": "not_implemented"}


register_provider("webhook", WebhookProvider)
