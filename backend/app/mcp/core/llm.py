"""The one outbound path from this backend to a language model.

Every model call made by the agent tooling goes through `chat()` here. That
gives the egress rules a single place to live:

1. **The job is checked first.** `validate_job` refuses a non-allowlisted
   provider and refuses a telemetry job whose egress gate is not wired — and
   it does so *before* a client is built, so a refused job sends nothing.
2. **The payload is redacted again.** Tool output was already redacted on the
   way out of the registry; redacting the assembled prompt is the second lock
   on the same door. Defense in depth is not paranoia when the context can
   contain a student's email.
3. **Every attempt is audited.** One row per outbound request — including the
   ones that failed and the ones that were failed over — with `sent_to`,
   `bytes_out`, `redactions_applied` and `redaction_salt`. If a byte left the
   building, there is a row that says where it went.

The provider clients are not new: `llms.get_client()` returns the *existing*
OppFeed clients, so there is one HTTP implementation per provider in the
codebase, not two.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Sequence

from sqlmodel import Session

from llms import LLMConfigError, get_client
from mcp.core import redact as _redaction
from mcp.core.jobs import JobRefused, validate_job
from mcp.core.registry import write_audit

logger = logging.getLogger(__name__)

#: Failover order for a job: NVIDIA NIM first, OpenRouter's free models as
#: the fallback. Only allowlisted providers appear here.
DEFAULT_FALLBACKS: tuple[str, ...] = ("nvidia_nim", "openrouter")

#: The tool name recorded on the audit row of an outbound request. Same
#: `llm.*` family as the Stage 2 narrative row, so "what left the building"
#: is one filtered query.
AUDIT_TOOL = "llm.request"


class LLMRequestError(RuntimeError):
    """Every allowlisted provider failed for this request."""


def _redacted_messages(
    messages: Sequence[dict[str, Any]], salt: str
) -> tuple[list[dict[str, Any]], int]:
    """Mask the prompt body. Returns (messages, redactions applied).

    Structured values go through the walker (which pseudonymizes id-keyed
    fields); strings are counted by *occurrence*, so the audit column says how
    many masks were applied rather than how many strings changed.
    """
    out: list[dict[str, Any]] = []
    total = 0
    for message in messages:
        redacted: dict[str, Any] = {}
        for key, value in message.items():
            if isinstance(value, str):
                masked, count = _redaction.redact_counted(value)
                redacted[key] = masked
                total += count
            else:
                masked, count = _redaction.redact_value(value, salt)
                redacted[key] = masked
                total += count
        out.append(redacted)
    return out, total


async def chat(
    session: Session,
    *,
    job_kind: str,
    provider: str,
    messages: Sequence[dict[str, Any]],
    scan_id: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
    fallbacks: Sequence[str] = DEFAULT_FALLBACKS,
    client: Any | None = None,
) -> Any:
    """Send one chat request through the gate, with failover and an audit row.

    `client` exists for tests and for callers that already hold a client
    (the OppFeed agent does). When it is None the provider client is built
    from the reused OppFeed implementation.

    Raises `JobRefused` (nothing sent), `LLMConfigError` (no usable
    provider) or `LLMRequestError` (every provider failed).
    """
    salt = _redaction.salt_for(scan_id)

    # 1. The gate. A refusal here means no client was built and nothing was
    #    sent - that is the whole point of checking before building.
    validate_job(
        job_kind=job_kind,
        provider=provider,
        scan_id=scan_id,
        salt=salt,
        session=session,
    )

    # 2. Redact the prompt body.
    safe_messages, redactions = _redacted_messages(messages, salt)

    chain = [provider] + [p for p in fallbacks if p != provider]
    last_error: Exception | None = None

    for attempt_provider in chain:
        try:
            active = client if client is not None else get_client(attempt_provider)
        except LLMConfigError as exc:
            # An unconfigured provider is not a request - record nothing sent.
            last_error = exc
            logger.warning("provider %s unavailable: %s", attempt_provider, exc)
            continue

        if model and hasattr(active, "_model"):
            active._model = model  # the reused clients keep their model here

        payload = {
            "model": getattr(active, "default_model", model) or model,
            "messages": safe_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        bytes_out = len(json.dumps(payload, default=str).encode("utf-8"))

        started = time.monotonic()
        try:
            response = await active.chat(
                safe_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception as exc:  # noqa: BLE001 - a provider can fail any way
            duration_ms = int((time.monotonic() - started) * 1000)
            write_audit(
                session,
                scan_id=scan_id,
                tool=AUDIT_TOOL,
                args={"provider": attempt_provider, "model": model},
                metric_key=None,
                duration_ms=duration_ms,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                sent_to=attempt_provider,
                redactions_applied=redactions,
                bytes_out=bytes_out,
                redaction_salt=salt,
            )
            last_error = exc
            logger.warning("provider %s failed: %s", attempt_provider, exc)
            continue

        duration_ms = int((time.monotonic() - started) * 1000)
        write_audit(
            session,
            scan_id=scan_id,
            tool=AUDIT_TOOL,
            args={"provider": attempt_provider, "model": model},
            metric_key=None,
            duration_ms=duration_ms,
            ok=True,
            error=None,
            sent_to=attempt_provider,
            redactions_applied=redactions,
            bytes_out=bytes_out,
            redaction_salt=salt,
        )
        return response

    raise LLMRequestError(
        f"every provider in {chain} failed for scan {scan_id!r}: {last_error}"
    )
