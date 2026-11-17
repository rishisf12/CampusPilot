"""Auth service: register, login, refresh, logout, change password, audit."""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import HTTPException, Request
from starlette import status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, delete, func

from app.models.user import User, UserCreate, UserRead
from app.models.token import RefreshToken, RefreshTokenCreate, TokenPair
from app.models.audit import AuditLog
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings


# In-memory rate limiter (Redis-backed in production; simple dict for dev/single instance)
_RATE_LIMIT_WINDOW = timedelta(minutes=15)
_rate_limit_store: dict[str, list[datetime]] = {}


def _rate_limit_key(identifier: str, endpoint: str) -> str:
    return f"{endpoint}:{identifier}"


def is_rate_limited(identifier: str, endpoint: str, max_attempts: int = 5) -> bool:
    now = datetime.now(timezone.utc)
    key = _rate_limit_key(identifier, endpoint)
    window_start = now - _RATE_LIMIT_WINDOW
    attempts = _rate_limit_store.get(key, [])
    # prune old
    attempts = [t for t in attempts if t > window_start]
    _rate_limit_store[key] = attempts
    if len(attempts) >= max_attempts:
        return True
    attempts.append(now)
    _rate_limit_store[key] = attempts
    return False


async def _audit(
    session: AsyncSession,
    action: str,
    user: User | None,
    request: Request | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: str | None = None,
) -> None:
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    session.add(entry)


async def register(
    session: AsyncSession,
    data: UserCreate,
    request: Request | None = None,
) -> tuple[User, bool]:
    """Register a new user. First user becomes admin. Returns (user, is_first)."""
    # Rate limit by IP
    ident = request.client.host if request and request.client else "unknown"
    if is_rate_limited(ident, "auth:register", max_attempts=10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Try again later.",
        )

    # Case-insensitive email uniqueness
    existing = await session.exec(
        select(User).where(User.email.ilike(data.email.strip().lower()))
    )
    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    count = (await session.exec(select(func.count(User.id)))).one()
    is_first = count == 0

    user = User(
        email=data.email.strip().lower(),
        display_name=data.display_name,
        is_admin=is_first,
        is_active=True,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    await _audit(session, "auth:register", user, request, resource_type="user", resource_id=str(user.id))
    await session.commit()
    return user, is_first


async def authenticate(
    session: AsyncSession,
    email: str,
    password: str,
    request: Request | None = None,
) -> User | None:
    """Verify credentials. Returns user or None. Rate-limited by IP+email."""
    ident = (request.client.host if request and request.client else "unknown") + ":" + email.lower()
    if is_rate_limited(ident, "auth:login", max_attempts=10):
        return None  # generic failure to avoid revealing rate limit

    user = await session.exec(select(User).where(User.email.ilike(email.strip().lower())))
    user = user.first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> TokenPair:
    """Create access + rotating refresh token, store refresh hash."""
    # Revoke all existing refresh tokens for this user on login (single-device session)
    await session.exec(delete(RefreshToken).where(RefreshToken.user_id == user.id))

    refresh_raw = create_refresh_token(user.id)
    refresh_hash = _hash_token(refresh_raw)
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(refresh_token)
    await session.commit()

    access_token = create_access_token(user.id)
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_raw,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def rotate_refresh_token(
    session: AsyncSession,
    refresh_raw: str,
    request: Request | None = None,
) -> TokenPair | None:
    """Rotate a refresh token. Reuse detection revokes the whole family."""
    token_hash = _hash_token(refresh_raw)
    token = await session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = token.first()
    if not token or token.revoked or token.expires_at < datetime.now(timezone.utc):
        # Reuse of a revoked/expired token: revoke entire family (defense in depth)
        if token:
            token.revoked = True
            session.add(token)
        # Revoke all tokens for this user (family revocation on reuse)
        await session.exec(delete(RefreshToken).where(RefreshToken.user_id == token.user_id))
        await session.commit()
        return None

    # Verify the user still exists and is active
    user = await session.get(User, token.user_id)
    if not user or not user.is_active:
        token.revoked = True
        session.add(token)
        await session.commit()
        return None

    # Revoke current, issue new
    token.revoked = True
    new_raw = create_refresh_token(user.id)
    new_hash = _hash_token(new_raw)
    token.replaced_by_token_hash = new_hash
    new_token = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(new_token)
    await session.commit()

    access_token = create_access_token(user.id)
    return TokenPair(
        access_token=access_token,
        refresh_token=new_raw,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def revoke_refresh_token(session: AsyncSession, refresh_raw: str) -> None:
    token_hash = _hash_token(refresh_raw)
    token = await session.exec(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token = token.first()
    if token:
        token.revoked = True
        session.add(token)
        await session.commit()


async def revoke_all_user_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.exec(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await session.commit()


async def change_password(
    session: AsyncSession,
    user: User,
    new_password: str,
    request: Request | None = None,
) -> None:
    user.password_hash = hash_password(new_password)
    session.add(user)
    await session.commit()
    # Invalidate all sessions on password change
    await revoke_all_user_tokens(session, user.id)
    await _audit(session, "auth:change_password", user, request, resource_type="user", resource_id=str(user.id))
    await session.commit()
