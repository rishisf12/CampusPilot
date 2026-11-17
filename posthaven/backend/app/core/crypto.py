"""Encryption at rest for mail credentials (AES-GCM via Fernet)."""
from app.core.security import encrypt_secret, decrypt_secret


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a mail credential (password/oauth token) for storage."""
    return encrypt_secret(plaintext)


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a stored mail credential back to plaintext."""
    return decrypt_secret(ciphertext)
