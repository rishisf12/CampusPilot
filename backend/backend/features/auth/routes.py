"""Auth routes: signup, verify-email, login, me, logout."""
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import jwt
from passlib.hash import sha256_crypt
import aiosmtplib
from email.message import EmailMessage
import random

from core.database import get_session
from models import User, UserProfile
from core.config import get_settings
from core.deps import get_current_user
from features.auth import passkeys as passkey_service, password_reset as password_reset_service, signup as signup_verification_service

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


class StartSignupRequest(BaseModel):
    #: Only the address. Nothing is created yet - that happens after the code is
    #: confirmed, so a mistyped code no longer leaves a half-built account.
    email: EmailStr


class VerifySignupRequest(BaseModel):
    email: EmailStr
    code: str


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
    role: str = "student"

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


async def send_password_reset_email(email: str, code: str) -> None:
    """
    Email a reset code to the address already on the account.

    Says plainly what will happen, because the consequence is bigger than a
    password change: signing out everywhere and dropping the passkeys is
    surprising if nobody warned you.
    """
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = email
    msg["Subject"] = "CampusPilot — Reset your password"
    msg.set_content(f"""
Someone asked to reset the password for your CampusPilot account.

Your reset code is: {code}

This code expires in 15 minutes.

Once you use it:
  * your password changes
  * every signed-in device is signed out
  * any passkeys on your account are removed, so you will need to set up a new one

If you did not ask for this, ignore this email and nothing will change.
Your current password still works.

If this keeps happening, tell your department - someone may have your username.
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
        logger.info("Password reset email sent to %s", email)
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {e}")
        raise


def create_access_token(
    user_id: int, username: str, password_changed_at: Optional[datetime] = None
) -> str:
    """
    Mint a session token.

    The password-change time is baked in as ``pw_at``. :func:`get_current_user`
    refuses any token older than the account's current password, so resetting a
    password signs out every device - including whoever prompted the reset.

    A token with no ``pw_at`` predates this field and is treated as older than any
    reset, i.e. invalid. Rejecting is the safe direction for an existing token.
    """
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if password_changed_at is not None:
        # Naive UTC in the database; stamp as epoch seconds.
        payload["pw_at"] = int(password_changed_at.replace(tzinfo=timezone.utc).timestamp())
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password(plain: str, hashed: str) -> bool:
    return sha256_crypt.verify(plain, hashed)


def hash_password(password: str) -> str:
    return sha256_crypt.hash(password)


# ---------- Routes ----------

@router.post("/signup/start", response_model=dict)
async def start_signup(
    data: StartSignupRequest, session: Session = Depends(get_session)
):
    """
    Step 1 of registration: prove the address before any account exists.

    Always answers the same way, whether or not a code was actually sent, and
    whether or not the address already has an account. Revealing that here would
    turn this into a way to enumerate students; it is answered later, by
    ``/auth/signup``, once the requester has proved they can read mail there.
    """
    try:
        code, retry_after = signup_verification_service.start(session, data.email)
    except signup_verification_service.SignupVerificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if code is not None:
        try:
            await send_verification_email(data.email.lower(), code)
        except Exception:  # noqa: BLE001 - a mail failure must not leak the account
            logger.error("Signup verification email failed for %s", data.email.lower())

    # `retry_after` is deliberately not returned: it would reveal that something
    # already existed for this address. The client rate-limits itself instead.
    return {"message": signup_verification_service.GENERIC_MESSAGE}


@router.post("/signup/verify", response_model=dict)
async def verify_signup(
    data: VerifySignupRequest, session: Session = Depends(get_session)
):
    """
    Step 2: confirm the code, which marks the address proven.

    Also completes any account left unverified by the old signup order, so a
    student who abandoned the previous flow is not stranded.
    """
    try:
        signup_verification_service.verify(session, data.email, data.code)
    except signup_verification_service.SignupVerificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    existing = session.exec(
        select(User).where(User.email == data.email.lower())
    ).first()
    if existing is not None and not existing.is_email_verified:
        existing.is_email_verified = True
        session.add(existing)
        session.commit()

    return {"message": "Email verified. You can finish creating your account."}


@router.post("/signup", response_model=dict)
async def signup(data: SignupRequest, session: Session = Depends(get_session)):
    """
    Step 3: create the account.

    Refused unless the address was already proven by ``/signup/verify``. That gate
    is the whole point of the reordering: the account is now created already
    verified, because the mailbox has been shown to belong to whoever is asking.

    The duplicate checks below are therefore safe to report - by this point the
    requester controls the address, so learning that it is taken does not hand
    them anything they could not already establish.
    """
    if not signup_verification_service.is_verified(session, data.email):
        raise HTTPException(
            status_code=400,
            detail="Verify your email address first.",
        )

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
        # Already proven by /signup/verify - see the gate at the top of this route.
        is_email_verified=True,
        # Students can only ever create student accounts; admin is granted by
        # tools/make_admin.py, never by signup.
        role="student",
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

    # The address was proven before this point, so the account starts verified
    # and no further code is sent. The pending record has served its purpose.
    signup_verification_service.clear(session, data.email)

    return {"message": "Account created.", "email": data.email.lower()}


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

    access_token = create_access_token(user.id, user.username, user.password_changed_at)
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
        role=user.role or "student",
    )


@router.post("/logout", response_model=dict)
async def logout():
    """Logout (client-side token removal)."""
    return {"message": "Logged out successfully"}


# ---------- Passkeys (WebAuthn) ----------

class PasskeyLoginOptionsRequest(BaseModel):
    #: Optional. With a username the device is offered only that account's
    #: passkeys; without one it offers any passkey it holds.
    username: Optional[str] = None


class PasskeyRegistrationRequest(BaseModel):
    #: The credential JSON produced by ``navigator.credentials.create()``.
    credential: dict
    #: The challenge from ``/passkeys/register/options``.
    challenge: str
    label: Optional[str] = None


class PasskeyLoginRequest(BaseModel):
    #: The credential JSON produced by ``navigator.credentials.get()``.
    credential: dict
    #: The challenge from ``/passkeys/login/options``.
    challenge: str


class ForgotPasswordRequest(BaseModel):
    #: Username or registered email - whichever the student remembers.
    identifier: str


class ResetPasswordRequest(BaseModel):
    identifier: str
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.get("/passkeys")
async def list_passkeys(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    The signed-in user's passkeys.

    Used to decide whether to offer enrolment: a password login on an account
    with no passkeys yet is exactly when the prompt should appear.
    """
    records = passkey_service.list_credentials(session, user.id)
    return {
        "has_passkey": bool(records),
        "count": len(records),
        "passkeys": [passkey_service.describe(record) for record in records],
    }


@router.post("/passkeys/register/options")
async def passkey_register_options(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Start enrolment: issue a challenge and describe the acceptable devices."""
    try:
        return passkey_service.registration_options(
            session, user, user_agent=request.headers.get("user-agent")
        )
    except passkey_service.PasskeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/passkeys/register")
async def passkey_register(
    body: PasskeyRegistrationRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Finish enrolment by verifying the device's attestation.

    Authentication is required: enrolling a passkey is handing the account a
    passwordless way in, so it must never be possible from a signed-out session.
    """
    try:
        record = passkey_service.complete_registration(
            session, user, body.credential, body.challenge, body.label
        )
    except passkey_service.PasskeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"message": "Passkey set up.", "passkey": passkey_service.describe(record)}


@router.post("/passkeys/login/options")
async def passkey_login_options(
    body: PasskeyLoginOptionsRequest,
    session: Session = Depends(get_session),
):
    """
    Start passwordless sign-in.

    Deliberately unauthenticated - that is the point - but it only ever returns
    a challenge. No account detail is disclosed, and an unknown username gets the
    same message as one with no passkey, so this cannot enumerate students.
    """
    try:
        return passkey_service.authentication_options(session, body.username)
    except passkey_service.PasskeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/passkeys/login")
async def passkey_login(
    body: PasskeyLoginRequest, session: Session = Depends(get_session)
):
    """
    Finish passwordless sign-in and issue the usual session token.

    The password is not touched: this is a way *around* it, not a way to change
    it, so a forgotten password needs no reset.
    """
    try:
        user = passkey_service.complete_authentication(
            session, body.credential, body.challenge
        )
    except passkey_service.PasskeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox for the verification code.",
        )

    return TokenResponse(
        access_token=create_access_token(
            user.id, user.username, user.password_changed_at
        )
    )


