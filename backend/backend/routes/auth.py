"""Auth routes: signup, verify-email, login, me, logout."""
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import jwt
from passlib.hash import sha256_crypt
import aiosmtplib
from email.message import EmailMessage
import random

from database import get_session
from models import User, UserProfile
from config import get_settings
from routes.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Auth"])

settings = get_settings()
ALLOWED_EMAIL_DOMAIN = settings.ALLOWED_EMAIL_DOMAIN


# ---------- Pydantic Models ----------

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    gender: str
    programme: str
    semester: int
    branch: str
    username: str
    roll_number: str
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, v):
        if not v.endswith(ALLOWED_EMAIL_DOMAIN):
            raise ValueError(f"Email must be from {ALLOWED_EMAIL_DOMAIN} domain")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class ResendCodeRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    username: str
    roll_number: Optional[str] = None
    is_email_verified: bool

    class Config:
        from_attributes = True


# ---------- Email Verification Code Storage ----------
# In production, use Redis or database. For now, in-memory with TTL.
verification_codes: dict[str, dict] = {}


def generate_code() -> str:
    return str(random.randint(100000, 999999))


async def send_verification_email(email: str, code: str):
    """Send verification code via email."""
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = email
    msg["Subject"] = "CampusPilot — Verify Your Email"
    msg.set_content(f"""
Welcome to CampusPilot!

Your verification code is: {code}

This code expires in 10 minutes.

If you didn't request this, please ignore this email.
""")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            start_tls=True,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
        )
        logger.info(f"Verification email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        raise


def create_access_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password(plain: str, hashed: str) -> bool:
    return sha256_crypt.verify(plain, hashed)


def hash_password(password: str) -> str:
    return sha256_crypt.hash(password)


# ---------- Routes ----------

@router.post("/signup", response_model=dict)
async def signup(data: SignupRequest, session: Session = Depends(get_session)):
    """Register a new user."""
    # Check if email exists
    existing_email = session.exec(select(User).where(User.email == data.email.lower())).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if username exists
    existing_user = session.exec(select(User).where(User.username == data.username)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Check if roll number exists
    if data.roll_number:
        existing_roll = session.exec(select(User).where(User.roll_number == data.roll_number.upper())).first()
        if existing_roll:
            raise HTTPException(status_code=400, detail="Roll number already registered")

    # Hash password
    password_hash = hash_password(data.password)

    # Create user
    now = datetime.utcnow()
    user = User(
        email=data.email.lower(),
        password_hash=password_hash,
        full_name=f"{data.first_name} {data.last_name}",
        username=data.username,
        roll_number=data.roll_number.upper(),
        is_email_verified=False,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create profile
    profile = UserProfile(
        user_id=user.id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=data.gender,
        programme=data.programme,
        semester=data.semester,
        branch=data.branch,
        elective_codes=[],
    )
    session.add(profile)
    session.commit()

    # Generate and send verification code
    code = generate_code()
    verification_codes[data.email.lower()] = {
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "user_id": user.id,
    }

    await send_verification_email(data.email.lower(), code)

    return {"message": "Account created. Verification code sent to your email.", "email": data.email.lower()}


@router.post("/verify-email", response_model=dict)
async def verify_email(data: VerifyEmailRequest, session: Session = Depends(get_session)):
    """Verify email with 6-digit code."""
    email = data.email.lower()
    record = verification_codes.get(email)

    if not record:
        raise HTTPException(status_code=400, detail="No verification code found. Request a new one.")

    if datetime.now(timezone.utc) > record["expires_at"]:
        del verification_codes[email]
        raise HTTPException(status_code=400, detail="Verification code expired. Request a new one.")

    if record["code"] != data.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Mark user as verified
    user = session.exec(select(User).where(User.id == record["user_id"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_email_verified = True
    session.add(user)
    session.commit()

    # Clean up
    del verification_codes[email]

    return {"message": "Email verified successfully. You can now log in."}


@router.post("/resend-code", response_model=dict)
async def resend_code(data: ResendCodeRequest, session: Session = Depends(get_session)):
    """Resend verification code."""
    email = data.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    # Generate new code
    code = generate_code()
    verification_codes[email] = {
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "user_id": user.id,
    }

    await send_verification_email(email, code)

    return {"message": "Verification code resent."}


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """OAuth2 password flow login."""
    user = session.exec(select(User).where(User.username == form.username)).first()

    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox for the verification code.",
        )

    access_token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """
    Return the signed-in user.

    Uses the bearer-token dependency so the token is read from the
    ``Authorization`` header (previously it was treated as a query parameter,
    which made every session look unauthenticated).
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        username=user.username,
        roll_number=user.roll_number,
        is_email_verified=user.is_email_verified,
    )


@router.post("/logout", response_model=dict)
async def logout():
    """Logout (client-side token removal)."""
    return {"message": "Logged out successfully"}