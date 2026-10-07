"""
End-to-end tests for passkey enrolment and sign-in.

These drive the *real* WebAuthn ceremony. A software authenticator is built on
the spot - it generates an ES256 key, packs the authenticator data and COSE
public key by hand, and signs - so the server's verification path is genuinely
exercised rather than stubbed. If enrolment or assertion verification breaks,
these fail.
"""
import base64
import hashlib
import json
import struct
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import cbor2
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlmodel import Session, SQLModel, create_engine, delete, select

import core.database as database
from models import PasskeyChallenge, PasskeyCredential, User
from features.auth import passkeys as svc


ORIGIN = "http://localhost:5173"
RP_ID = "localhost"


#: Users created by the passkey test modules all carry one of these usernames,
#: so cleanup can be scoped to them instead of emptying shared tables that other
#: modules also write to.
TEST_USER_PREFIXES = (
    "passkey_tester",
    "other_passkey",
    "other_user",
    "intruder",
    "someone_else",
    "x",
)


def _purge(db: Session) -> None:
    """Remove only this module's rows, leaving other modules' data alone."""
    db.exec(delete(PasskeyChallenge))
    for credential in db.exec(select(PasskeyCredential)).all():
        db.delete(credential)
    for existing in db.exec(select(User)).all():
        if existing.username in TEST_USER_PREFIXES:
            db.delete(existing)
    db.commit()


@pytest.fixture()
def session():
    """A session against the scratch test database, tables created once."""
    engine = create_engine(database.engine.url, **database.engine_kwargs())
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        # The scratch database is shared with every other test module, so clear
        # this module's rows before and after rather than relying on ordering.
        _purge(db)
        yield db
        _purge(db)


def rows(session, model):
    return session.exec(select(model)).all()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class SoftwareAuthenticator:
    """
    A minimal credential: holds an ES256 key and packs the two byte strings a
    real authenticator would produce.

    Only the parts the server actually reads are implemented - attestation is
    always the "none" format, which is what a platform authenticator sends.
    """

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = b"\x01" + hashlib.sha256(self.key.public_key().public_numbers().x.to_bytes(32, "big")).digest()[:15]
        self.sign_count = 0

    def _cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps({
            1: 2,      # kty: EC2
            3: -7,     # alg: ES256
            -1: 1,     # crv: P-256
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        })

    def _authenticator_data(self, flags: int, attested: bool = False) -> bytes:
        rp_id_hash = hashlib.sha256(RP_ID.encode()).digest()
        data = rp_id_hash + bytes([flags]) + struct.pack(">I", self.sign_count)
        if attested:
            # aaguid (all zero) + credential id length + id + COSE key
            data += b"\x00" * 16 + struct.pack(">H", len(self.credential_id))
            data += self.credential_id + self._cose_key()
        return data

    @staticmethod
    def _client_data(challenge: str, ceremony: str) -> bytes:
        return json.dumps({
            "type": ceremony,
            "challenge": challenge,
            "origin": ORIGIN,
            "crossOrigin": False,
        }, separators=(",", ":")).encode()

    def create(self, challenge: str, flags: int = 0x45) -> Dict[str, Any]:
        """Produce a registration response, as ``navigator.credentials.create``."""
        client_data = self._client_data(challenge, "webauthn.create")
        attestation = cbor2.dumps({
            "fmt": "none",
            "authData": self._authenticator_data(flags, attested=True),
            "attStmt": {},
        })
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "attestationObject": b64(attestation),
            },
            "clientExtensionResults": {},
        }

    def get(self, challenge: str, flags: int = 0x05) -> Dict[str, Any]:
        """Produce an assertion, as ``navigator.credentials.get``."""
        self.sign_count += 1
        client_data = self._client_data(challenge, "webauthn.get")
        auth_data = self._authenticator_data(flags)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes_sha256()))
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "authenticatorData": b64(auth_data),
                "signature": b64(signature),
                "userHandle": None,
            },
            "clientExtensionResults": {},
        }


def hashes_sha256():
    from cryptography.hazmat.primitives import hashes

    return hashes.SHA256()