# ---------- Password reset by emailed code ----------

#: Deliberately one sentence, returned whether or not the account exists. Anything
#: more specific turns this into a way to discover who has an account here.
_RESET_SENT_MESSAGE = (
    "If that account exists, a reset code is on its way to the registered email address."
)


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest, session: Session = Depends(get_session)
):
    """
    Send a reset code to the account's registered address.

    Always returns the same 200 and the same message, so this cannot be used to
    find out which usernames are registered. The code only ever goes to the
    address already on the account - never to one supplied in the request, which
    is what stops this being used to send mail anywhere at all.
    """
    try:
        code = password_reset_service.request_code(session, body.identifier)
    except password_reset_service.PasswordResetError:
        # Still a success, for the same reason.
        return {"message": _RESET_SENT_MESSAGE}

    if code is not None:
        user = password_reset_service.find_account(session, body.identifier)
        try:
            await send_password_reset_email(user.email, code)
        except Exception:  # noqa: BLE001 - SMTP failure must not leak the account
            logger.error("Reset email failed; the code is on file and still usable")
        else:
            # The code was emailed, so it must not linger in the log.
            logger.debug("Reset code issued and emailed")

    return {"message": _RESET_SENT_MESSAGE}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest, session: Session = Depends(get_session)
):
    """
    Set a new password from an emailed code.

    Also signs out every other device and removes every passkey. A reset is
    usually prompted by the account feeling unsafe, so leaving a compromised
    device signed in - or holding a passkey - would defeat the point of doing it.
    The password is not sent back and the account is not signed in here; the
    student signs in with the new password like anyone else.
    """
    try:
        result = password_reset_service.complete_reset(
            session, body.identifier, body.code, body.new_password
        )
    except password_reset_service.PasswordResetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "message": "Password updated. Please sign in with your new password.",
        "passkeys_revoked": result["passkeys_revoked"],
    }


@router.delete("/passkeys/{credential_id:path}")
async def delete_passkey(
    credential_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Remove a passkey, e.g. after losing the device that held it.

    Deliberately possible even when it is the *last* one: a student who lost
    their only device has already lost that route, and keeping the row would stop
    them enrolling a replacement. The password is untouched either way.
    """
    try:
        passkey_service.delete_credential(session, user, credential_id)
    except passkey_service.PasskeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Passkey removed."}