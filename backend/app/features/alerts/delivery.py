"""Route an alert incident to the channels its rule names.

The channels are the app's own: email (SMTP), Slack and Discord (a webhook
POST) and Telegram (the bot API). A channel's secrets live in its
`config_json` and **never leave the database** - the delivery reads them,
the tools the scan agent sees do not (see `mcp.alerting`).

A failed delivery is logged and does not fail the evaluation: a broken
webhook must not stop the other channels from being told.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from sqlmodel import Session, select

from features.alerts.models import AlertChannel, AlertIncident, AlertRule

logger = logging.getLogger(__name__)

#: How long a delivery may take. A channel that hangs must not hold the
#: worker.
DELIVERY_TIMEOUT_S = 15.0


def _message(incident: AlertIncident, rule: AlertRule) -> str:
    return (
        f"[{rule.severity.upper()}] {rule.name}\n"
        f"{rule.description or ''}\n"
        f"metric: {rule.metric} = {incident.value} "
        f"(threshold {rule.condition} {rule.threshold})\n"
        f"started: {incident.started_at.isoformat() if incident.started_at else '?'}"
    ).strip()


async def _deliver_email(channel: AlertChannel, subject: str, body: str) -> bool:
    """Send by email, over the app's own SMTP settings."""
    try:
        import aiosmtplib
    except Exception:  # noqa: BLE001 - the dependency is optional at runtime
        logger.warning("aiosmtplib is not installed; email delivery skipped")
        return False

    from core.config import get_settings

    settings = get_settings()
    config = channel.config_json or {}
    recipients = config.get("to") or config.get("recipients") or []
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r for r in recipients if r]
    if not recipients:
        logger.warning("channel %s has no recipients; email skipped", channel.name)
        return False
    if not settings.SMTP_USER:
        # The host has a default, but without a user there is nothing to
        # authenticate with - so this is "not configured", not "try anyway".
        logger.warning("SMTP credentials are not configured; email delivery skipped")
        return False
    try:
        await aiosmtplib.send(
            message=body,
            sender=settings.EMAIL_FROM or None,
            recipients=recipients,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT or 587,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=bool(settings.SMTP_USER),
        )
        return True
    except Exception as exc:  # noqa: BLE001 - one broken channel must not stop the rest
        logger.warning("email delivery to %s failed: %s", channel.name, exc)
        return False


async def _deliver_webhook(
    channel: AlertChannel, subject: str, body: str
) -> bool:
    """Send to a Slack- or Discord-style incoming webhook."""
    config = channel.config_json or {}
    url = config.get("webhook_url") or config.get("url") or ""
    if not url:
        logger.warning("channel %s has no webhook URL; skipped", channel.name)
        return False
    payload = {"text": f"*{subject}*\n{body}"}
    if channel.channel_type == "discord":
        payload = {"content": f"**{subject}**\n{body}"}
    try:
        async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_S) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("webhook delivery to %s failed: %s", channel.name, exc)
        return False


async def _deliver_telegram(channel: AlertChannel, subject: str, body: str) -> bool:
    """Send through the Telegram bot API."""
    config = channel.config_json or {}
    token = config.get("bot_token") or config.get("token") or ""
    chat_id = config.get("chat_id") or ""
    if not token or not chat_id:
        logger.warning("channel %s has no bot token or chat id; skipped", channel.name)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_S) as client:
            response = await client.post(
                url,
                json={"chat_id": chat_id, "text": f"{subject}\n{body}"},
            )
            response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram delivery to %s failed: %s", channel.name, exc)
        return False


async def deliver(
    session: Session,
    incident: AlertIncident,
    rule: AlertRule,
) -> list[dict[str, Any]]:
    """Route one incident to the rule's channels.

    Returns what was attempted, and whether it worked - the caller logs it;
    a failed channel never stops the others.
    """
    channel_ids = list(rule.channels or [])
    if not channel_ids:
        return []
    channels = session.exec(
        select(AlertChannel).where(
            AlertChannel.id.in_(channel_ids),
            AlertChannel.enabled.is_(True),
        )
    ).all()

    subject = f"{rule.severity.upper()}: {rule.name}"
    body = _message(incident, rule)
    results: list[dict[str, Any]] = []
    for channel in channels:
        kind = (channel.channel_type or "").lower()
        if kind == "email":
            ok = await _deliver_email(channel, subject, body)
        elif kind in {"slack", "discord", "webhook"}:
            ok = await _deliver_webhook(channel, subject, body)
        elif kind == "telegram":
            ok = await _deliver_telegram(channel, subject, body)
        else:
            logger.warning("unknown channel type %r on %s", kind, channel.name)
            ok = False
        results.append({"channel": channel.name, "type": kind, "delivered": ok})
    return results
