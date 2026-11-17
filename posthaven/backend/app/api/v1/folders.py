from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.models.folder import Folder, FolderRead, FolderCreate, FolderUpdate
from app.models.account import MailAccount

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("", response_model=list[FolderRead])
async def list_folders(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: UUID = Query(...),
):
    # Verify account ownership
    account = await session.get(MailAccount, account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    result = await session.exec(
        select(Folder).where(Folder.account_id == account_id).order_by(Folder.name)
    )
    return result.all()


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
async def create_folder(
    current_user: CurrentUser,
    session: SessionDep,
    data: FolderCreate,
):
    account = await session.get(MailAccount, data.account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    folder = Folder(
        user_id=current_user.id,
        account_id=data.account_id,
        name=data.name,
        delimiter=data.delimiter,
        parent_id=data.parent_id,
        special_use=data.special_use,
        subscribed=data.subscribed,
    )
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return folder


@router.get("/{folder_id}", response_model=FolderRead)
async def get_folder(
    current_user: CurrentUser,
    session: SessionDep,
    folder_id: UUID,
):
    folder = await session.get(Folder, folder_id)
    if not folder or folder.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


@router.patch("/{folder_id}", response_model=FolderRead)
async def update_folder(
    current_user: CurrentUser,
    session: SessionDep,
    folder_id: UUID,
    data: FolderUpdate,
):
    folder = await session.get(Folder, folder_id)
    if not folder or folder.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(folder, field, value)
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    current_user: CurrentUser,
    session: SessionDep,
    folder_id: UUID,
):
    folder = await session.get(Folder, folder_id)
    if not folder or folder.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    await session.delete(folder)
    await session.commit()
    return None
