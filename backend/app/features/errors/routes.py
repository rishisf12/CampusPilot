"""Error tracking routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.errors import service

router = APIRouter(prefix="/admin/errors", tags=["Admin - Errors"])


class ErrorFingerprintResponse(BaseModel):
    id: int
    fingerprint: str
    error_type: str
    message: str
    first_seen: str
    last_seen: str
    count: int
    status: str
    assignee_id: Optional[int]
    affected_users: int


class ErrorListResponse(BaseModel):
    total: int
    page: int
    size: int
    errors: list[ErrorFingerprintResponse]


class ErrorStatusUpdate(BaseModel):
    status: str
    assignee_id: Optional[int] = None


class ErrorEventResponse(BaseModel):
    id: int
    request_id: Optional[str]
    user_id: Optional[int]
    platform: str
    app_version: Optional[str]
    url: Optional[str]
    stack_trace: Optional[str]
    created_at: str


@router.get("", response_model=ErrorListResponse)
def admin_list_errors(
    search: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_fingerprints(session, search, status, platform, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "errors": [service.fingerprint_to_public(r) for r in rows],
    }


@router.get("/{fingerprint_id}", response_model=ErrorFingerprintResponse)
def admin_get_error(
    fingerprint_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    fp = service.get_fingerprint(session, fingerprint_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Error not found")
    return service.fingerprint_to_public(fp)


@router.patch("/{fingerprint_id}", response_model=ErrorFingerprintResponse)
def admin_update_error(
    fingerprint_id: int,
    body: ErrorStatusUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    fp = service.update_fingerprint(session, fingerprint_id, body.status, body.assignee_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Error not found")
    return service.fingerprint_to_public(fp)


@router.get("/{fingerprint_id}/events")
def admin_list_error_events(
    fingerprint_id: int,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    events, total = service.list_events(session, fingerprint_id, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "events": [{"id": e.id, "request_id": e.request_id, "platform": e.platform, "app_version": e.app_version, "url": e.url, "stack_trace": e.stack_trace, "created_at": e.created_at.isoformat() if e.created_at else None} for e in events],
    }


# Client-side error ingestion endpoint (no auth required)
@router.post("/ingest")
async def ingest_error(
    request: Request,
    session: Session = Depends(get_session),
):
    """Receive error from web/mobile clients."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    result = service.ingest_error(session, data)
    return {"status": "ok", "fingerprint_id": result.id}