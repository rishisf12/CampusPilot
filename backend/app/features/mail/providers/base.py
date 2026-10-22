"""Mail provider abstractions.

A provider is how mail gets into and out of the system. The default (and
only shipping) provider is ``dummy`` - a simulated mail server used for
development and testing. Real providers (IMAP, Microsoft Graph, Gmail API,
webhook) ship as documented interfaces with an explicit "not implemented yet"
error, so switching ``MAIL_PROVIDER`` is configuration only.

Providers never touch routing or storage themselves. They produce and consume
``RawMessage`` / ``OutgoingMessage`` dataclasses; the ingestion pipeline and
the compose service own everything downstream.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


#: When true, the dummy provider simulates failed-auth mail so the quarantine
#: path can be exercised without a real mail server.
DUMMY_FAIL_AUTH = os.environ.get("MAIL_DUMMY_FAIL_AUTH", "0") in ("1", "true", "yes", "on")


@dataclass
class RawMessage:
    """A message as received from an inbound provider, before any processing.

    Fields are provider-normalised but otherwise uninterpreted: the ingestion
    pipeline parses headers, authenticates, dedupes, routes, threads and
    stores.
    """

    #: Provider-assigned identifier for deduplication.
    message_id: Optional[str] = None
    #: All recipient addresses (To + Cc + Bcc + Delivered-To aliases).
    to: list[str] = field(default_factory=list)
    #: The alias the mail was actually delivered to (one of the six aliases).
    delivered_to: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    received_at: Optional[datetime] = None
    #: Raw headers, as the provider gave them.
    headers: dict[str, list[str]] = field(default_factory=dict)
    #: Attachments as {filename, content_type, content_base64, size}.
    attachments: list[dict[str, Any]] = field(default_factory=list)
    #: Authentication results, when the provider supplies them.
    auth_spf: Optional[str] = None
    auth_dkim: Optional[str] = None
    auth_dmarc: Optional[str] = None


@dataclass
class OutgoingMessage:
    """A message ready to be sent by an outbound provider."""

    from_email: str
    from_name: Optional[str] = None
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    subject: str = ""
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    attachments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SendResult:
    """Result of sending a message."""

    provider_message_id: Optional[str] = None
    status: str = "sent"   # sent | queued | failed
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Provider interfaces
# ---------------------------------------------------------------------------


class InboundProvider:
    """Fetches new inbound mail from a provider."""

    async def fetch_new(self, since: Optional[datetime] = None) -> list[RawMessage]:
        """Return new messages since ``since`` (or all unread if None)."""
        raise NotImplementedError

    async def mark_fetched(self, message_ids: list[str]) -> None:
        """Tell the provider we have processed these messages."""
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        """Return provider health status for the mailbox footer."""
        raise NotImplementedError


class OutboundProvider:
    """Sends outbound mail through a provider."""

    async def send(self, message: OutgoingMessage) -> SendResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type] = {}


def register_provider(name: str, cls: type) -> None:
    """Register a provider class under ``name``."""
    _PROVIDERS[name.lower()] = cls


def get_provider(name: Optional[str] = None):
    """Instantiate the provider named ``name`` (or MAIL_PROVIDER env var)."""
    from features.mail.settings import get_mail_settings

    settings = get_mail_settings()
    name = (name or settings.provider).lower()
    if name not in _PROVIDERS:
        raise ValueError(
            f"Unknown mail provider '{name}'. "
            f"Available: {', '.join(sorted(_PROVIDERS))}"
        )
    return _PROVIDERS[name]()


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)


def register_providers() -> None:
    """Import and register all provider modules."""
    # Import side effects register providers in _PROVIDERS.
    from features.mail.providers import dummy  # noqa: F401
    from features.mail.providers import imap  # noqa: F401
    from features.mail.providers import graph  # noqa: F401
    from features.mail.providers import gmail  # noqa: F401
    from features.mail.providers import webhook  # noqa: F401
