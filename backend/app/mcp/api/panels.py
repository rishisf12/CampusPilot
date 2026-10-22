"""The admin monitoring panels, served through the MCP layer.

The admin Monitoring tab reads from here. Every figure it shows comes from
one of two places:

* **an MCP tool answer** - the same redacted, subsection-scoped, audited
  contract the scan agent uses (`mcp.monitoring.REGISTRY`), or
* **a read-only store query**, for the handful of measures no MCP tool
  covers yet: revenue, ARPU and ad revenue, the retention cohorts, the
  per-day feedback series, the live registry counters and the collector's
  age.

That split is deliberate, not a compromise. The MCP tools answer *counts
and summaries*, never raw series, so a panel built only from tool answers
would lose the retention cohorts and the hourly volume chart. What the MCP
layer changes is the *source* of every measure it does cover and the audit
trail underneath: each tool call goes through `run_tool`, so the egress
gate redacts it and a row lands in `telemetry.tool_call_audit`.

Every response carries an `mcp` key naming the tools that answered and the
ones that refused. A refused tool degrades one figure instead of failing
the whole screen - and the admin can see the figure is missing rather than
read a zero as "nothing is wrong".

This router is mounted unconditionally; the *operator console* (`/tools`
and `/call` in `mcp.api.routes`) stays behind `ENABLE_ADMIN_MCP`, because
a console is an opt-in tool and a dashboard is the product.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from core.config import get_settings
from core.database import get_session
from core.deps import get_current_admin
from features.monitoring.api.schemas import (
    ScanRequest,
    ScanResponse,
    SubsectionInfo,
    SubsectionsResponse,
)
from features.monitoring.domain.subsections import SUBSECTIONS, SUBSECTION_IDS
from features.monitoring.services import queries
from mcp.core.registry import ToolError, run_tool
from mcp.monitoring.common import (
    MAX_AGGREGATE_WINDOW_DAYS,
    MAX_AGGREGATE_WINDOW_HOURS,
    MAX_UPTIME_WINDOW_HOURS,
)

router = APIRouter()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _window(days: int) -> tuple[datetime, datetime]:
    """The dashboard's window, anchored to clock-hour boundaries.

    `end` is the start of the next hour, so the window covers every complete
    hour up to and including the current one. Two reads within the same hour
    return an identical window, and a window edge never splits a rollup
    bucket (buckets are half-open [start, end)).
    """
    end = _now_utc().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return end - timedelta(days=days), end


def _hours(days: int, cap: int = MAX_AGGREGATE_WINDOW_HOURS) -> int:
    """A day count as an hour count, inside what the aggregate tools accept."""
    return max(1, min(days * 24, cap))


def _subsection_for(platform: str, kind: str) -> str:
    """The scan subsection that owns a measure, for the tool's own scoping.

    The registry refuses a tool that belongs to another subsection, so a
    panel read has to ask as the subsection whose job the measure is part
    of. The android halves were removed with the android client, so `web`
    is the only live platform - the android ids stay in the mapping because
    the tools still accept an android platform label.
    """
    web = platform == "web"
    return {
        "health": "A_W_HEALTH" if web else "A_A_HEALTH",
        "activity": "B_W_ACTIVITY" if web else "B_A_ACTIVITY",
        "security": "C_W_SECURITY" if web else "C_A_SECURITY",
        "feedback": "D_W_FEEDBACK" if web else "D_A_FEEDBACK",
    }[kind]


class _Tools:
    """Runs MCP tools for one panel and remembers what answered.

    A refused tool is recorded, not raised. The dashboard must degrade one
    figure rather than fail the whole screen, and the admin has to be able
    to tell "this tool refused" from "there is nothing to report" - a zero
    that means "not measured" is how a dashboard ends up confidently wrong.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self.used: list[str] = []
        self.failed: dict[str, str] = {}

    def call(self, name: str, subsection: str, args: dict[str, Any]) -> Any:
        from mcp.monitoring import REGISTRY

        try:
            result = run_tool(
                self._session,
                REGISTRY,
                subsection=subsection,
                name=name,
                args=args,
            )
        except ToolError as exc:
            self.failed[name] = str(exc)
            return None
        self.used.append(name)
        return result.data

    def as_dict(self) -> dict[str, Any]:
        return {"tools": self.used, "failed": self.failed}


