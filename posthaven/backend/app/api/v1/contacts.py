from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.services import contacts as contacts_service
from app.models.contact import ContactCreate, ContactUpdate, ContactRead, ContactGroupCreate, ContactGroupRead

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.get("", response_model=list[ContactRead])
async def list_contacts(
    current_user: CurrentUser,
    session: SessionDep,
    q: Optional[str] = Query(default=None),
    group_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await contacts_service.list_contacts(
        session, str(current_user.id), q=q, group_id=group_id, limit=limit, offset=offset
    )

@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def create_contact(
    current_user: CurrentUser, session: SessionDep, data: ContactCreate,
):
    return await contacts_service.create_contact(session, str(current_user.id), data)

@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(
    current_user: CurrentUser, session: SessionDep, contact_id: UUID,
):
    return await contacts_service.get_contact(session, str(current_user.id), contact_id)

@router.patch("/{contact_id}", response_model=ContactRead)
async def update_contact(
    current_user: CurrentUser, session: SessionDep, contact_id: UUID, data: ContactUpdate,
):
    return await contacts_service.update_contact(session, str(current_user.id), contact_id, data)

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    current_user: CurrentUser, session: SessionDep, contact_id: UUID,
):
    await contacts_service.delete_contact(session, str(current_user.id), contact_id)
    return None

@router.get("/autocomplete", response_model=list[ContactRead])
async def autocomplete_contacts(
    current_user: CurrentUser,
    session: SessionDep,
    q: str = Query(default=""),
    limit: int = Query(default=10, le=50),
):
    return await contacts_service.autocomplete_contacts(session, str(current_user.id), q, limit)

@router.get("/groups", response_model=list[ContactGroupRead])
async def list_contact_groups(
    current_user: CurrentUser, session: SessionDep,
):
    return await contacts_service.list_contact_groups(session, str(current_user.id))

@router.post("/groups", response_model=ContactGroupRead, status_code=status.HTTP_201_CREATED)
async def create_contact_group(
    current_user: CurrentUser, session: SessionDep, data: ContactGroupCreate,
):
    return await contacts_service.create_contact_group(session, str(current_user.id), data)
