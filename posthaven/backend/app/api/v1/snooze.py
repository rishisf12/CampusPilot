from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.models.snooze import Snooze, SnoozeRead, SnoozeCreate
from app.models.message import Message

router = APIRouter(prefix="/snooze", tags=["snooze"])

@router.post("", response_model=SnoozeRead, status_code=status.HTTP_201_CREATED)
async def snooze_message(current_user: CurrentUser, session: SessionDep, data: SnoozeCreate):
    msg = await session.get(Message, data.message_id)
    if not msg or msg.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    snooze = Snooze(user_id=current_user.id, **data.model_dump())
    session.add(snooze)
    await session.commit()
    await session.refresh(snooze)
    return snooze

@router.get("", response_model=list[SnoozeRead])
async def list_snoozes(current_user: CurrentUser, session: SessionDep, include_woke: bool = Query(default=False)):
    q = select(Snooze).where(Snooze.user_id == current_user.id)
    if not include_woke:
        q = q.where(Snooze.woke == False)
    result = await session.exec(q)
    return result.all()
