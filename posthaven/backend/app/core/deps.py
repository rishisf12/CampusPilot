"""FastAPI dependencies: DB session, current user, admin guard."""
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from app.models.user import User
from app.core.security import decode_token
from app.core.config import settings


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user_optional(request: Request, session: SessionDep) -> User | None:
    """Return current user from httpOnly cookie, or None if no valid session."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


async def get_current_user(session: SessionDep, request: Request) -> User:
    """Require a valid, active user session. Raises 401 otherwise."""
    user = await get_current_user_optional(request, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_admin(session: SessionDep, request: Request) -> User:
    """Require an admin user."""
    user = await get_current_user(session, request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin required",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
