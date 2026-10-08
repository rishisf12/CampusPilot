"""REST API endpoints for Web App Monitoring and Android App Monitoring.

All endpoints are admin-only. The eight subsections are:
  A_W_HEALTH, B_W_ACTIVITY, C_W_SECURITY, D_W_FEEDBACK
  A_A_HEALTH, B_A_ACTIVITY, C_A_SECURITY, D_A_FEEDBACK

Each subsection has its own Scan now button, history, and incident log.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from core.config import get_settings
from core.database import get_session
from core.deps import get_current_admin
from features.monitoring import collector, queries, rollup as rollup_mod
from features.monitoring.models import (
    AdEvent,
    CrashReport,
    EventHourly,
    HealthMetric,
    Purchase,
    ScanResult,
    SecurityEvent,
    SecurityLog,
    Session as MonitorSession,
    StatusTransition,
    ToolCallAudit,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Collector Router (public, unauthenticated - for telemetry ingestion)
# --------------------------------------------------------------------------

collect_router = APIRouter(prefix="/collect", tags=["collect"])


@collect_router.post("/events")
def collect_events(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    request: Request = None,
):
    """Ingest a batch of telemetry events from web or Android clients.

    Public endpoint - no auth. Protected by schema validation, size caps,
    and per-source rate limiting.
    """
    settings = get_settings()
    if not settings.telemetry_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry collection is disabled",
        )

    # Rate limiting by IP
    client_ip = request.client.host if request and request.client else "unknown"
    if not collector.COLLECT_BATCH_LIMIT.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(collector.COLLECT_BATCH_LIMIT.retry_after(client_ip))},
        )

    # Use the pepper from settings for pseudonymisation
    pepper = settings.telemetry_pepper
    client_ip_addr = request.client.host if request and request.client else None

    try:
        result = collector.collect(
            session,
            payload,
            user_id=None,  # No auth context here
            pepper=settings.telemetry_pepper,
            ip=client_ip_addr,
        )
    except collector.CollectError as e:
        # Check if it's an oversized batch error
        if "too many events in one batch" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return result


@collect_router.post("/crash")
def collect_crash(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    request: Request = None,
):
    """Ingest a crash report (crash or ANR) from Android."""
    settings = get_settings()
    if not settings.telemetry_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry collection is disabled",
        )

    # Rate limiting by IP
    client_ip = request.client.host if request and request.client else "unknown"
    if not collector.CRASH_LIMIT.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(collector.CRASH_LIMIT.retry_after(client_ip))},
        )

    # Validate required fields
    required = ["platform", "kind", "session_id", "fingerprint", "fatal"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Validate kind
    valid_kinds = {"crash", "anr"}
    if payload["kind"] not in valid_kinds:
        raise HTTPException(status_code=400, detail=f"Invalid crash kind: {payload['kind']}")

    # Validate platform
    if payload["platform"] not in {"web", "android"}:
        raise HTTPException(status_code=400, detail="Invalid platform")

    # Store crash report
    crash = CrashReport(
        ts=datetime.now(timezone.utc).replace(tzinfo=None),
        platform=payload["platform"],
        kind=payload["kind"],
        session_id=payload["session_id"],
        fingerprint=payload["fingerprint"],
        exception_type=payload.get("exception_type"),
        message=payload.get("message"),
        stack_trace=payload.get("stack_trace"),
        fatal=payload["fatal"],
        app_version=payload.get("app_version"),
        os_version=payload.get("os_version"),
        device_model=payload.get("device_model"),
        foreground=payload.get("foreground", True),
    )
    session.add(crash)
    session.commit()

    return {"accepted": True}


@collect_router.post("/security-signal")
def collect_security_signal(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    request: Request = None,
):
    """Ingest a security signal (root, emulator, tamper detection, etc.)."""
    settings = get_settings()
    if not settings.telemetry_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry collection is disabled",
        )

    # Rate limiting by IP
    client_ip = request.client.host if request and request.client else "unknown"
    if not collector.COLLECT_BATCH_LIMIT.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(collector.COLLECT_BATCH_LIMIT.retry_after(client_ip))},
        )

    # Validate required fields
    required = ["platform", "kind"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Validate platform
    if payload["platform"] not in {"web", "android"}:
        raise HTTPException(status_code=400, detail="Invalid platform")

    # Validate kind
    valid_kinds = {"root_detected", "emulator_detected", "tamper_detected", "hook_detected", "debugger_detected"}
    if payload["kind"] not in valid_kinds:
        raise HTTPException(status_code=400, detail=f"Invalid security signal kind: {payload['kind']}")

    # Get client IP for hashing
    client_ip = request.client.host if request and request.client else None

    # Hash IP if present
    ip_hash = collector.ip_hash(settings.telemetry_pepper, client_ip) if client_ip else None

    # Store security signal
    signal = SecurityEvent(
        ts=datetime.now(timezone.utc).replace(tzinfo=None),
        platform=payload["platform"],
        kind=payload["kind"],
        ip_hash=collector.ip_hash(settings.telemetry_pepper, client_ip) if client_ip else None,
        user_hash=None,
        app_version=payload.get("app_version"),
        blocked=payload.get("blocked", False),
        detail=payload.get("detail", {}),
    )
    session.add(signal)
    session.commit()

    return {"accepted": True}


# --------------------------------------------------------------------------
# Monitoring Router (admin-only)
# --------------------------------------------------------------------------

monitoring_router = APIRouter(prefix="/monitoring", tags=["monitoring"])

SUBSECTIONS: tuple[dict[str, str], ...] = (
    {"id": "A_W_HEALTH", "platform": "web", "group": "Web App Monitoring", "title": "Health & Performance"},
    {"id": "B_W_ACTIVITY", "platform": "web", "group": "Web App Monitoring", "title": "User Activity & Monetization"},
    {"id": "C_W_SECURITY", "platform": "web", "group": "Web App Monitoring", "title": "Security Monitoring"},
    {"id": "D_W_FEEDBACK", "platform": "web", "group": "Web App Monitoring", "title": "Feedback Analysis"},
    {"id": "A_A_HEALTH", "platform": "android", "group": "Android App Monitoring", "title": "Health & Performance"},
    {"id": "B_A_ACTIVITY", "platform": "android", "group": "Android App Monitoring", "title": "User Activity & Monetization"},
    {"id": "C_A_SECURITY", "platform": "android", "group": "Android App Monitoring", "title": "Security Monitoring"},
    {"id": "D_A_FEEDBACK", "platform": "android", "group": "Android App Monitoring", "title": "Feedback Analysis"},
)


# --------------------------------------------------------------------------
# Pydantic Schemas
# --------------------------------------------------------------------------

class ScanRequest(BaseModel):
    """Request body for triggering a scan."""
    window_days: int = Field(default=7, ge=1, le=90)
    model: Optional[str] = Field(default=None, description="Override model (e.g. 'qwen2.5:7b')")


class ScanResponse(BaseModel):
    """Response from a scan trigger."""
    scan_id: str
    subsection: str
    status: str
    summary: str
    findings: list[dict[str, Any]]
    root_causes: list[str]
    actions: list[dict[str, Any]]
    confidence: dict[str, Any]
    window_start: datetime
    window_end: datetime
    duration_ms: int
    model: str
    created_at: datetime


class SubsectionInfo(BaseModel):
    id: str
    platform: str
    group: str
    title: str


class SubsectionsResponse(BaseModel):
    subsections: list[SubsectionInfo]


class ScanHistoryResponse(BaseModel):
    scans: list[dict[str, Any]]
    incidents: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


class RollupResponse(BaseModel):
    start: str
    end: str
    buckets: int
    rows_written: int
    events_scanned: int


# --------------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------------

def _require_telemetry() -> None:
    settings = get_settings()
    if not settings.telemetry_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry collection is disabled",
        )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _window(days: int) -> tuple[datetime, datetime]:
    # Anchor to clock-hour boundaries: `end` is the start of the next
    # hour, so the window covers every complete hour up to and
    # including the current one. Two reads within the same hour return
    # an identical window, and a window edge never splits a rollup
    # bucket (buckets are half-open [start, end)).
    end = _now_utc().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = end - timedelta(days=days)
    return start, end


def _incident_from_transition(sub: str, t: StatusTransition, next_t: Optional[StatusTransition]) -> dict[str, Any]:
    """Build an incident dict from a status transition."""
    ended = next_t.at if next_t and next_t.to_status == "healthy" else None
    return {
        "subsection": sub,
        "status": t.to_status,
        "started_at": t.at.isoformat(),
        "ended_at": ended.isoformat() if ended else None,
        "duration_s": int((ended - t.at).total_seconds()) if ended else None,
        "open": ended is None,
    }


# --------------------------------------------------------------------------
# Subsection List
# --------------------------------------------------------------------------

@monitoring_router.get("/subsections", response_model=SubsectionsResponse)
def list_subsections(_admin=Depends(get_current_admin)):
    """Return the canonical eight subsections."""
    return {"subsections": [SubsectionInfo(**s) for s in SUBSECTIONS]}


# --------------------------------------------------------------------------
# Overview (single call for all panels)
# --------------------------------------------------------------------------

@monitoring_router.get("/overview")
def overview(
    days: int = Query(default=7),
    platform: Optional[str] = Query(default=None, pattern="^(web|android)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """One call returns everything the dashboard needs for one platform.

    `days` is clamped here rather than rejected: an over-bounded
    window is a client bug, not an error the admin needs a 422 for.
    """
    days = max(1, min(days, 90))
    start, end = _window(days)

    out = {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "platform": platform,
        "activity": queries.activity_overview(session, start, end, platform),
        "security": queries.security_overview(session, start, end, platform),
        "revenue": queries.revenue_overview(session, start, end, platform),
        "arpu": queries.arpu_overview(session, start, end, platform),
        "ads": queries.ads_overview(session, start, end, platform),
        "crashes": queries.crashes_overview(session, start, end, platform),
        "health": queries.health_overview(session, start, end, platform),
        "feedback": queries.feedback_overview(session, start, end, platform),
        "data_freshness": queries.data_freshness(session),
    }
    return out


# --------------------------------------------------------------------------
# Health & Performance (Subsection A)
# --------------------------------------------------------------------------

@monitoring_router.get("/health")
def health(
    days: int = Query(default=7, ge=1, le=90),
    platform: str = Query(default="web", pattern="^(web|android)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    days = max(1, min(days, 90))
    start, end = _window(days)
    return queries.health_detail(session, start, end, platform)


# --------------------------------------------------------------------------
# User Activity & Monetization (Subsection B)
# --------------------------------------------------------------------------

@monitoring_router.get("/activity")
def activity(
    days: int = Query(default=7, ge=1, le=90),
    platform: Optional[str] = Query(default=None, pattern="^(web|android)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    days = max(1, min(days, 90))
    start, end = _window(days)
    return queries.activity_detail(session, start, end, platform)


@monitoring_router.get("/monetisation")
def monetisation(
    days: int = Query(default=30, ge=1, le=365),
    platform: Optional[str] = Query(default=None, pattern="^(web|android)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    days = max(1, min(days, 365))
    start, end = _window(days)
    prev_start, prev_end = start - timedelta(days=days), start
    return queries.monetisation_detail(session, start, end, prev_start, prev_end, platform)


# --------------------------------------------------------------------------
# Security Monitoring (Subsection C)
# --------------------------------------------------------------------------

@monitoring_router.get("/security")
def security(
    days: int = Query(default=7, ge=1, le=90),
    platform: Optional[str] = Query(default=None, pattern="^(web|android)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    days = max(1, min(days, 90))
    start, end = _window(days)
    return queries.security_detail(session, start, end, platform)


# --------------------------------------------------------------------------
# Feedback Analysis (Subsection D)
# --------------------------------------------------------------------------

@monitoring_router.get("/feedback")
def feedback_analysis(
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    days = max(1, min(days, 365))
    start, end = _window(days)
    return queries.feedback_detail(session, start, end)


# --------------------------------------------------------------------------
# Scan History & Incident Log (Subsection E - global)
# --------------------------------------------------------------------------

@monitoring_router.get("/history", response_model=ScanHistoryResponse)
def history(
    subsection: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    limit = max(1, min(limit, 200))

    scans_stmt = select(ScanResult).order_by(ScanResult.created_at.desc()).limit(limit)
    if subsection:
        scans_stmt = scans_stmt.where(ScanResult.subsection == subsection)
    scans = session.exec(scans_stmt).all()

    trans_stmt = select(StatusTransition).order_by(StatusTransition.at.desc()).limit(limit * 4)
    if subsection:
        trans_stmt = trans_stmt.where(StatusTransition.subsection == subsection)
    transitions = session.exec(trans_stmt).all()

    # Build incidents from transitions
    by_sub: dict[str, list[StatusTransition]] = {}
    for t in sorted(transitions, key=lambda x: x.at):
        by_sub.setdefault(t.subsection, []).append(t)

    incidents: list[dict] = []
    for sub, items in by_sub.items():
        open_since = None
        open_status = None
        for t in items:
            if t.to_status in {"warning", "critical"}:
                if open_since is None:
                    open_since, open_status = t.at, t.to_status
            elif open_since is not None and t.to_status == "healthy":
                incidents.append({
                    "subsection": sub,
                    "status": open_status,
                    "started_at": open_since.isoformat(),
                    "ended_at": t.at.isoformat(),
                    "duration_s": int((t.at - open_since).total_seconds()),
                    "open": False,
                })
                open_since = open_status = None
        if open_since is not None:
            incidents.append({
                "subsection": sub,
                "status": open_status,
                "started_at": open_since.isoformat(),
                "ended_at": None,
                "duration_s": None,
                "open": True,
            })

    incidents.sort(key=lambda i: i["started_at"], reverse=True)

    tool_calls_stmt = select(ToolCallAudit).order_by(ToolCallAudit.at.desc()).limit(limit * 8)
    if subsection:
        tool_calls_stmt = tool_calls_stmt.where(ToolCallAudit.scan_id.like(f"%{subsection}%"))
    tool_calls = session.exec(tool_calls_stmt).all()

    return {
        "scans": [
            {
                "scan_id": s.scan_id,
                "subsection": s.subsection,
                "status": s.status,
                "summary": s.summary,
                "confidence": s.confidence,
                "window": {"start": s.window_start.isoformat(), "end": s.window_end.isoformat()},
                "duration_ms": s.duration_ms,
                "model": s.model,
                "created_at": s.created_at.isoformat(),
            }
            for s in scans
        ],
        "incidents": incidents[:limit],
        "tool_calls": [
            {"scan_id": a.scan_id, "tool": a.tool, "metric_key": a.metric_key,
             "row_count": a.row_count, "ok": a.ok, "at": a.at.isoformat()}
            for a in tool_calls
        ],
    }


# --------------------------------------------------------------------------
# Scan Trigger (per subsection)
# --------------------------------------------------------------------------

@monitoring_router.post("/scan/{subsection}", response_model=ScanResponse)
async def trigger_scan(
    subsection: str,
    payload: ScanRequest = ScanRequest(),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """Trigger an AI scan for one subsection. Returns the scan result."""
    # Validate subsection
    valid_ids = {s["id"] for s in SUBSECTIONS}
    if subsection not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Unknown subsection: {subsection}")

    # TODO: Enqueue scan job via RQ, return immediately with pending status
    # For now, return a stub response
    scan_id = f"{subsection}-{int(datetime.now(timezone.utc).timestamp())}"
    start, end = _window(payload.window_days)

    return ScanResponse(
        scan_id=scan_id,
        subsection=subsection,
        status="pending",
        summary="Scan queued; worker will pick up shortly.",
        findings=[],
        root_causes=[],
        actions=[],
        confidence={},
        window_start=start,
        window_end=end,
        duration_ms=0,
        model=payload.model or "local-llm",
        created_at=_now_utc(),
    )


# --------------------------------------------------------------------------
# Rollup Management
# --------------------------------------------------------------------------

@monitoring_router.post("/rollup", response_model=RollupResponse)
def trigger_rollup(
    lookback_hours: int = Query(default=48, ge=1, le=720),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    lookback_hours = max(1, min(lookback_hours, 24 * 31))
    summary = rollup_mod.rollup(session, lookback_hours=lookback_hours)
    return RollupResponse(**summary)


# --------------------------------------------------------------------------
# Data Freshness
# --------------------------------------------------------------------------

@monitoring_router.get("/freshness")
def data_freshness(
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """Return the age of the newest data in each monitoring table."""
    latest = session.exec(
        select(EventHourly.bucket_hour).order_by(EventHourly.bucket_hour.desc()).limit(1)
    ).first()
    raw_latest = session.exec(
        select(CrashReport.ts).order_by(CrashReport.ts.desc()).limit(1)
    ).first()
    now = _now_utc()
    return {
        "now": now.isoformat(),
        "latest_rollup_hour": latest.isoformat() if latest else None,
        "latest_crash_at": raw_latest.isoformat() if raw_latest else None,
        "rollup_lag_minutes": int((now - latest).total_seconds() // 60) if latest else None,
    }


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

@monitoring_router.get("/export/{subsection}")
def export_subsection(
    subsection: str,
    days: int = Query(default=30, ge=1, le=365),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin),
):
    """Export raw data for one subsection (JSON or CSV)."""
    valid_ids = {s["id"] for s in SUBSECTIONS}
    if subsection not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Unknown subsection: {subsection}")

    # TODO: Implement CSV export
    if format == "csv":
        raise HTTPException(status_code=501, detail="CSV export not yet implemented")

    # For now, return a summary
    return {"message": f"Export for {subsection} not yet implemented"}