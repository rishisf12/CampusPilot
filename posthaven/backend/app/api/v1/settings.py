from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.models.setting import UserSetting, UserSettingRead, UserSettingUpsert

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=list[UserSettingRead])
async def list_settings(
    current_user: CurrentUser,
    session: SessionDep,
):
    result = await session.exec(
        select(UserSetting).where(UserSetting.user_id == current_user.id).order_by(UserSetting.key)
    )
    return result.all()

@router.post("/{key}", response_model=UserSettingRead)
async def upsert_setting(
    current_user: CurrentUser,
    session: SessionDep,
    key: str,
    data: UserSettingUpsert,
):
    result = await session.exec(
        select(UserSetting).where(UserSetting.user_id == current_user.id, UserSetting.key == key)
    )
    setting = result.first()
    if setting:
        setting.value = data.value
    else:
        setting = UserSetting(user_id=current_user.id, key=key, value=data.value)
        session.add(setting)
    await session.commit()
    await session.refresh(setting)
    return setting
