"""
Password reset by emailed code.

This is the fallback for someone who has neither a working password nor a usable
passkey. It is deliberately the weakest of the three sign-in routes, so it is
built to be uninteresting to attack:

- the response never says whether an account exists, so the endpoint cannot be
  used to enumerate students
- the code only ever goes to the address already on the account, never to one the
  requester supplies
- codes are stored hashed, expire quickly, are single-use, and die after a few
  wrong guesses
- sending is rate limited, so a known address cannot be used to flood an inbox

A reset also has to *contain* an incident, not just restore access. Changing the
password must be enough to lock out whoever prompted the student to do it, so a
successful reset invalidates existing sessions and revokes every passkey - a
compromised device keeps neither.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from models import PasswordResetCode, PasskeyCredential, User

logger = logging.getLogger(__name__)

#: Six digits, matching the existing email-verification codes.
CODE_LENGTH = 6

#: Long enough to survive a slow inbox, short enough to keep the guessing window
#: small.
CODE_TTL = timedelta(minutes=15)

#: Wrong guesses allowed per code. Six digits is a million possibilities, so a
#: tight budget is what makes the code unguessable rather than merely hidden.
MAX_ATTEMPTS = 5

#: Codes issued for one account inside this window, before sending is refused.
SEND_COOLDOWN = timedelta(minutes=5)

#: Codes kept per account. Older ones are swept, so requesting repeatedly cannot
#: leave a trail of live codes.
MAX_LIVE_CODES = 3

#: Sweep anything older than this so the table cannot grow without bound.
CODE_RETENTION = timedelta(days=1)


class PasswordResetError(Exception):
    """A reset could not proceed. The message is safe to show the requester."""


def _now() -> datetime:
    """Naive UTC, matching how the database stores timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_code(user_id: int, code: str) -> str:
    """
    Hash the code, salted with the account id.

    The salt is not secrecy - it stops one precomputed table cracking every code
    in the database at once. What actually protects the code is the attempt
    counter.
    """
    return hashlib.sha256(f"{user_id}:{code}".encode("utf-8")).hexdigest()


def _purge(session: Session) -> None:
    cutoff = _now() - CODE_RETENTION
    for stale in session.exec(select(PasswordResetCode)).all():
        if stale.created_at is not None and stale.created_at < cutoff:
            session.delete(stale)


def find_account(session: Session, identifier: str) -> Optional[User]:
    """
    Look up a user by username or registered email.

    Both are accepted: a student who has forgotten their password may equally
    have forgotten which of the two they normally type.
    """
    value = (identifier or "").strip()
    if not value:
        return None
    lowered = value.lower()
    return session.exec(
        select(User).where(
            (User.username == value) | (User.email == lowered)
        )
    ).first()


def _live_codes(session: Session, user_id: int) -> List[PasswordResetCode]:
    now = _now()
    live = []
    for row in session.exec(
        select(PasswordResetCode).where(PasswordResetCode.user_id == user_id)
    ).all():
        if row.used_at is not None:
            continue
        if row.created_at is None or row.created_at + CODE_TTL <= now:
            continue
        live.append(row)
    return live


def request_code(session: Session, identifier: str) -> Optional[str]:
    """
    Issue a code for an account, or return ``None`` if there is no such account.

    The caller must not tell the requester which happened. Returning the code (not
    just success) keeps it out of any response body and lets the tests assert on
    the real value.

    Raises :class:`PasswordResetError` when the account is known but sending is
    rate limited - also an answer the caller must not disclose.
    """
    user = find_account(session, identifier)
    if user is None:
        return None

    _purge(session)

    now = _now()
    live = _live_codes(session, user.id)
    if live and live[-1].created_at + SEND_COOLDOWN > now:
        raise PasswordResetError(
            "A reset code was sent recently. Please wait a few minutes before asking for another."
        )

    # Only the newest few stay live, so an old code in an old inbox stops working.
    if len(live) > MAX_LIVE_CODES:
        for surplus in live[: len(live) - MAX_LIVE_CODES]:
            session.delete(surplus)

    code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
    session.add(PasswordResetCode(user_id=user.id, code_hash=_hash_code(user.id, code)))
    session.commit()
    logger.info("Password reset code issued for user %s", user.id)
    return code


def _claim(session: Session, user: User, code: str) -> Optional[PasswordResetCode]:
    """
    Find the live code matching ``code``, counting a wrong guess against it.

    A wrong code increments the newest live code's attempt counter rather than
    creating a new row, so an attacker cannot make guesses "free" by first
    requesting a fresh code. Once the budget is spent the row is *deleted*, not
    merely refused - a code that stays on file with its budget gone would still
    absorb guesses indefinitely, which is no limit at all.
    """
    live = _live_codes(session, user.id)
    wanted = _hash_code(user.id, code)

    for row in live:
        if secrets.compare_digest(row.code_hash, wanted):
            if row.attempts >= MAX_ATTEMPTS:
                session.delete(row)
                session.commit()
                raise PasswordResetError(
                    "Too many wrong attempts. Please request a new code."
                )
            return row

    if live:
        newest = max(live, key=lambda item: item.created_at)
        newest.attempts += 1
        exhausted = newest.attempts >= MAX_ATTEMPTS
        session.add(newest)
        session.commit()
        if exhausted:
            session.delete(newest)
            session.commit()
            raise PasswordResetError(
                "Too many wrong attempts. Please request a new code."
            )

    return None


def complete_reset(
    session: Session, identifier: str, code: str, new_password: str
) -> Dict[str, Any]:
    """
    Set a new password and shut out whoever had the old one.

    On success this revokes every passkey and stamps ``password_changed_at``, which
    invalidates all existing session tokens. Both are deliberate: a student
    resetting because the account felt compromised must not leave the attacker
    holding a working credential or a live session.
    """
    user = find_account(session, identifier)
    if user is None:
        # Never confirm or deny an account's existence through this path.
        raise PasswordResetError("That code is not valid.")

    row = _claim(session, user, code.strip())
    if row is None:
        raise PasswordResetError("That code is not valid.")

    from features.auth.routes import hash_password

    now = _now()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    session.add(user)

    # Single use, whether or not it worked.
    row.used_at = now
    session.add(row)

    revoked = 0
    for credential in session.exec(
        select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
    ).all():
        session.delete(credential)
        revoked += 1

    # Any other live codes for this account die with the password they were
    # issued to change.
    for other in _live_codes(session, user.id):
        if other.id != row.id:
            session.delete(other)

    session.commit()
    logger.info(
        "Password reset completed for user %s; %d passkey(s) revoked", user.id, revoked
    )
    return {"passkeys_revoked": revoked}


def seconds_until_retry(session: Session, identifier: str) -> int:
    """Seconds until another code may be requested, for the client to show."""
    user = find_account(session, identifier)
    if user is None:
        return 0
    live = _live_codes(session, user.id)
    if not live:
        return 0
    now = _now()
    soonest = min(row.created_at + SEND_COOLDOWN for row in live)
    remaining = (soonest - now).total_seconds()
    return max(0, int(remaining))
