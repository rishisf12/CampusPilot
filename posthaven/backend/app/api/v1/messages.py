from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.models.message import Message, MessageRead, MessageListItem
from app.models.folder import Folder

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=dict)
async def list_messages(
    current_user: CurrentUser,
    session: SessionDep,
    folder_id: UUID = Query(...),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    unread_only: bool = Query(default=False),
):
    # Verify folder ownership
    folder = await session.get(Folder, folder_id)
    if not folder or folder.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    q = select(Message).where(Message.folder_id == folder_id)
    if unread_only:
        # flags is JSON list; check if \Seen not in flags
        q = q.where(Message.flags.is_not(None))  # placeholder; refine with JSON contains

    # Cursor pagination: use received_at as cursor
    if cursor:
        try:
            cursor_dt = func.now()  # placeholder; parse ISO cursor
        except Exception:
            cursor_dt = None

    q = q.order_by(Message.received_at.desc().nullslast()).limit(limit)
    result = await session.exec(q)
    messages = result.all()

    # next cursor = last message received_at
    next_cursor = None
    if messages:
        last = messages[-1]
        if last.received_at:
            next_cursor = last.received_at.isoformat()

    return {
        "messages": [MessageListItem.model_validate(m) for m in messages],
        "next_cursor": next_cursor,
        "count": len(messages),
    }


@router.get("/{message_id}", response_model=MessageRead)
async def get_message(
    current_user: CurrentUser,
    session: SessionDep,
    message_id: UUID,
):
    msg = await session.get(Message, message_id)
    if not msg or msg.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return msg
