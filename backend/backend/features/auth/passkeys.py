"""
Passkey (WebAuthn) enrolment and sign-in.

A passkey replaces the password for signing in: the device holds the private key,
the server keeps only the public half, so a forgotten password never has to be
reset to get back in. Nothing here can turn a stored credential into a way to
impersonate someone - only the device can produce a valid assertion.

The credential flow is the standard WebAuthn ceremony in four steps:

1. the server issues a **challenge** and describes what it will accept
2. the browser asks the authenticator to sign that challenge
3. the browser posts the authenticator's answer back
4. the server verifies the signature against the stored public key

Challenges are single-use. Each one is deleted the moment it is spent, so a
replayed response is rejected even if it arrives within the timeout.
"""
import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from core.config import settings
from models import PasskeyChallenge, PasskeyCredential, User

logger = logging.getLogger(__name__)

#: A challenge is only good for five minutes; the spec's own default is 60s.
CHALLENGE_TTL = timedelta(minutes=5)

#: Challenges older than this are swept on the next write so the table cannot
#: grow without bound.
CHALLENGE_RETENTION = timedelta(hours=1)

#: Verification policy. Requiring user presence stops a silent sign-in, and
#: asking for verification accepts a PIN or biometric check, which is what makes
#: a passkey meaningfully stronger than the password it replaces.
REQUIRE_USER_PRESENCE = True
REQUIRE_USER_VERIFICATION = True


class PasskeyError(Exception):
    """A passkey request could not be completed. The message is user-safe."""