# --------------------------------------------------------------------------
# Subsection list
# --------------------------------------------------------------------------

@router.get("/panel/subsections", response_model=SubsectionsResponse)
def panel_subsections(_admin=Depends(get_current_admin)):
    """The canonical subsections, plus what this install can do.

    The flags come from settings rather than being inferred by the client,
    so "Scan now" is offered exactly when the backend would accept the
    request. `scan_llm_enabled` reports whether a model is actually
    reachable: the scan is LLM-driven end to end, so "the rules will answer
    without a model" is no longer true and the UI must not claim it.
    """
    settings = get_settings()
    return {
        "subsections": [SubsectionInfo(**s) for s in SUBSECTIONS],
        "scan_enabled": settings.scan_enabled,
        "scan_llm_enabled": _llm_configured(),
    }


def _llm_configured() -> bool:
    """Is a usable model provider configured for a scan?

    Checked by resolution rather than by a flag: the scan reaches the model
    through the allowlisted providers, and "the flag is on" has never meant
    "a key is present".
    """
    try:
        from llms import LLMConfigError, resolve

        resolve()
    except Exception:  # noqa: BLE001 - any failure here means "not usable"
        return False
    return True


# --------------------------------------------------------------------------
# Overview (one call for all panels)
# --------------------------------------------------------------------------

