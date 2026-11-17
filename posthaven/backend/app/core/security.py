"""Security primitives: password hashing, JWT, encryption at rest, CSRF."""
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid
import secrets

from passlib.context import CryptContext
from jose import jwt, JWTError
from cryptography.fernet import Fernet
from app.core.config import settings

# --- Password hashing (Argon2 via passlib) ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT ---
def create_access_token(subject: str | uuid.UUID, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(subject: str | uuid.UUID, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


# --- Encryption at rest (Fernet / AES-GCM compatible) ---
def get_fernet() -> Fernet:
    # Fernet key must be 32 url-safe base64-encoded bytes. Derive deterministically
    # from ENCRYPTION_KEY so it's stable across restarts.
    import base64
    import hashlib

    key_material = hashlib.sha256(settings.ENCRYPTION_KEY.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_material)
    return Fernet(fernet_key)


def encrypt_secret(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


# --- CSRF ---
def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
