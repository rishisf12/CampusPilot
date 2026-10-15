"""Admin routes: user list, role change, stats, teams moderation."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from models import User
from features.admin import service

router = APIRouter(tags=["Admin"])


class RoleBody(BaseModel):
    role: str


class SettingBody(BaseModel):
    value: object = None


@router.get("/users")
def admin_list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_users(session, search, role, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "users": [service.to_public(u) for u in rows],
    }


@router.patch("/users/{user_id}/role")
def admin_set_role(
    user_id: int,
    body: RoleBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    if body.role not in ("admin", "student"):
        raise HTTPException(status_code=400, detail="role must be admin or student")
    if admin.id == user_id and body.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote yourself")
    user = service.set_role(session, user_id, body.role)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return service.to_public(user)


@router.get("/stats")
def admin_stats(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    return service.stats(session)


@router.get("/settings")
def admin_get_settings(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """All system settings as one flat object. Missing keys are simply
    absent - the Settings tab falls back to its own defaults, so a fresh
    install renders correctly with zero rows stored."""
    return service.get_settings_all(session)


@router.patch("/settings/{key}")
def admin_update_setting(
    key: str,
    body: SettingBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    return service.set_setting(session, key, body.value, updated_by=admin.id)


@router.get("/teams")
def admin_list_teams(
    search: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    teams, total = service.list_teams(session, search, page, size)
    return {"total": total, "page": page, "size": size, "teams": teams}


@router.delete("/teams/{team_id}", status_code=204)
def admin_delete_team(
    team_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    if not service.delete_team_any(session, team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    return
