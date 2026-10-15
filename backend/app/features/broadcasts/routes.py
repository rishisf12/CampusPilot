"""Broadcast routes."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from features.broadcasts import service

router = APIRouter(prefix="/admin/broadcasts", tags=["Admin - Broadcasts"])


class BroadcastCreate(BaseModel):
    title: str
    body: str
    channel: str = "in_app"  # in_app, push, email
    target_roles: List[str] = []
    target_user_ids: List[int] = []
    target_branches: List[str] = []
    target_semesters: List[int] = []
    target_segments: List[int] = []
    scheduled_at: Optional[str] = None


class BroadcastUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    channel: Optional[str] = None
    target_roles: Optional[List[str]] = None
    target_user_ids: Optional[List[int]] = None
    target_branches: Optional[List[str]] = None
    target_semesters: Optional[List[int]] = None
    target_segments: Optional[List[int]] = None
    scheduled_at: Optional[str] = None


class BroadcastResponse(BaseModel):
    id: int
    title: str
    body: str
    channel: str
    target_roles: List[str]
    target_user_ids: List[int]
    target_branches: List[str]
    target_semesters: List[int]
    target_segments: List[int]
    scheduled_at: Optional[str]
    sent_at: Optional[str]
    created_at: str
    created_by: int


class BroadcastListResponse(BaseModel):
    total: int
    page: int
    size: int
    broadcasts: List[BroadcastResponse]


class DeliveryResponse(BaseModel):
    id: int
    broadcast_id: int
    user_id: int
    channel: str
    status: str
    sent_at: Optional[str]
    read_at: Optional[str]
    error_message: Optional[str]


class DeliveryListResponse(BaseModel):
    total: int
    page: int
    size: int
    deliveries: List[DeliveryResponse]


@router.get("", response_model=BroadcastListResponse)
def admin_list_broadcasts(
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_broadcasts(session, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "broadcasts": [service.to_public(b) for b in rows],
    }


@router.post("", response_model=BroadcastResponse, status_code=201)
def admin_create_broadcast(
    body: BroadcastCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    scheduled_at = datetime.fromisoformat(body.scheduled_at) if body.scheduled_at else None
    broadcast = service.create_broadcast(
        session,
        title=body.title,
        body=body.body,
        channel=body.channel,
        target_roles=body.target_roles or None,
        target_user_ids=body.target_user_ids or None,
        target_branches=body.target_branches or None,
        target_semesters=body.target_semesters or None,
        target_segments=body.target_segments or None,
        scheduled_at=datetime.fromisoformat(body.scheduled_at) if body.scheduled_at else None,
        created_by=admin.id,
    )
    return service.to_public(broadcast)


@router.get("/{broadcast_id}", response_model=BroadcastResponse)
def admin_get_broadcast(
    broadcast_id: int,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    broadcast = service.get_broadcast(session, broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return service.to_public(broadcast)


@router.patch("/{broadcast_id}", response_model=BroadcastResponse)
def admin_update_broadcast(
    broadcast_id: int,
    body: BroadcastUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    update_data = body.model_dump(exclude_unset=True)
    if "scheduled_at" in update_data and update_data["scheduled_at"]:
        update_data["scheduled_at"] = datetime.fromisoformat(update_data["scheduled_at"])
    broadcast = service.update_broadcast(session, broadcast_id, update_data)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return service.to_public(broadcast)


@router.delete("/{broadcast_id}", status_code=204)
def admin_delete_broadcast(
    broadcast_id: int,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    if not service.delete_broadcast(session, broadcast_id):
        raise HTTPException(status_code=404, detail="Broadcast not found")


@router.post("/{broadcast_id}/send")
def admin_send_broadcast(
    broadcast_id: int,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    result = service.send_broadcast(session, broadcast_id)
    return result


@router.get("/{broadcast_id}/deliveries", response_model=DeliveryListResponse)
def admin_list_deliveries(
    broadcast_id: int,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_deliveries(session, broadcast_id, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "deliveries": [service.delivery_to_public(d) for d in rows],
    }