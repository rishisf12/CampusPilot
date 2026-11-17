from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.services import search as search_service
from app.models.saved_search import SavedSearchCreate, SavedSearchRead

router = APIRouter(prefix="/search", tags=["search"])

@router.get("")
async def search(
    current_user: CurrentUser,
    session: SessionDep,
    q: str = Query(default=""),
    folder_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    result = await search_service.search_messages(
        session=session, user_id=str(current_user.id), query=q,
        folder_id=str(folder_id) if folder_id else None, limit=limit, offset=offset,
    )
    return result

@router.post("/saved", response_model=SavedSearchRead, status_code=status.HTTP_201_CREATED)
async def save_search(
    current_user: CurrentUser, session: SessionDep, data: SavedSearchCreate,
):
    return await search_service.save_search(session, str(current_user.id), data)

@router.get("/saved", response_model=list[SavedSearchRead])
async def list_saved_searches(
    current_user: CurrentUser, session: SessionDep,
):
    return await search_service.list_saved_searches(session, str(current_user.id))
