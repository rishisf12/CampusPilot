"""Moderation routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.moderation import service

router = APIRouter(prefix="/admin/moderation", tags=["Admin - Moderation"])


class ModerationReview(BaseModel):
    action: str  # approve, remove, warn
    reason: Optional[str] = None


class ModerationItemResponse(BaseModel):
    id: int
    content_type: str
    content_id: int
    reporter_id: Optional[int]
    reason: str
    details: Optional[str]
    status: str
    reviewer_id: Optional[int]
    reviewed_at: Optional[str]
    action_taken: Optional[str]
    action_reason: Optional[str]
    created_at: str
    updated_at: str


class ModerationListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list


@router.get("")
def admin_list_moderation(
    status: Optional[str] = None,
    content_type: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_moderation(session, status, content_type, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [service.to_public(r) for r in rows],
    }


@router.get("/{moderation_id}")
def admin_get_moderation(
    moderation_id: int,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    item = service.get_moderation(session, moderation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Moderation item not found")
    return service.to_public(item)


@router.patch("/{moderation_id}/review")
def admin_review_moderation(
    moderation_id: int,
    body: ModerationReview,
    session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    if body.action not in ("approve", "remove", "warn"):
        raise HTTPException(status_code=400, detail="action must be approve, remove, or warn")
    item = service.review_moderation(session, moderation_id, admin.id, body.action, body.reason)
    if not item:
        raise HTTPException(status_code=404, detail="Moderation item not found or already reviewed")
    return service.to_public(item)