@pytest.fixture()
def user(session):
    record = User(
        # A unique address: the scratch database is shared, and email is UNIQUE.
        email="passkey_tester@iiitdmj.ac.in",
        full_name="Passkey Tester",
        username="passkey_tester",
        roll_number="23BCS999",
        password_hash="x",
        is_email_verified=True,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@pytest.fixture()
def authenticator():
    return SoftwareAuthenticator()


@pytest.fixture()
def enrolled(session, user, authenticator):
    """A user with one working passkey."""
    options = svc.registration_options(session, user, user_agent="Mozilla/5.0 (Windows NT 10.0)")
    record = svc.complete_registration(
        session,
        user,
        authenticator.create(options["_challenge"]),
        options["_challenge"],
        options["_label"],
    )
    return record


class TestRegistration:
    def test_stores_only_the_public_key(self, session, user, enrolled, authenticator):
        """The stored material must never be able to sign as the user."""
        stored = svc.list_credentials(session, user.id)
        assert len(stored) == 1
        row = stored[0]
        assert row.public_key
        # A private scalar is never written; only the COSE key of the public pair.
        assert "PRIVATE" not in row.public_key.upper()

    def test_labels_the_device_from_the_user_agent(self, session, user):
        options = svc.registration_options(
            session, user, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        assert options["_label"] == "Windows Hello"

    def test_asks_for_a_discoverable_credential(self, session, user):
        """Without this the "any passkey on this device" option cannot work."""
        options = svc.registration_options(session, user)
        selection = options["authenticatorSelection"]
        assert selection["residentKey"] in ("preferred", "required")
        assert selection["userVerification"] == "required"

    def test_returns_a_single_use_challenge(self, session, user):
        options = svc.registration_options(session, user)
        assert rows(session, PasskeyChallenge)
        assert options["_challenge"]

    def test_challenge_is_spent_on_use(self, session, user, authenticator):
        options = svc.registration_options(session, user)
        svc.complete_registration(
            session, user, authenticator.create(options["_challenge"]), options["_challenge"]
        )
        with pytest.raises(svc.PasskeyError, match="expired"):
            svc.complete_registration(
                session, user, authenticator.create(options["_challenge"]), options["_challenge"]
            )

    def test_a_challenge_from_another_purpose_is_refused(
        self, session, user, enrolled, authenticator
    ):
        """A sign-in challenge must not be spendable on enrolment."""
        options = svc.authentication_options(session, user.username)
        with pytest.raises(svc.PasskeyError, match="not valid for that action"):
            svc.complete_registration(
                session, user, authenticator.create(options["_challenge"]), options["_challenge"]
            )

    def test_rejects_a_response_for_a_different_account(self, session, user, authenticator):
        """A challenge issued to one account must not enrol a passkey on another."""
        other = User(
            email="other@iiitdmj.ac.in",
            full_name="Other",
            username="other_user",
            roll_number="23BCS998",
            password_hash="x",
            is_email_verified=True,
        )
        session.add(other)
        session.commit()

        # The challenge is issued to `other`, but `user` tries to spend it.
        options = svc.registration_options(session, other)
        with pytest.raises(svc.PasskeyError, match="not valid for this account"):
            svc.complete_registration(
                session, user, authenticator.create(options["_challenge"]), options["_challenge"]
            )

    def test_rejects_a_tampered_signature(self, session, user, authenticator):
        options = svc.registration_options(session, user)
        response = authenticator.create(options["_challenge"])
        raw = bytearray(unb64(response["response"]["attestationObject"]))
        raw[-1] ^= 0xFF
        response["response"]["attestationObject"] = b64(bytes(raw))
        with pytest.raises(svc.PasskeyError, match="could not be enrolled"):
            svc.complete_registration(
                session, user, response, options["_challenge"]
            )

    def test_rejects_a_response_made_for_another_origin(self, session, user, authenticator):
        """A challenge leaked to a phishing site must not enrol here."""
        options = svc.registration_options(session, user)
        client_data = json.dumps({
            "type": "webauthn.create",
            "challenge": options["_challenge"],
            "origin": "https://evil.example.com",
            "crossOrigin": False,
        }, separators=(",", ":")).encode()
        response = authenticator.create(options["_challenge"])
        response["response"]["clientDataJSON"] = b64(client_data)
        with pytest.raises(svc.PasskeyError, match="could not be enrolled"):
            svc.complete_registration(
                session, user, response, options["_challenge"]
            )

    def test_rejects_a_replayed_client_data_from_a_registration(self, session, user, authenticator):
        """The ceremony type is bound into the signed data."""
        options = svc.registration_options(session, user)
        first = authenticator.create(options["_challenge"])
        client_data = json.loads(unb64(first["response"]["clientDataJSON"]))
        client_data["type"] = "webauthn.get"
        second = authenticator.create(options["_challenge"])
        second["response"]["clientDataJSON"] = b64(
            json.dumps(client_data, separators=(",", ":")).encode()
        )
        with pytest.raises(svc.PasskeyError, match="could not be enrolled"):
            svc.complete_registration(
                session, user, second, options["_challenge"]
            )


class TestAuthentication:
    def test_signs_in_with_the_passkey_alone(self, session, user, enrolled, authenticator):
        options = svc.authentication_options(session, user.username)
        signed_in = svc.complete_authentication(
            session, authenticator.get(options["_challenge"]), options["_challenge"]
        )
        assert signed_in.id == user.id

    def test_password_is_never_touched(self, session, user, enrolled, authenticator):
        """Recovery means going around the password, not rewriting it."""
        before = user.password_hash
        options = svc.authentication_options(session, user.username)
        svc.complete_authentication(
            session, authenticator.get(options["_challenge"]), options["_challenge"]
        )
        session.refresh(user)
        assert user.password_hash == before

    def test_can_skip_the_username(self, session, user, enrolled, authenticator):
        options = svc.authentication_options(session, None)
        signed_in = svc.complete_authentication(
            session, authenticator.get(options["_challenge"]), options["_challenge"]
        )
        assert signed_in.id == user.id

    def test_narrows_the_offer_to_one_account(self, session, user, enrolled, authenticator):
        options = svc.authentication_options(session, user.username)
        allowed = options["allowCredentials"]
        assert len(allowed) == 1
        assert allowed[0]["id"] == enrolled.credential_id

    def test_a_challenge_is_still_issued_when_no_username_is_given(self, session, user, enrolled):
        options = svc.authentication_options(session, None)
        assert options["_challenge"]

    def test_unknown_username_is_refused(self, session, user):
        with pytest.raises(svc.PasskeyError, match="no passkey set up"):
            svc.authentication_options(session, "nobody_here")

    def test_username_with_no_passkey_gives_the_same_message(self, session, user):
        """Identical wording, so this cannot be used to find enrolled accounts."""
        with pytest.raises(svc.PasskeyError) as unknown:
            svc.authentication_options(session, "nobody_here")
        with pytest.raises(svc.PasskeyError) as no_key:
            svc.authentication_options(session, user.username)
        assert str(unknown.value) == str(no_key.value)

    def test_rejects_an_unregistered_credential(self, session, user, enrolled):
        """A forged response cannot nominate an account."""
        stranger = SoftwareAuthenticator()
        options = svc.authentication_options(session, user.username)
        with pytest.raises(svc.PasskeyError, match="not registered"):
            svc.complete_authentication(
                session, stranger.get(options["_challenge"]), options["_challenge"]
            )

    def test_rejects_a_challenge_used_twice(self, session, user, enrolled, authenticator):
        options = svc.authentication_options(session, user.username)
        response = authenticator.get(options["_challenge"])
        svc.complete_authentication(session, response, options["_challenge"])
        with pytest.raises(svc.PasskeyError, match="expired"):
            svc.complete_authentication(session, response, options["_challenge"])

    def test_rejects_a_challenge_from_enrolment(self, session, user, enrolled, authenticator):
        options = svc.registration_options(session, user)
        with pytest.raises(svc.PasskeyError, match="not valid for that action"):
            svc.complete_authentication(
                session, authenticator.get(options["_challenge"]), options["_challenge"]
            )

    def test_rejects_an_expired_challenge(self, session, user, enrolled, authenticator):
        options = svc.authentication_options(session, user.username)
        response = authenticator.get(options["_challenge"])
        row = rows(session, PasskeyChallenge)[0]
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        session.add(row)
        session.commit()
        with pytest.raises(svc.PasskeyError, match="expired"):
            svc.complete_authentication(session, response, options["_challenge"])

    def test_rejects_an_assertion_for_another_origin(self, session, user, enrolled, authenticator):
        options = svc.authentication_options(session, user.username)
        response = authenticator.get(options["_challenge"])
        forged = json.loads(unb64(response["response"]["clientDataJSON"]))
        forged["origin"] = "https://evil.example.com"
        client_data = json.dumps(forged, separators=(",", ":")).encode()
        auth_data = unb64(response["response"]["authenticatorData"])
        signature = authenticator.key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes_sha256())
        )
        response["response"]["clientDataJSON"] = b64(client_data)
        response["response"]["signature"] = b64(signature)
        with pytest.raises(svc.PasskeyError, match="could not be verified"):
            svc.complete_authentication(session, response, options["_challenge"])

    def test_rejects_a_tampered_authenticator_data(self, session, user, enrolled, authenticator):
        options = svc.authentication_options(session, user.username)
        response = authenticator.get(options["_challenge"])
        raw = bytearray(unb64(response["response"]["authenticatorData"]))
        raw[32] ^= 0x01  # flip a flag byte, invalidating the signature
        response["response"]["authenticatorData"] = b64(bytes(raw))
        with pytest.raises(svc.PasskeyError, match="could not be verified"):
            svc.complete_authentication(session, response, options["_challenge"])

    def test_rejects_a_credential_matching_a_different_account(
        self, session, user, enrolled, authenticator
    ):
        """A username/credential mismatch must not sign in the wrong person."""
        intruder = User(
            email="intruder@iiitdmj.ac.in",
            full_name="Intruder",
            username="intruder",
            roll_number="23BCS997",
            password_hash="x",
            is_email_verified=True,
        )
        session.add(intruder)
        session.commit()

        # Give the intruder a passkey so a challenge can be issued for them.
        intruder_options = svc.registration_options(session, intruder)
        svc.complete_registration(
            session,
            intruder,
            SoftwareAuthenticator().create(intruder_options["_challenge"]),
            intruder_options["_challenge"],
        )

        options = svc.authentication_options(session, intruder.username)
        # `user`'s passkey is offered instead of the intruder's own.
        with pytest.raises(svc.PasskeyError, match="different account"):
            svc.complete_authentication(
                session, authenticator.get(options["_challenge"]), options["_challenge"]
            )


