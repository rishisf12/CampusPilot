"""
Verify an email address *before* an account is created for it.

The previous order was wrong for a student: signup built the account and mailed a
code, so anyone who mistyped the code or closed the tab left a half-made account
that then blocked the real signup with "email already registered". Proving the
address first means nothing is created until it is known good.

The flow this supports:

    start(email)  -> mails a code, records the address as pending
    verify(...)   -> marks the address verified once the code is right
    is_verified() -> the gate the account-creation endpoint checks

One property is deliberate and worth stating: **nothing here reveals whether an
address is already registered.** That question is answered only later, by
``/auth/signup``, and only once the requester has proved they can receive mail at
the address. Learning who has an account is therefore gated behind actually owning
that mailbox, rather than being handed to anyone who can type an address.

The rules for the code itself - hashed at rest, single use, expiring, and dead
after a handful of wrong guesses - match the password-reset code exactly. Both
are six digits, which is a million possibilities; the attempt budget is the only
thing making that safe.
"""
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlmodel import Session, select

from models import PendingSignup

logger = logging.getLogger(__name__)

CODE_LENGTH = 6

#: Long enough to survive a slow inbox, short enough to keep the guessing window small.
CODE_TTL = timedelta(minutes=15)

#: Wrong guesses allowed before the code is destroyed. The single most important
#: number in this file: six digits alone is not a secret.
MAX_ATTEMPTS = 5

#: One code per address per window, so a known address cannot be used to flood
#: an inbox or to keep extending a guessing session.
SEND_COOLDOWN = timedelta(minutes=5)

#: Swept on the next write so the table cannot grow without bound.
RETENTION = timedelta(days=1)

#: Once the address is proven, this is how long the proof stays good. Long enough
#: to fill in a form, short enough that an abandoned verification does not reserve
#: the address indefinitely.
VERIFIED_TTL = timedelta(minutes=30)

#: Deliberately one sentence, returned whether or not a code was actually sent.
GENERIC_MESSAGE = (
    "If that address can receive mail, a verification code is on its way."
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupVerificationError(Exception):
    """The verification step failed. The message is safe to show the requester."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalise(email: str) -> str:
    return (email or "").strip().lower()


def _hash_code(email: str, code: str) -> str:
    """
    Hash the code, salted with the address.

    The salt is not secrecy - it stops one precomputed table cracking every code
    in the database at once. The attempt budget is what actually protects it.
    """
    return hashlib.sha256(f"{email}:{code}".encode("utf-8")).hexdigest()


def looks_like_email(email: str) -> bool:
    return bool(EMAIL_RE.match(normalise(email)))


def _purge(session: Session) -> None:
    cutoff = _now() - RETENTION
    for stale in session.exec(select(PendingSignup)).all():
        if stale.created_at is not None and stale.created_at < cutoff:
            session.delete(stale)


def find(session: Session, email: str) -> Optional[PendingSignup]:
    return session.exec(
        select(PendingSignup).where(PendingSignup.email == normalise(email))
    ).first()


def is_verified(session: Session, email: str) -> bool:
    """
    Has this address been proven, recently?

    This is the gate on creating an account. Time-limited: a proof from an hour
    ago is no longer good, because by then it is anyone's guess that the mailbox
    is still theirs.
    """
    row = find(session, email)
    if row is None or row.verified_at is None:
        return False
    return row.verified_at + VERIFIED_TTL > _now()


def start(session: Session, email: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Record the address as pending and return ``(code, retry_after_seconds)``.

    ``code`` is ``None`` when nothing was sent, which is not an error the caller
    should report - the response is the same either way, so the endpoint cannot be
    used to find out which addresses have accounts.

    ``retry_after_seconds`` is non-zero when the cooldown is still running, which
    the caller may pass to the client as a hint. It is a hint only: revealing it
    reveals that *something* happened for this address, so the frontend should
    prefer not to display it and merely rate-limit itself.
    """
    address = normalise(email)
    if not looks_like_email(address):
        raise SignupVerificationError("Enter a valid email address.")

    _purge(session)
    row = find(session, address)
    now = _now()

    if row is not None and row.created_at is not None:
        elapsed = now - row.created_at
        if elapsed < SEND_COOLDOWN:
            remaining = int((SEND_COOLDOWN - elapsed).total_seconds())
            return None, remaining

    code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"

    if row is None:
        row = PendingSignup(email=address, code_hash=_hash_code(address, code))
    else:
        # A fresh attempt resets everything: new code, new budget, not verified.
        row.code_hash = _hash_code(address, code)
        row.attempts = 0
        row.verified_at = None
        row.created_at = now

    session.add(row)
    session.commit()
    logger.info("Signup verification started for %s", address)
    return code, 0


def verify(session: Session, email: str, code: str) -> None:
    """
    Check the code and, if it matches, mark the address proven.

    A wrong code is counted against the *same* row rather than a new one, so an
    attacker cannot make guesses free by asking for another code first. Once the
    budget is spent the row is deleted outright: a code left on file with its
    budget gone would absorb guesses forever, which is no limit at all.
    """
    address = normalise(email)
    row = find(session, address)
    if row is None:
        raise SignupVerificationError("No verification code found. Request a new one.")

    now = _now()
    if row.created_at is None or row.created_at + CODE_TTL <= now:
        session.delete(row)
        session.commit()
        raise SignupVerificationError("That code has expired. Request a new one.")

    if row.attempts >= MAX_ATTEMPTS:
        session.delete(row)
        session.commit()
        raise SignupVerificationError(
            "Too many wrong attempts. Please request a new code."
        )

    wanted = _hash_code(address, (code or "").strip())
    if not secrets.compare_digest(row.code_hash, wanted):
        row.attempts += 1
        spent = row.attempts >= MAX_ATTEMPTS
        session.add(row)
        session.commit()
        if spent:
            session.delete(row)
            session.commit()
            raise SignupVerificationError(
                "Too many wrong attempts. Please request a new code."
            )
        raise SignupVerificationError("That code is not correct.")

    row.verified_at = now
    # The code is spent: proving the address once must not leave a replayable code.
    row.attempts = MAX_ATTEMPTS
    session.add(row)
    session.commit()
    logger.info("Signup email verified for %s", address)


def clear(session: Session, email: str) -> None:
    """Drop a pending signup, e.g. once the account finally exists."""
    row = find(session, email)
    if row is not None:
        session.delete(row)
        session.commit()


def seconds_until_retry(session: Session, email: str) -> int:
    """Whole seconds until another code may be requested for this address."""
    row = find(session, email)
    if row is None or row.created_at is None:
        return 0
    remaining = (row.created_at + SEND_COOLDOWN - _now()).total_seconds()
    return max(0, int(remaining))
