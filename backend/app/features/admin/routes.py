"""Admin routes: user list, role change, stats."""
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
