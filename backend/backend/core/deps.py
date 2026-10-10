"""Shared FastAPI dependencies: bearer-token authentication."""
import logging
from datetime import timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from core.config import get_settings
from core.database import get_session
from models import User

logger = logging.getLogger(__name__)
settings = get_settings()

security = HTTPBearer(auto_error=False)


def _token_predates_password(payload: dict, user: User) -> bool:
    """
    Was this token issued before the account's current password?

    A password reset stamps ``password_changed_at``. Any token minted earlier must
    stop working, or resetting the password would not actually lock out whoever
    prompted the reset - the attacker's 7-day token would keep going.

    A token with no ``pw_at`` predates the feature, so it counts as older than any
    reset and is refused. Rejecting is the safe direction.
    """
    changed = user.password_changed_at
    if changed is None:
        return False
    issued = payload.get("pw_at")
    if issued is None:
        return True
    changed_epoch = int(changed.replace(tzinfo=timezone.utc).timestamp())
    return int(issued) < changed_epoch


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    """
    Resolve the authenticated user from the ``Authorization: Bearer`` header.

    Raises 401 when the header is missing or the token cannot be decoded.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = int(payload.get("sub"))
    except Exception as exc:
        logger.info("Token rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if _token_predates_password(payload, user):
        # The password was reset after this token was minted, so the session it
        # represents no longer has the owner's consent.
        logger.info("Token rejected for user %s: older than password change", user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired - please sign in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """Same as :func:`get_current_user` but returns ``None`` instead of raising."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = int(payload.get("sub"))
    except Exception:  # noqa: BLE001
        return None
    user = session.exec(select(User).where(User.id == user_id)).first()
    # Same rule as get_current_user: a token older than the current password is
    # not a session, it is a leftover.
    if user is None or _token_predates_password(payload, user):
        return None
    return user


def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Require the signed-in user to be an admin (developer).

    Students get a 403, not a 404: the endpoint exists, they are just not
    allowed in. Admin is granted with ``tools/make_admin.py``, never by signup.
    """
    if (user.role or "student") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user