from typing import Optional
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from fastapi import HTTPException, status

from app.models.account import MailAccount, MailAccountCreate, MailAccountUpdate, MailAccountRead, MailAccountTestResult
from app.models.user import User
from app.core.crypto import encrypt_credential
from app.services.imap_client import test_imap_connection
from app.services.smtp_client import test_smtp_connection


async def list_accounts(session: AsyncSession, user: User) -> list[MailAccount]:
    result = await session.exec(
        select(MailAccount).where(MailAccount.user_id == user.id).order_by(MailAccount.created_at.desc())
    )
    return result.all()


async def get_account(session: AsyncSession, user: User, account_id: UUID) -> MailAccount:
    result = await session.exec(
        select(MailAccount).where(MailAccount.id == account_id, MailAccount.user_id == user.id)
    )
    account = result.first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


async def create_account(
    session: AsyncSession,
    user: User,
    data: MailAccountCreate,
) -> MailAccount:
    # Test IMAP + SMTP before saving
    imap_result = await test_imap_connection(
        host=data.host, port=data.imap_port, username=data.username,
        password=data.password, security=data.imap_security,
    )
    if not imap_result["ok"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IMAP test failed: {imap_result['message']}",
        )

    smtp_result = await test_smtp_connection(
        host=data.host, port=data.smtp_port, username=data.username,
        password=data.password, security=data.smtp_security,
    )
    if not smtp_result["ok"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SMTP test failed: {smtp_result['message']}",
        )

    account = MailAccount(
        user_id=user.id,
        provider=data.provider,
        host=data.host,
        imap_port=data.imap_port,
        smtp_port=data.smtp_port,
        imap_security=data.imap_security,
        smtp_security=data.smtp_security,
        username=data.username,
        encrypted_password=encrypt_credential(data.password),
        is_enabled=data.is_enabled,
        sync_enabled=data.sync_enabled,
        status="connected",
        status_message=None,
        capabilities=",".join(imap_result.get("imap_capabilities") or []),
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def update_account(
    session: AsyncSession,
    user: User,
    account_id: UUID,
    data: MailAccountUpdate,
) -> MailAccount:
    account = await get_account(session, user, account_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def delete_account(session: AsyncSession, user: User, account_id: UUID) -> None:
    account = await get_account(session, user, account_id)
    await session.delete(account)
    await session.commit()


async def test_account_connection(
    session: AsyncSession,
    user: User,
    account_id: Optional[UUID] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    security: str = "ssl",
) -> MailAccountTestResult:
    """Test connection for an existing account or raw parameters."""
    if account_id:
        account = await get_account(session, user, account_id)
        password = decrypt_credential(account.encrypted_password) if account.encrypted_password else ""
        username = account.username
        host = account.host
        port = account.imap_port
        security = account.imap_security

    if not host or not port or not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing connection parameters")

    result = await test_imap_connection(
        host=host, port=port, username=username, password=password or "", security=security
    )
    return MailAccountTestResult(
        ok=result["ok"],
        imap_capabilities=result.get("imap_capabilities"),
        message=result["message"],
    )
