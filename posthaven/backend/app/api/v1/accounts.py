from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.services import accounts as accounts_service
from app.models.account import (
    MailAccount,
    MailAccountRead,
    MailAccountCreate,
    MailAccountUpdate,
    MailAccountTestResult,
)
from app.services.sync import SyncService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[MailAccountRead])
async def list_accounts(
    current_user: CurrentUser,
    session: SessionDep,
):
    return await accounts_service.list_accounts(session, current_user)


@router.post("", response_model=MailAccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    current_user: CurrentUser,
    session: SessionDep,
    data: MailAccountCreate,
):
    return await accounts_service.create_account(session, current_user, data)


@router.get("/{account_id}", response_model=MailAccountRead)
async def get_account(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: UUID,
):
    return await accounts_service.get_account(session, current_user, account_id)


@router.patch("/{account_id}", response_model=MailAccountRead)
async def update_account(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: UUID,
    data: MailAccountUpdate,
):
    return await accounts_service.update_account(session, current_user, account_id, data)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: UUID,
):
    await accounts_service.delete_account(session, current_user, account_id)
    return None


@router.post("/test", response_model=MailAccountTestResult)
async def test_connection(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: Optional[UUID] = Query(default=None),
    host: Optional[str] = Query(default=None),
    port: Optional[int] = Query(default=None),
    username: Optional[str] = Query(default=None),
    password: Optional[str] = Query(default=None),
    security: str = Query(default="ssl"),
):
    return await accounts_service.test_account_connection(
        session=session,
        user=current_user,
        account_id=account_id,
        host=host,
        port=port,
        username=username,
        password=password,
        security=security,
    )


@router.post("/{account_id}/sync", response_model=dict)
async def sync_account(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: UUID,
    headers_limit: int = Query(default=200, le=1000),
):
    account = await accounts_service.get_account(session, current_user, account_id)
    svc = SyncService(session, account, current_user.id)
    stats = await svc.sync_all(headers_limit=headers_limit)
    return stats
