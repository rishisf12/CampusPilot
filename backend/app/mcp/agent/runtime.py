"""The scan-agent runtime: tools in, a reconciled verdict out.

The loop is short and every step of it is checkable:

1. **Ask the tools.** The subsection's own tools run through the registry, so
   scoping, the timeout and the row cap are enforced server-side, and the
   egress gate redacts their answers before the model sees them.
2. **Ask the model.** The SCAN-AGENT.md §1 system prompt, the tool output and
   the §2 schema. The model returns JSON; nothing else is accepted.
3. **Reconcile.** Every number the model cited is checked against the audit
   trail. A number no tool produced fails the scan.
4. **Retry once, then fail honestly.** A failed reconciliation is retried at a
   lower temperature. If it fails again the scan is stored as `error` with the
   reason - never as `healthy`, and never with an unverified finding.

Nothing here acts on the model's advice. The result is a report; the reactor
(Phase 6) is a different component with a different contract.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from sqlmodel import Session

from features.monitoring.api.schemas import (
    Confidence,
    Metric,
    ScanResult,
    Status,
)
from features.monitoring.domain.models import ScanResult as ScanResultRow
from features.monitoring.domain.models import StatusTransition
from mcp.agent.prompts import SUBSECTION_PROMPTS, load_system_prompt
from mcp.agent.reconcile import ReconcileError, reconcile

logger = logging.getLogger(__name__)

#: Which tools each subsection asks, and with what arguments. The registry
#: enforces the scoping as well - this map only says what a good question
#: looks like.
SUBSECTION_TOOLS: dict[str, tuple[tuple[str, dict[str, Any]], ...]] = {
    "A_W_HEALTH": (
        ("telemetry_health", {"days": 7, "platform": "web"}),
        ("p95_latency_window", {"hours": 6, "platform": "web"}),
        ("health_uptime_pct", {"window_hours": 24, "platform": "web"}),
    ),
    "A_A_HEALTH": (
        ("telemetry_health", {"days": 7, "platform": "android"}),
        ("p95_latency_window", {"hours": 6, "platform": "android"}),
        ("crash_clusters", {"days": 7, "platform": "android"}),
    ),
    "B_W_ACTIVITY": (("daily_active_users", {"window_days": 7, "platform": "web"}),),
    "B_A_ACTIVITY": (("daily_active_users", {"window_days": 7, "platform": "android"}),),
    "C_W_SECURITY": (
        ("security_signals", {"days": 7}),
        ("failed_logins_by_hour", {"hours": 24, "platform": "web"}),
    ),
    "C_A_SECURITY": (
        ("security_signals", {"days": 7}),
        ("failed_logins_by_hour", {"hours": 24, "platform": "android"}),
    ),
    "D_W_FEEDBACK": (("feedback_themes_top5", {"days": 7}),),
    "D_A_FEEDBACK": (("feedback_themes_top5", {"days": 7}),),
}

#: The JSON shape the model must return (a trimmed view of §2 - the schema
#: itself is the authority, this is a reminder in the prompt).
_SCHEMA_HINT = {
    "schema_version": 1,
    "status": "healthy | warning | critical | error",
    "summary": "2-4 sentences",
    "findings": [
        {
            "title": "...",
            "severity": "info | warning | critical",
            "evidence": [
                {
                    "metric": "<the tool's metric_key, optionally with a dotted path>",
                    "value": 0.0,
                    "unit": "ms | pct | count | hours",
                    "window": "24h",
                    "source": "<tool name>",
                }
            ],
        }
    ],
    "root_causes": ["..."],
    "recommended_actions": [
        {"action": "<one of the allowed actions>", "priority": 1, "detail": "..."}
    ],
    "confidence": {"level": "low | medium | high", "missing_data": [], "tools_failed": []},
}

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

#: A chat callable: given the messages, return the model's text (or a parsed
#: dict). Injected in tests; the default goes through the egress-gated
# gateway.
ChatFn = Callable[[list[dict[str, Any]]], Awaitable[Any]]


def _parse_json(raw: Any) -> dict[str, Any]:
    """Pull a JSON object out of whatever the model returned."""
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model output is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    return data


def _default_chat(
    session: Session,
    *,
    provider: str,
    scan_id: str,
    model: str | None,
) -> ChatFn:
    """The default transport: the egress-gated gateway, telemetry job kind.

    A closure, not a global: the session, the provider and the scan id belong
    to one call, and two scans running side by side must not share them.
    """

    async def chat(messages: list[dict[str, Any]]) -> Any:
        from mcp.core.llm import chat as gateway_chat

        response = await gateway_chat(
            session,
            job_kind="telemetry",
            provider=provider,
            messages=messages,
            scan_id=scan_id,
            model=model,
        )
        return getattr(response, "text", response)

    return chat


def _collect_tools(
    session: Session,
    subsection: str,
    scan_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run the subsection's tools. Returns (outputs, failed tool names)."""
    from mcp.core.registry import ToolError, run_tool
    from mcp.monitoring import REGISTRY

    outputs: list[dict[str, Any]] = []
    failed: list[str] = []
    for name, args in SUBSECTION_TOOLS.get(subsection, ()):  # type: ignore[arg-type]
        try:
            result = run_tool(
                session,
                REGISTRY,
                scan_id=scan_id,
                subsection=subsection,
                name=name,
                args=args,
            )
        except ToolError as exc:
            failed.append(name)
            logger.warning("tool %s failed for %s: %s", name, subsection, exc)
            continue
        outputs.append(
            {
                "tool": name,
                "metric_key": result.metric_key,
                "data": result.data,
            }
        )
    return outputs, failed