def _b64url(data: bytes) -> str:
    """Base64url without padding, the encoding WebAuthn uses everywhere."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64url(text: str) -> bytes:
    """Decode base64url text back to bytes, restoring any stripped padding."""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _transport_enum(values: List[str]) -> Optional[List[Any]]:
    """
    Stored transport hints as the enum the library expects.

    A hint the browser no longer recognises is dropped rather than raising: the
    transport is only an optimisation, and an unrecognised one must not stop a
    passkey from working.
    """
    from webauthn.helpers.structs import AuthenticatorTransport

    known = []
    for value in values or []:
        try:
            known.append(AuthenticatorTransport(value))
        except ValueError:
            logger.debug("Ignoring unknown authenticator transport %r", value)
    return known or None


def _origin_list() -> List[str]:
    return settings.passkey_origins or [settings.FRONTEND_URL]


def _describe_device(user_agent: Optional[str]) -> str:
    """A short, human name for the passkey so a student can tell them apart."""
    agent = (user_agent or "").lower()
    if "windows" in agent:
        return "Windows Hello"
    if "iphone" in agent or "ipad" in agent or "macintosh" in agent:
        return "Apple device"
    if "android" in agent:
        return "Android device"
    if "chrome" in agent:
        return "Chrome"
    if "safari" in agent:
        return "Safari"
    if "firefox" in agent:
        return "Firefox"
    return "This device"


def _purge_old_challenges(session: Session) -> None:
    cutoff = datetime.now(timezone.utc) - CHALLENGE_RETENTION
    for stale in session.exec(select(PasskeyChallenge)).all():
        created = stale.created_at
        if created is None:
            continue
        # created_at is naive UTC in SQLite, so compare naively.
        if created.replace(tzinfo=timezone.utc) < cutoff:
            session.delete(stale)


def _store_challenge(
    session: Session, challenge: str, purpose: str, user_id: Optional[int]
) -> None:
    _purge_old_challenges(session)
    session.add(
        PasskeyChallenge(
            challenge=challenge, purpose=purpose, user_id=user_id
        )
    )
    session.commit()


def _take_challenge(
    session: Session, challenge: str, purpose: str
) -> Optional[PasskeyChallenge]:
    """
    Consume a challenge, returning it only if it exists and is still fresh.

    Deleting before verification means a challenge cannot be spent twice even if
    verification then fails - a wrong signature must not leave a live challenge
    behind for an attacker to retry.
    """
    row = session.exec(
        select(PasskeyChallenge).where(PasskeyChallenge.challenge == challenge)
    ).first()
    if row is None:
        raise PasskeyError("This sign-in request has expired. Please start again.")

    session.delete(row)
    session.commit()

    created = row.created_at
    if created is not None and created.replace(tzinfo=timezone.utc) < (
        datetime.now(timezone.utc) - CHALLENGE_TTL
    ):
        raise PasskeyError("This sign-in request has expired. Please start again.")

    if row.purpose != purpose:
        raise PasskeyError("This sign-in request is not valid for that action.")

    return row


def list_credentials(session: Session, user_id: int) -> List[PasskeyCredential]:
    return list(
        session.exec(
            select(PasskeyCredential).where(PasskeyCredential.user_id == user_id)
        ).all()
    )


def registration_options(
    session: Session,
    user: User,
    user_agent: Optional[str] = None,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Step 1 of enrolment: a fresh challenge plus what the device may choose.

    ``residentKey`` is requested so the credential is discoverable - that is what
    lets a student later sign in with "any passkey on this device" without
    typing a username first.
    """
    from webauthn import generate_registration_options
    from webauthn.helpers import options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialType,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    existing = list_credentials(session, user.id)
    options = generate_registration_options(
        rp_id=settings.PASSKEY_RP_ID,
        rp_name=settings.PASSKEY_RP_NAME,
        user_name=user.username,
        user_display_name=user.email or user.username,
        user_id=str(user.id).encode("utf-8"),
        # Already-enrolled credentials are excluded so the device will not
        # silently create a duplicate for the same authenticator.
        exclude_credentials=[
            PublicKeyCredentialDescriptor(
                id=_unb64url(item.credential_id),
                type=PublicKeyCredentialType.PUBLIC_KEY,
                transports=_transport_enum(item.transports),
            )
            for item in existing
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )

    challenge = _b64url(options.challenge)
    _store_challenge(session, challenge, "register", user.id)

    payload = json.loads(options_to_json(options))
    payload["_challenge"] = challenge
    payload["_label"] = (label or _describe_device(user_agent)).strip()[:60]
    return payload


def complete_registration(
    session: Session,
    user: User,
    credential: Dict[str, Any],
    challenge: str,
    label: Optional[str] = None,
) -> PasskeyCredential:
    """
    Step 3 of enrolment: verify the attestation and store the public key.

    The stored key is the only thing kept. Losing the device loses the passkey,
    which is why enrolment is only ever offered to a user who has just proved
    they know their password.
    """
    from webauthn import verify_registration_response

    stored_challenge = _take_challenge(session, challenge, "register")
    if stored_challenge.user_id not in (None, user.id):
        raise PasskeyError("This sign-up request is not valid for this account.")

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=_unb64url(challenge),
            expected_rp_id=settings.PASSKEY_RP_ID,
            expected_origin=_origin_list(),
            require_user_presence=REQUIRE_USER_PRESENCE,
            require_user_verification=REQUIRE_USER_VERIFICATION,
        )
    except PasskeyError:
        raise
        # range of error types for a failed ceremony; every one of them
        # is the same user-facing outcome, so they collapse to PasskeyError.
    except Exception as exc:
        logger.info("Passkey enrolment rejected: %s", exc)
        raise PasskeyError("This device could not be enrolled. Please try again.") from exc

    record = PasskeyCredential(
        user_id=user.id,
        credential_id=_b64url(verification.credential_id),
        public_key=_b64url(verification.credential_public_key),
        sign_count=verification.sign_count,
        transports=[
            # Stored as plain strings: this row outlives the library's enum.
            str(getattr(transport, "value", transport))
            for transport in (verification.credential_device_type or [])
        ],
        label=(label or _describe_device(None)).strip()[:60] or "This device",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    logger.info("Passkey enrolled for user %s (%s)", user.id, record.label)
    return record


def authentication_options(
    session: Session, username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Step 1 of sign-in: a challenge, optionally narrowed to one account.

    With a username the device is offered only that user's passkeys, which is
    predictable. With no username the credential list is left empty, and the
    authenticator offers whatever discoverable passkeys it holds.
    """
    from webauthn import generate_authentication_options
    from webauthn.helpers import options_to_json
    from webauthn.helpers.structs import (
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialType,
        UserVerificationRequirement,
    )

    allow: List[Any] = []
    user: Optional[User] = None

    if username:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            # The same message either way, so this cannot be used to discover
            # which usernames exist.
            raise PasskeyError("That username has no passkey set up on this device.")
        allow = [
            PublicKeyCredentialDescriptor(
                id=_unb64url(item.credential_id),
                # Only public-key credentials are ever stored, so the type is
                # fixed rather than read from the row.
                type=PublicKeyCredentialType.PUBLIC_KEY,
                transports=_transport_enum(item.transports),
            )
            for item in list_credentials(session, user.id)
        ]
        if not allow:
            raise PasskeyError("That username has no passkey set up on this device.")

    options = generate_authentication_options(
        rp_id=settings.PASSKEY_RP_ID,
        allow_credentials=allow or None,
        user_verification=(
            UserVerificationRequirement.REQUIRED
            if REQUIRE_USER_VERIFICATION
            else UserVerificationRequirement.PREFERRED
        ),
    )

    challenge = _b64url(options.challenge)
    _store_challenge(session, challenge, "authenticate", user.id if user else None)

    payload = json.loads(options_to_json(options))
    payload["_challenge"] = challenge
    return payload


def complete_authentication(
    session: Session, credential: Dict[str, Any], challenge: str
) -> User:
    """
    Step 3 of sign-in: verify the assertion and return the owning user.

    The user is looked up from the credential, not from anything the client
    sends, so a forged response can only ever fail - it cannot nominate a
    different account.
    """
    from webauthn import verify_authentication_response

    stored_challenge = _take_challenge(session, challenge, "authenticate")

    credential_id = credential.get("id") or credential.get("rawId")
    if not credential_id:
        raise PasskeyError("This device did not return a passkey.")

    record = session.exec(
        select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
    ).first()
    if record is None:
        raise PasskeyError("That passkey is not registered. Please sign in with your password.")

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=_unb64url(challenge),
            expected_rp_id=settings.PASSKEY_RP_ID,
            expected_origin=_origin_list(),
            credential_public_key=_unb64url(record.public_key),
            credential_current_sign_count=record.sign_count,
            require_user_verification=REQUIRE_USER_VERIFICATION,
        )
    except PasskeyError:
        raise
        # the specific webauthn exception is not actionable to the caller.
    except Exception as exc:
        logger.info("Passkey sign-in rejected: %s", exc)
        raise PasskeyError("That passkey could not be verified. Please try again.") from exc

    # A counter that goes backwards means two devices share a credential, which
    # should not happen and is worth refusing.
    if record.sign_count and verification.new_sign_count <= record.sign_count:
        raise PasskeyError("This passkey could not be verified. Please sign in with your password.")

    record.sign_count = verification.new_sign_count
    record.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(record)

    user = session.get(User, record.user_id)
    if user is None:
        raise PasskeyError("That passkey is not linked to an account.")

    # The account the challenge was issued for must match the credential's owner,
    # or a username/credential mismatch would silently sign in the wrong person.
    if stored_challenge.user_id not in (None, user.id):
        raise PasskeyError("That passkey belongs to a different account.")

    session.commit()
    logger.info("Passkey sign-in for user %s", user.id)
    return user


def delete_credential(session: Session, user: User, credential_id: str) -> None:
    """Remove one passkey. Scoped to the user so ids cannot be probed."""
    record = session.exec(
        select(PasskeyCredential).where(
            PasskeyCredential.credential_id == credential_id,
            PasskeyCredential.user_id == user.id,
        )
    ).first()
    if record is None:
        raise PasskeyError("That passkey was not found on your account.")
    session.delete(record)
    session.commit()


def describe(record: PasskeyCredential) -> Dict[str, Any]:
    """A credential as the client sees it - never the public key or counter."""
    return {
        "credential_id": record.credential_id,
        "label": record.label or "This device",
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
    }
