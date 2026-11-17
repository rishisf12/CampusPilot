from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from uuid import UUID

from app.db.session import get_session
from app.core.deps import CurrentAdmin, SessionDep
from app.models.user import User, UserRead

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users", response_model=list[UserRead])
async def list_users(
    current_admin: CurrentAdmin,
    session: SessionDep,
):
    result = await session.exec(select(User).order_by(User.created_at.desc()))
    return result.all()

@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    current_admin: CurrentAdmin,
    session: SessionDep,
    user_id: UUID,
    is_active: Optional[bool] = Query(default=None),
    is_admin: Optional[bool] = Query(default=None),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_active is not None:
        user.is_active = is_active
    if is_admin is not None:
        user.is_admin = is_admin
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@router.get("/health")
async def admin_health(
    current_admin: CurrentAdmin,
    session: SessionDep,
):
    user_count = (await session.exec(select(func.count(User.id)))).one()
    return {"status": "ok", "user_count": user_count}