@router.get("/panel/overview")
def panel_overview(
    days: int = Query(default=7),
    platform: Optional[str] = Query(default=None, pattern="^(web|android)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """One call returns everything the dashboard needs for one platform.

    `days` is clamped here rather than rejected: an over-bounded window is
    a client bug, not an error the admin needs a 422 for.
    """
    days = max(1, min(days, 90))
    start, end = _window(days)
    plat = platform or "web"
    tools = _Tools(session)

    activity = queries.activity_overview(session, start, end, platform)
    security = queries.security_overview(session, start, end, platform)
    revenue = queries.revenue_overview(session, start, end, platform)
    arpu = queries.arpu_overview(session, start, end, platform)
    ads = queries.ads_overview(session, start, end, platform)
    crashes = queries.crashes_overview(session, start, end, platform)
    health = queries.health_overview(session, start, end, platform)
    feedback = queries.feedback_overview(session, start, end, platform)

    dau = tools.call(
        "daily_active_users",
        _subsection_for(plat, "activity"),
        {"window_days": days, "platform": plat},
    )
    signals = tools.call(
        "security_signals",
        _subsection_for(plat, "security"),
        {"days": days},
    )
    failed_logins = tools.call(
        "failed_logins_by_hour",
        _subsection_for(plat, "security"),
        {"hours": _hours(days), "platform": plat},
    )
    telemetry = tools.call(
        "telemetry_health",
        _subsection_for(plat, "health"),
        {"days": days, "platform": plat},
    )
    clusters = tools.call(
        "crash_clusters",
        _subsection_for(plat, "health"),
        {"days": days, "platform": plat},
    )
    themes = tools.call(
        "feedback_themes_top5",
        _subsection_for(plat, "feedback"),
        {"days": min(days, MAX_AGGREGATE_WINDOW_DAYS)},
    )

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "platform": platform,
        "activity": activity,
        "security": security,
        "revenue": revenue,
        "arpu": arpu,
        "ads": ads,
        "crashes": crashes,
        "health": health,
        "feedback": feedback,
        "data_freshness": queries.data_freshness(session),
        "mcp": {
            **tools.as_dict(),
            "activity": {"dau": dau},
            "security": {**(signals or {}), "failed_logins_by_hour": failed_logins},
            "health": telemetry,
            "crashes": {"clusters": clusters},
            "feedback": {"themes": themes},
        },
    }


# --------------------------------------------------------------------------
# Health & Performance (Subsection A)
# --------------------------------------------------------------------------

@router.get("/panel/health")
def panel_health(
    days: int = Query(default=7, ge=1, le=90),
    platform: str = Query(default="web", pattern="^(web|android)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """The health panel: the live figures plus the MCP window aggregates.

    The live half (`http`, `db`, `snapshot`) is a registry and store read -
    the cumulative counters cannot express "during this window", so only the
    sampler can. The MCP half is the window's shape: uptime, the latency
    and error averages, the slowest endpoints and the crash fingerprints.
    """
    days = max(1, min(days, 90))
    start, end = _window(days)
    sub = _subsection_for(platform, "health")
    tools = _Tools(session)

    detail = queries.health_detail(session, start, end, platform)
    telemetry = tools.call(
        "telemetry_health", sub, {"days": days, "platform": platform}
    )
    latest = tools.call("health_latest", sub, {"platform": platform})
    uptime = tools.call(
        "health_uptime_pct",
        sub,
        {
            "window_hours": max(1, min(days * 24, MAX_UPTIME_WINDOW_HOURS)),
            "platform": platform,
        },
    )
    latency = tools.call(
        "p95_latency_window",
        sub,
        {"hours": _hours(days), "platform": platform},
    )
    clusters = tools.call(
        "crash_clusters", sub, {"days": days, "platform": platform}
    )

    return {
        **detail,
        "mcp": {
            **tools.as_dict(),
            "telemetry": telemetry,
            "latest": latest,
            "uptime_pct": uptime,
            "latency": latency,
            "crash_clusters": clusters,
        },
    }


# --------------------------------------------------------------------------
# Feedback Analysis (Subsection D)
# --------------------------------------------------------------------------

@router.get("/panel/feedback")
def panel_feedback(
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """The feedback panel.

    Two different sources, deliberately kept apart:

    * the live analysis reads the `feedback` table - the actual student
      submissions, with their per-day series, reply coverage and sample
      size, and
    * the MCP tool reads the rolled-up `feedback_analysis` table - the
      topic mix and the sentiment balance the collector recorded.

    They are not the same measurement and the panel shows both rather than
    pretending one of them is the other.
    """
    days = max(1, min(days, 365))
    start, end = _window(days)
    from features.monitoring.services.feedback_analysis import analyse

    tools = _Tools(session)
    analysis = analyse(session, start, end)
    themes = tools.call(
        "feedback_themes_top5",
        "D_W_FEEDBACK",
        {"days": min(days, MAX_AGGREGATE_WINDOW_DAYS)},
    )

    return {
        **analysis,
        "mcp": {**tools.as_dict(), "themes": themes},
    }


# --------------------------------------------------------------------------
# Scan trigger (per subsection)
# --------------------------------------------------------------------------

@router.post("/scan/{subsection}", response_model=ScanResponse)
async def trigger_scan(
    subsection: str,
    payload: ScanRequest = ScanRequest(),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """Run one subsection's scan through the MCP runtime.

    The runtime asks the subsection's own tools, hands their answers to the
    model, and reconciles every number the model cited against the audit
    trail - a finding whose number no tool produced fails the scan.

    `async def` on purpose. The runtime awaits the LLM, so it must be
    called from a running loop; the previous rule-engine implementation was
    synchronous and could not be awaited. That is the whole difference
    between the two, and it is why this endpoint is `async` where the old
    one was `def`.
    """
    if subsection not in SUBSECTION_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown subsection: {subsection}")

    settings = get_settings()
    if not settings.scan_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI scanning is disabled. Set SCAN_ENABLED=true to enable.",
        )

    from mcp.agent.runtime import run_scan as run_mcp_scan

    scan_id = f"scan-{uuid.uuid4().hex[:12]}"
    started = time.monotonic()
    now = _now_utc()
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        result = await run_mcp_scan(
            session,
            subsection=subsection,
            scan_id=scan_id,
            model=payload.model,
        )
    except ValueError as exc:
        # The runtime refuses an unknown subsection; the allowlist above
        # already caught that, so this is a programming error, not a client
        # one. Say so rather than surfacing a 500 with no explanation.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ScanResponse(
        scan_id=result.scan_id,
        subsection=result.subsection,
        status=result.status.value,
        summary=result.summary,
        findings=[f.model_dump() for f in result.findings],
        root_causes=result.root_causes,
        actions=[a.model_dump() for a in result.recommended_actions],
        confidence=result.confidence.model_dump(),
        window_start=window_start,
        window_end=now,
        duration_ms=int((time.monotonic() - started) * 1000),
        model=payload.model or "nvidia_nim",
        created_at=now,
    )
