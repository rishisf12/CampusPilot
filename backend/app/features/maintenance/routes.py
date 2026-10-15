"""Maintenance mode routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.maintenance import service

router = APIRouter(prefix="/admin/maintenance", tags=["Admin - Maintenance"])


class MaintenanceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    global_maintenance: bool = False
    target_features: list[str] = []
    message: Optional[str] = None
    allow_list_user_ids: list[int] = []
    bypass_roles: list[str] = []
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None


class MaintenanceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    global_maintenance: Optional[bool] = None
    target_features: Optional[list[str]] = None
    message: Optional[str] = None
    allow_list_user_ids: Optional[list[int]] = None
    bypass_roles: Optional[list[str]] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None


class MaintenanceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    enabled: bool
    global_maintenance: bool
    target_features: list[str]
    message: Optional[str]
    allow_list_user_ids: list[int]
    bypass_roles: list[str]
    scheduled_start: Optional[str]
    scheduled_end: Optional[str]
    created_at: str
    updated_at: str


class MaintenanceListResponse(BaseModel):
    total: int
    page: int
    size: int
    windows: list[MaintenanceResponse]


@router.get("", response_model=MaintenanceListResponse)
def admin_list_maintenance(
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_maintenance_windows(session, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "windows": [service.to_public(r) for r in rows],
    }


@router.post("", response_model=MaintenanceResponse, status_code=201)
def admin_create_maintenance(
    body: MaintenanceCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    window = service.create_maintenance_window(session, body, admin.id)
    return service.to_public(window)


@router.get("/{window_id}", response_model=MaintenanceResponse)
def admin_get_maintenance(
    window_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    window = service.get_maintenance_window(session, window_id)
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")
    return service.to_public(window)


@router.patch("/{window_id}", response_model=MaintenanceResponse)
def admin_update_maintenance(
    window_id: int,
    body: MaintenanceUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    window = service.update_maintenance_window(session, window_id, body, admin.id)
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")
    return service.to_public(window)


@router.delete("/{window_id}", status_code=204)
def admin_delete_maintenance(
    window_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    if not service.delete_maintenance_window(session, window_id):
        raise HTTPException(status_code=404, detail="Maintenance window not found")


@router.get("/status/check")
def admin_check_maintenance(
    user_id: Optional[int] = None,
    feature: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    from core.maintenance import maintenance_mode
    window = maintenance_mode.is_active(
        user_id=user_id,
        feature=feature,
    )
    if not window:
        return {"active": False}
    return {
        "active": True,
        "window_id": window.id,
        "name": window.name,
        "message": window.message,
        "global": window.global_maintenance,
        "features": window.target_features,
    }