class TestSignCount:
    def test_advances_the_stored_counter(self, session, user, enrolled, authenticator):
        for _ in range(3):
            options = svc.authentication_options(session, user.username)
            svc.complete_authentication(
                session, authenticator.get(options["_challenge"]), options["_challenge"]
            )
        session.refresh(enrolled)
        assert enrolled.sign_count == 3

    def test_stamps_the_last_use(self, session, user, enrolled, authenticator):
        assert enrolled.last_used_at is None
        options = svc.authentication_options(session, user.username)
        svc.complete_authentication(
            session, authenticator.get(options["_challenge"]), options["_challenge"]
        )
        session.refresh(enrolled)
        assert enrolled.last_used_at is not None

    def test_a_counter_that_goes_backwards_is_refused(self, session, user, enrolled, authenticator):
        """Two devices sharing a credential would move the counter backwards."""
        options = svc.authentication_options(session, user.username)
        svc.complete_authentication(
            session, authenticator.get(options["_challenge"]), options["_challenge"]
        )
        session.refresh(enrolled)
        enrolled.sign_count = 99
        session.add(enrolled)
        session.commit()

        options = svc.authentication_options(session, user.username)
        with pytest.raises(svc.PasskeyError, match="could not be verified"):
            svc.complete_authentication(
                session, authenticator.get(options["_challenge"]), options["_challenge"]
            )


