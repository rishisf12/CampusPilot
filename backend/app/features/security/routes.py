"""Security events routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from features.security import service

router = APIRouter(prefix="/admin/security", tags=["Admin - Security"])


@router.get("/events")
def admin_list_security_events(
    hours: int = 24,
    limit: int = 100,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    events = service.get_recent_events(session, hours, limit)
    return {"events": events}


@router.get("/feed")
def admin_list_security_feed(
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    days: int = 7,
    page: int = 1,
    size: int = 50,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.get_security_feed(session, severity, event_type, days, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "feed": [service.feed_to_public(r) for r in rows],
    }


@router.post("/anomalies/detect")
def admin_detect_anomalies(
    hours: int = 24,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    anomalies = service.detect_anomalies(session, hours)
    return {"detected": len(anomalies), "anomalies": anomalies}