def _error_result(
    scan_id: str,
    subsection: str,
    reason: str,
    *,
    tools_failed: Optional[list[str]] = None,
    missing_data: Optional[list[str]] = None,
) -> ScanResult:
    """An honest failure: `error` status, no findings, the reason included."""
    return ScanResult(
        scan_id=scan_id,
        subsection=subsection,  # type: ignore[arg-type]
        status=Status.ERROR,
        summary=(
            f"The scan could not be completed: {reason}. No finding is "
            "reported, because an unverified finding is worse than none."
        ),
        findings=[],
        root_causes=[],
        recommended_actions=[],
        confidence=Confidence(
            level="low",
            missing_data=missing_data or [],
            tools_failed=tools_failed or [],
        ),
    )


def _store(
    session: Session,
    result: ScanResult,
    *,
    model: str,
    duration_ms: int,
    window_start: datetime,
    window_end: datetime,
) -> None:
    """Persist the verdict and the status transition."""
    session.add(
        ScanResultRow(
            scan_id=result.scan_id,
            subsection=result.subsection,
            status=result.status.value,
            summary=result.summary,
            findings=[f.model_dump() for f in result.findings],
            root_causes=result.root_causes,
            actions=[a.model_dump() for a in result.recommended_actions],
            confidence=result.confidence.model_dump(),
            window_start=window_start,
            window_end=window_end,
            duration_ms=duration_ms,
            model=model,
        )
    )
    session.add(
        StatusTransition(
            subsection=result.subsection,
            from_status="healthy",
            to_status=result.status.value,
            scan_id=result.scan_id,
            at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.commit()


async def run_scan(
    session: Session,
    *,
    subsection: str,
    scan_id: str,
    provider: str = "nvidia_nim",
    model: str | None = None,
    temperature: float = 0.2,
    chat: ChatFn | None = None,
    store: bool = True,
    propose_actions: bool = True,
) -> ScanResult:
    """Run one subsection's scan and return its reconciled verdict.

    `chat` is the seam for tests and for a caller that already holds a
    transport. When it is None the egress-gated gateway is used, with the
    job kind `telemetry` - which means the gate is checked before anything
    is sent.

    `propose_actions` records the verdict's recommendations as work items
    through the reactor. That is a proposal, not an action: the reactor
    refuses anything outside its closed catalogue and never changes
    production.
    """
    if subsection not in SUBSECTION_TOOLS:
        raise ValueError(f"unknown subsection {subsection!r}")

    started = datetime.now(timezone.utc).replace(tzinfo=None)
    started_monotonic = time.monotonic()
    window_end = started
    window_start = started.replace(hour=0, minute=0, second=0, microsecond=0)

    outputs, tools_failed = _collect_tools(session, subsection, scan_id)

    system_prompt = load_system_prompt()
    focus = SUBSECTION_PROMPTS.get(subsection, "")
    user_prompt = json.dumps(
        {
            "subsection": subsection,
            "tool_output": outputs,
            "expected_shape": _SCHEMA_HINT,
        },
        indent=2,
        default=str,
    )

    transport = chat or _default_chat(
        session, provider=provider, scan_id=scan_id, model=model
    )

    result: ScanResult | None = None
    reason = ""
    for attempt in range(2):  # one retry, at a lower temperature
        messages = [
            {"role": "system", "content": system_prompt + ("\n\n" + focus if focus else "")},
            {"role": "user", "content": user_prompt},
        ]
        if attempt:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"The previous attempt failed: {reason}. Return the JSON "
                        "again, using only numbers that appear in the tool "
                        "output above."
                    ),
                }
            )
        try:
            raw = await transport(messages)
        except Exception as exc:  # noqa: BLE001 - a provider can fail any way
            # The model could not be reached at all: no key, no network, a
            # refusal from the egress gate. That is a failed scan, not a
            # crashed request - the reason goes into an honest `error`
            # verdict rather than becoming a 500 with no explanation.
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "scan %s (%s) attempt %d could not reach a model: %s",
                scan_id, subsection, attempt + 1, reason,
            )
            continue
        try:
            data = _parse_json(raw)
            data["scan_id"] = scan_id
            data["subsection"] = subsection
            candidate = ScanResult(**data)
            reconcile(session, candidate, scan_id=scan_id)
        except (ValueError, ReconcileError) as exc:
            reason = str(exc)
            logger.warning(
                "scan %s (%s) attempt %d failed: %s", scan_id, subsection, attempt + 1, reason
            )
            continue
        result = candidate
        break

    if result is None:
        result = _error_result(
            scan_id,
            subsection,
            reason or "the model did not return a usable verdict",
            tools_failed=tools_failed,
        )
    elif tools_failed:
        result.confidence.tools_failed = list(result.confidence.tools_failed) + tools_failed

    if propose_actions and result.status != Status.ERROR:
        # Propose, never act: the reactor records the suggestions as work
        # items for a human. Nothing here changes production.
        try:
            from mcp.reactor import propose_from_result

            propose_from_result(session, result, scan_id=scan_id)
        except Exception as exc:  # noqa: BLE001 - a proposal must not lose the verdict
            logger.warning("could not record proposals for %s: %s", scan_id, exc)

    if store:
        _store(
            session,
            result,
            model=model or provider,
            duration_ms=int((time.monotonic() - started_monotonic) * 1000),
            window_start=window_start,
            window_end=window_end,
        )
    return result


__all__ = ["SUBSECTION_TOOLS", "ReconcileError", "Metric", "run_scan"]