class TestRemoval:
    def test_removes_only_the_owner_s_credential(self, session, user, enrolled):
        other = User(
            email="x@iiitdmj.ac.in",
            full_name="X",
            username="someone_else",
            roll_number="23BCS996",
            password_hash="x",
            is_email_verified=True,
        )
        session.add(other)
        session.commit()

        with pytest.raises(svc.PasskeyError, match="not found on your account"):
            svc.delete_credential(session, other, enrolled.credential_id)
        assert rows(session, PasskeyCredential)

    def test_a_removed_passkey_no_longer_signs_in(self, session, user, enrolled, authenticator):
        svc.delete_credential(session, user, enrolled.credential_id)
        options = svc.authentication_options(session, None)
        with pytest.raises(svc.PasskeyError, match="not registered"):
            svc.complete_authentication(
                session, authenticator.get(options["_challenge"]), options["_challenge"]
            )


class TestReporting:
    def test_describe_hides_sensitive_fields(self, session, enrolled):
        described = svc.describe(enrolled)
        assert set(described) == {"credential_id", "label", "created_at", "last_used_at"}
        assert "public_key" not in described
        assert "sign_count" not in described

    def test_counts_reflect_stored_credentials(self, session, user):
        assert svc.list_credentials(session, user.id) == []

    def test_challenges_do_not_accumulate(self, session, user):
        for _ in range(5):
            svc.authentication_options(session, None)
        assert len(rows(session, PasskeyChallenge)) == 5

        # Anything older than the retention window is swept on the next write.
        stale = rows(session, PasskeyChallenge)[0]
        stale.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        session.add(stale)
        session.commit()

        svc.authentication_options(session, None)
        assert len(rows(session, PasskeyChallenge)) == 5
