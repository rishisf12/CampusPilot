"""Auth endpoints: register, login, refresh, logout, me, change-password."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.core.deps import get_current_user, get_current_user_optional, SessionDep, CurrentUser
from app.core.security import create_access_token
from app.core.config import settings
from app.services import auth as auth_service
from app.models.user import UserCreate, UserRead, UserRegisterResponse

class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    new_password: str

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = settings.ENV == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")


@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    response: Response,
    data: UserCreate,
    session: SessionDep,
    request: Request,
):
    user, is_first = await auth_service.register(session, data, request)
    token_pair = await auth_service.issue_token_pair(session, user)
    _set_auth_cookies(response, token_pair.access_token, token_pair.refresh_token)
    return UserRegisterResponse(
        user=UserRead.model_validate(user),
        message="First user is admin" if is_first else "Account created successfully",
    )


@router.post("/login", response_model=UserRead)
async def login(
    response: Response,
    payload: LoginRequest,
    session: SessionDep,
    request: Request,
):
    user = await auth_service.authenticate(session, payload.email, payload.password, request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token_pair = await auth_service.issue_token_pair(session, user)
    _set_auth_cookies(response, token_pair.access_token, token_pair.refresh_token)
    return UserRead.model_validate(user)


@router.post("/refresh", response_model=UserRead)
async def refresh(
    response: Response,
    request: Request,
    session: SessionDep,
):
    from app.core.security import decode_token
    from app.models.user import User

    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )
    token_pair = await auth_service.rotate_refresh_token(session, refresh_token, request)
    if not token_pair:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    _set_auth_cookies(response, token_pair.access_token, token_pair.refresh_token)
    payload = decode_token(token_pair.access_token)
    user = await session.get(User, payload["sub"])
    if not user or not user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    request: Request,
    session: SessionDep,
    current_user: Annotated[object, Depends(get_current_user_optional)],
):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await auth_service.revoke_refresh_token(session, refresh_token)
    _clear_auth_cookies(response)
    return None


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser):
    return UserRead.model_validate(current_user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    response: Response,
    payload: ChangePasswordRequest,
    session: SessionDep,
    current_user: CurrentUser,
    request: Request,
):
    await auth_service.change_password(session, current_user, payload.new_password, request)
    _clear_auth_cookies(response)
    return None
