"""Mail ingestion pipeline.

Single path for all providers::

    receive -> parse -> authenticate -> dedupe -> route -> thread ->
    store -> index -> notify

The pipeline is provider-agnostic: it consumes ``RawMessage`` objects from any
:class:`features.mail.providers.base.InboundProvider` and produces stored
:class:`features.mail.models.MailMessage` rows.

Running the pipeline::

    from features.mail.ingestion.pipeline import run_pipeline
    await run_pipeline()
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from core.database import get_session
from features.mail import service
from features.mail.models import MailMessage
from features.mail.providers.base import InboundProvider, RawMessage
from features.mail.providers import get_provider
from features.mail.settings import get_mail_settings

logger = logging.getLogger(__name__)


def _content_hash(raw: RawMessage) -> str:
    """Content-based hash for dedupe when Message-ID is missing."""
    parts = [
        raw.from_email or "",
        raw.subject or "",
        raw.body_text or "",
        str(raw.received_at) if raw.received_at else "",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:40]


import json

def _group_for_alias(
    settings: Any, alias: Optional[str]
) -> Optional[str]:
    """Determine which group an alias belongs to from MAIL_MAILBOXES_JSON."""
    if not alias:
        return None
    try:
        mailboxes = json.loads(settings.mail_mailboxes_json or "{}")
    except json.JSONDecodeError:
        return None
    for group, cfg in mailboxes.items():
        sections = cfg.get("sections", {}) or {}
        for section_name, section_alias in sections.items():
            if section_alias == alias:
                return group
    return None


async def run_pipeline(
    provider: Optional[InboundProvider] = None,
    session: Optional[Session] = None,
) -> dict[str, int]:
    """Run one ingestion cycle.

    Returns a dict of counts: ``received``, ``deduped``, ``routed``,
    ``quarantined``, ``stored``, ``errors``.
    """
    settings = get_mail_settings()
    provider = provider or get_provider()
    counts = {"received": 0, "deduped": 0, "routed": 0, "quarantined": 0,
              "stored": 0, "errors": 0}

    close_session = session is None
    if session is None:
        session = next(get_session())

    try:
        raw_messages = await provider.fetch_new()
        counts["received"] = len(raw_messages)

        for raw in raw_messages:
            try:
                _process_one(session, raw, settings, counts)
            except Exception as exc:  # noqa: BLE001 - one bad mail must not stop the run
                logger.warning("Failed to ingest message %s: %s", raw.message_id, exc)
                counts["errors"] += 1

        session.commit()
    finally:
        if close_session:
            session.close()

    await provider.mark_fetched([m.message_id for m in raw_messages if m.message_id])
    logger.info("Ingestion cycle complete: %s", counts)
    return counts


def _process_one(
    session: Session, raw: RawMessage, settings: Any, counts: dict[str, int]
) -> None:
    """Process a single raw message through the pipeline."""
    message_id = raw.message_id or _content_hash(raw)

    # ---- Dedupe ----------------------------------------------------------
    existing = session.exec(
        select(MailMessage).where(MailMessage.message_id == message_id)
    ).first()
    if existing is not None:
        counts["deduped"] += 1
        return

    # ---- Authenticate ----------------------------------------------------
    is_quarantined = False
    if settings.require_auth_for_routing and not settings.is_dummy:
        failed = any(
            (raw.auth_spf or "").lower() == "fail"
            or (raw.auth_dkim or "").lower() == "fail"
            or (raw.auth_dmarc or "").lower() == "fail"
        )
        if failed:
            is_quarantined = True
            counts["quarantined"] += 1

    # ---- Route (sender decides, never the receiving address) -------------
    group = _group_for_alias(settings, raw.delivered_to)
    if group is None:
        # No group owns this alias: file under ug as default, or skip?
        # For safety, use the first configured group.
        try:
            mailboxes = json.loads(settings.mail_mailboxes_json or "{}")
        except json.JSONDecodeError:
            mailboxes = {}
        group = list(mailboxes.keys())[0] if mailboxes else "ug"
    filing = service.filing_for(session, group, raw.from_email)
    counts["routed"] += 1

    # ---- Thread ----------------------------------------------------------
    thread_id = service.thread_key(raw.subject)

    # ---- Store -----------------------------------------------------------
    message = service.store_message(
        session,
        group=group,
        section=filing.section,
        cluster_id=filing.cluster_id,
        thread_id=thread_id,
        intake_address=raw.delivered_to,
        from_email=raw.from_email or "",
        from_name=raw.from_name,
        to_email=raw.to[0] if raw.to else None,
        subject=raw.subject,
        body_text=raw.body_text,
        body_html=raw.body_html,
        received_at=raw.received_at,
        message_id=message_id,
        direction="inbox",
        is_quarantined=is_quarantined,
        auth_spf=raw.auth_spf,
        auth_dkim=raw.auth_dkim,
        auth_dmarc=raw.auth_dmarc,
        auth_summary=_auth_summary(raw),
        attachments=raw.attachments,
        labels=[],
    )
    counts["stored"] += 1

    # ---- Index / notify --------------------------------------------------
    # Full-text search index and notification (SSE/bell) are Phase 6/8.
    # For now, storing is enough; the list endpoint reads from the DB.


def _auth_summary(raw: RawMessage) -> Optional[str]:
    parts = []
    if raw.auth_spf:
        parts.append(f"spf={raw.auth_spf}")
    if raw.auth_dkim:
        parts.append(f"dkim={raw.auth_dkim}")
    if raw.auth_dmarc:
        parts.append(f"dmarc={raw.auth_dmarc}")
    return ", ".join(parts) or None
