"""User control routes: suspend, ban, force logout, etc."""
from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from models import User
from features.user_control import service
from core.audit import log_audit

router = APIRouter(prefix="/admin/users", tags=["Admin - User Control"])


class UserActionBody(BaseModel):
    reason: Optional[str] = None
    duration_days: Optional[int] = Field(default=None, ge=1, le=365)


class BulkActionBody(BaseModel):
    user_ids: List[int]
    action: str  # suspend, ban, force_logout, revoke_tokens, reset_verification
    reason: Optional[str] = None
    duration_days: Optional[int] = Field(default=None, ge=1, le=365)


class UserActionLogResponse(BaseModel):
    id: int
    admin_id: int
    target_user_id: int
    action: str
    reason: Optional[str]
    expires_at: Optional[str]
    created_at: str


class UserActionLogListResponse(BaseModel):
    total: int
    page: int
    size: int
    logs: list[UserActionLogResponse]


@router.post("/{user_id}/suspend")
def admin_suspend_user(
    user_id: int,
    body: UserActionBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    if body.duration_days is None:
        raise HTTPException(status_code=400, detail="duration_days required for suspend")
    try:
        action = service.suspend_user(session, admin.id, user_id, body.reason, body.duration_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(
        session, actor=admin, action="user.suspend",
        target_type="user", target_id=str(user_id),
        after={"action": action.action, "reason": body.reason, "expires_at": str(action.expires_at)},
    )
    return service.to_public(action)


@router.post("/{user_id}/ban")
def admin_ban_user(
    user_id: int,
    body: UserActionBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    try:
        action = service.ban_user(session, admin.id, user_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(
        session, actor=admin, action="user.ban",
        target_type="user", target_id=str(user_id),
        after={"action": action.action, "reason": body.reason},
    )
    return service.to_public(action)


@router.post("/{user_id}/force-logout")
def admin_force_logout(
    user_id: int,
    body: UserActionBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    try:
        action = service.force_logout_user(session, admin.id, user_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(
        session, actor=admin, action="user.force_logout",
        target_type="user", target_id=str(user_id),
        after={"action": action.action, "reason": body.reason},
    )
    return service.to_public(action)


@router.post("/{user_id}/revoke-tokens")
def admin_revoke_tokens(
    user_id: int,
    body: UserActionBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    try:
        action = service.revoke_tokens(session, admin.id, user_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(
        session, actor=admin, action="user.revoke_tokens",
        target_type="user", target_id=str(user_id),
        after={"action": action.action, "reason": body.reason},
    )
    return service.to_public(action)


@router.post("/{user_id}/reset-verification")
def admin_reset_verification(
    user_id: int,
    body: UserActionBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    try:
        action = service.reset_verification(session, admin.id, user_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(
        session, actor=admin, action="user.reset_verification",
        target_type="user", target_id=str(user_id),
        after={"action": action.action, "reason": body.reason},
    )
    return service.to_public(action)


@router.post("/{user_id}/impersonate")
def admin_impersonate(
    user_id: int,
    body: UserActionBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    action = service.start_impersonation(session, admin.id, user_id, body.reason)
    if not action:
        raise HTTPException(status_code=404, detail="User not found or not admin")
    return service.to_public(action)


@router.post("/{user_id}/impersonate/end")
def admin_impersonate_end(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    action = service.end_impersonation(session, admin.id, user_id)
    if not action:
        raise HTTPException(status_code=404, detail="No active impersonation")
    return service.to_public(action)


@router.post("/bulk")
def admin_bulk_action(
    body: BulkActionBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    valid_actions = ["suspend", "ban", "force_logout", "revoke_tokens", "reset_verification"]
    if body.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")
    if body.action == "suspend" and body.duration_days is None:
        raise HTTPException(status_code=400, detail="duration_days required for suspend")
    actions = service.bulk_action(session, admin.id, body.user_ids, body.action, body.reason, body.duration_days)
    # One entry for the bulk action, not one per affected user: 500 rows from one
    # click is unreadable in the log and the count of user_ids already records
    # the scale.
    log_audit(
        session, actor=admin, action=f"user.bulk.{body.action}",
        target_type="user", target_id=None,
        after={"affected": len(actions), "reason": body.reason},
    )
    return {"performed": len(actions), "actions": [service.to_public(a) for a in actions]}


@router.get("/actions")
def admin_list_user_actions(
    user_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    action: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_user_actions(session, user_id, admin_id, action, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "logs": [service.to_public(r) for r in rows],
    }