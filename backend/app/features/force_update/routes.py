"""Force/Soft update routes."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from core.database import get_session
from core.deps import get_current_admin
from features.force_update import service
from features.force_update.models import ForceUpdateRule

router = APIRouter(prefix="/admin/force-update", tags=["Admin - Force Update"])


class ForceUpdateRuleCreate(BaseModel):
    platform: str
    min_version: str
    recommended_version: str
    store_url: str
    message: Optional[str] = None
    is_active: bool = True


class ForceUpdateRuleUpdate(BaseModel):
    min_version: Optional[str] = None
    recommended_version: Optional[str] = None
    store_url: Optional[str] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None


class ForceUpdateRuleResponse(BaseModel):
    id: int
    platform: str
    min_version: str
    recommended_version: str
    store_url: str
    message: Optional[str]
    is_active: bool
    created_by: Optional[int]
    created_at: str
    updated_at: str


class ForceUpdateCheckResponse(BaseModel):
    required: bool
    type: str  # force, soft, none
    min_version: str
    recommended_version: str
    store_url: str
    message: Optional[str]


@router.get("", response_model=dict)
def admin_list_rules(
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    # response_model is dict, not list[dict]: the handler returns a paginated
    # envelope, and declaring a list made every call fail validation with 500.
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_rules(session, page, size)
    return {"total": total, "page": page, "size": size, "rules": [service.to_public(r) for r in rows]}


@router.post("", response_model=dict, status_code=201)
def admin_create_rule(
    body: ForceUpdateRuleCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    rule = service.create_rule(
        session,
        platform=body.platform,
        min_version=body.min_version,
        recommended_version=body.recommended_version,
        store_url=body.store_url,
        message=body.message,
        is_active=body.is_active,
        created_by=admin.id,
    )
    return service.to_public(rule)


@router.get("/check")
def check_update(
    platform: str = Query(..., description="Platform: ios, android, web"),
    version: str = Query(..., description="Current app version"),
    session: Session = Depends(get_session),
):
    """Client-facing endpoint to check for updates.

    Declared before `/{platform}` on purpose: FastAPI matches in order, so a
    later `/check` would be swallowed by `/{platform}` with platform="check"
    and the public check would be unreachable behind admin auth.
    """
    result = service.get_rule_for_client(session, platform, version)
    if not result:
        return {"required": False, "type": "none"}
    return result


@router.get("/{platform}", response_model=dict)
def admin_get_rule(
    platform: str,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    rule = service.get_rule(session, platform)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return service.to_public(rule)


@router.patch("/{platform}", response_model=dict)
def admin_update_rule(
    platform: str,
    body: ForceUpdateRuleUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    rule = session.exec(
        select(ForceUpdateRule)
        .where(ForceUpdateRule.platform == platform)
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    rule.updated_at = datetime.utcnow()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return {"id": rule.id, "platform": rule.platform, "min_version": rule.min_version,
            "recommended_version": rule.recommended_version, "store_url": rule.store_url,
            "message": rule.message, "is_active": rule.is_active,
            "created_by": rule.created_by, "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None}


@router.delete("/{platform}", status_code=204)
def admin_delete_rule(
    platform: str,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    rule = session.exec(
        select(ForceUpdateRule)
        .where(ForceUpdateRule.platform == platform)
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()