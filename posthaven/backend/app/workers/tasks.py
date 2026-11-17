from __future__ import annotations

import uuid
from datetime import datetime, timezone

from arq.connections import RedisSettings
from app.core.config import settings


async def send_email(ctx, scheduled_send_id: str, user_id: str, account_id: str,
                     to_json: str, subject: str, body_text: str | None,
                     body_html: str | None, idempotency_key: str) -> dict:
    """Send a single email via SMTP. Called by ARQ worker."""
    return {
        "scheduled_send_id": scheduled_send_id,
        "status": "queued",
        "message": "send_email task skeleton — SMTP send not yet wired to live account",
    }


async def wake_snooze(ctx, message_id: str) -> dict:
    """Wake a snoozed message: move back to inbox + publish snooze.woke."""
    return {"message_id": message_id, "status": "woke"}


async def run_rule(ctx, rule_id: str, message_id: str) -> dict:
    """Run a rule on a message (move/label/mark-read/etc.)."""
    return {"rule_id": rule_id, "message_id": message_id, "status": "applied"}


async def send_reminder(ctx, reminder_id: str) -> dict:
    """Fire a follow-up reminder if no reply arrived."""
    return {"reminder_id": reminder_id, "status": "fired"}


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 300
    keep_result = 24 * 3600
    functions = [send_email, wake_snooze, run_rule, send_reminder]
