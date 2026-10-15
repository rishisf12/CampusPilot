"""Health check routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from features.health import service

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
def health_live():
    """Liveness probe - always returns 200 if app is running."""
    return {"status": "alive"}


@router.get("/ready")
def health_ready(
    session: Session = Depends(get_session),
):
    """Readiness probe - checks if all dependencies are healthy."""
    result = service.check_readiness(session)
    if not result["ready"]:
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/components")
def health_components(
    component: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    """Get health status of all components (admin only)."""
    return service.get_component_health(session, component)


@router.get("/history")
def health_history(
    component: Optional[str] = None,
    hours: int = 24,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    """Get health history for trending (admin only)."""
    return service.get_health_history(session, component, hours)


@router.post("/check")
def health_check_now(
    component: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    """Trigger an immediate health check (admin only)."""
    return service.run_health_checks(session, component)