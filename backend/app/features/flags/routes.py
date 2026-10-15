"""Feature flag routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.flags import service

router = APIRouter(prefix="/admin/flags", tags=["Admin - Feature Flags"])


class FlagTargetRuleIn(BaseModel):
    attribute: str
    operator: str
    values: list[str]


class FlagCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    enabled: bool = False
    rollout_percentage: int = 0
    target_roles: list[str] = []
    target_user_ids: list[int] = []
    target_platforms: list[str] = []
    target_app_versions: list[str] = []
    target_rules: list[FlagTargetRuleIn] = []


class FlagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = None
    target_roles: Optional[list[str]] = None
    target_user_ids: Optional[list[int]] = None
    target_platforms: Optional[list[str]] = None
    target_app_versions: Optional[list[str]] = None
    target_rules: Optional[list[FlagTargetRuleIn]] = None


class FlagResponse(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    enabled: bool
    rollout_percentage: int
    target_roles: list[str]
    target_user_ids: list[int]
    target_platforms: list[str]
    target_app_versions: list[str]
    target_rules: list[FlagTargetRuleIn]
    created_at: str
    updated_at: str


class FlagListResponse(BaseModel):
    total: int
    page: int
    size: int
    flags: list[FlagResponse]


@router.get("", response_model=FlagListResponse)
def admin_list_flags(
    search: Optional[str] = None,
    enabled: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_flags(session, search, enabled, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "flags": [service.to_public(r) for r in rows],
    }


@router.post("", response_model=FlagResponse, status_code=201)
def admin_create_flag(
    body: FlagCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    flag = service.create_flag(session, body, admin.id)
    return service.to_public(flag)


@router.get("/{key}", response_model=FlagResponse)
def admin_get_flag(
    key: str,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    flag = service.get_flag(session, key)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return service.to_public(flag)


@router.patch("/{key}", response_model=FlagResponse)
def admin_update_flag(
    key: str,
    body: FlagUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    flag = service.update_flag(session, key, body, admin.id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return service.to_public(flag)


@router.delete("/{key}", status_code=204)
def admin_delete_flag(
    key: str,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    if not service.delete_flag(session, key):
        raise HTTPException(status_code=404, detail="Flag not found")


@router.post("/evaluate")
def admin_evaluate_flag(
    key: str,
    user_id: Optional[int] = None,
    platform: Optional[str] = None,
    app_version: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    from core.feature_flags import flag_engine
    from models import User

    user = session.get(User, user_id) if user_id else None
    enabled = flag_engine.is_enabled(
        key, user=user, platform=platform, app_version=app_version
    )
    return {"key": key, "enabled": enabled}