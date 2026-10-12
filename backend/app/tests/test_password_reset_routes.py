"""
Route-level tests for password reset.

The service tests cover the rules; these cover what a client and an attacker
actually see over HTTP - in particular that the endpoint cannot be used to find
out who has an account, and that a reset really does end the sessions it should.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.database as database
from main import app
from models import PasswordResetCode, PasskeyCredential, User
from features.auth.routes import create_access_token, hash_password, verify_password
from features.auth import passkeys as passkey_service, password_reset as svc

USERNAME = "reset_tester"
EMAIL = "reset_tester@iiitdmj.ac.in"
PASSWORD = "Original@123"
NEW_PASSWORD = "Brand@New456"


def _purge(db: Session) -> None:
    db.exec(delete(PasswordResetCode))
    for credential in db.exec(select(PasskeyCredential)).all():
        db.delete(credential)
    for user in db.exec(select(User)).all():
        if user.username in ("reset_tester", "reset_other"):
            db.delete(user)
    db.commit()


@pytest.fixture()
def db():
    engine = create_engine(database.engine.url, **database.engine_kwargs())
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _purge(session)
        yield session
        _purge(session)


@pytest.fixture()
def client(db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def account(db):
    db.add(
        User(
            email=EMAIL,
            full_name="Reset Tester",
            username=USERNAME,
            roll_number="23BCS995",
            password_hash=hash_password(PASSWORD),
            is_email_verified=True,
        )
    )
    db.commit()
    return db.exec(select(User).where(User.username == USERNAME)).first()


def request_code(db, identifier=USERNAME):
    """Issue a code and return its value, bypassing the email."""
    return svc.request_code(db, identifier)


class TestForgotPassword:
    def test_always_says_the_same_thing_for_a_known_account(self, client, account):
        response = client.post("/auth/forgot-password", json={"identifier": USERNAME})
        assert response.status_code == 200
        assert "registered email address" in response.json()["message"]

    def test_says_the_thing_identical_for_an_unknown_account(self, client, account):
        """The whole point: this must not enumerate students."""
        known = client.post("/auth/forgot-password", json={"identifier": USERNAME})
        unknown = client.post("/auth/forgot-password", json={"identifier": "nobody_here"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    def test_accepts_the_registered_email(self, client, account):
        response = client.post("/auth/forgot-password", json={"identifier": EMAIL})
        assert response.status_code == 200

    def test_a_blank_identifier_is_still_a_200(self, client, account):
        """A 422 here would again distinguish nothing, but stay consistent."""
        response = client.post("/auth/forgot-password", json={"identifier": "  "})
        assert response.status_code == 200

    def test_smtp_failure_does_not_leak_that_the_account_exists(self, client, account):
        """No SMTP configured here, so every send fails - and still says the same."""
        response = client.post("/auth/forgot-password", json={"identifier": USERNAME})
        unknown = client.post("/auth/forgot-password", json={"identifier": "nobody_here"})
        assert response.json() == unknown.json()

    def test_works_without_a_session(self, client, account):
        assert "access_token" not in client.post(
            "/auth/forgot-password", json={"identifier": USERNAME}
        ).json()


class TestResetPassword:
    def test_sets_the_new_password(self, client, db, account):
        code = request_code(db)
        response = client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 200
        db.refresh(account)
        assert verify_password(NEW_PASSWORD, account.password_hash)

    def test_the_old_password_stops_working(self, client, db, account):
        code = request_code(db)
        client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )
        assert (
            client.post(
                "/auth/login", data={"username": USERNAME, "password": PASSWORD}
            ).status_code
            == 401
        )

    def test_the_new_password_signs_in(self, client, db, account):
        code = request_code(db)
        client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )
        assert (
            client.post(
                "/auth/login", data={"username": USERNAME, "password": NEW_PASSWORD}
            ).status_code
            == 200
        )

    def test_a_wrong_code_is_a_400(self, client, db, account):
        request_code(db)
        wrong = "000000"
        response = client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": wrong, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400
        db.refresh(account)
        assert verify_password(PASSWORD, account.password_hash)

    def test_an_unknown_account_is_a_400_not_a_404(self, client, account):
        """A 404 would confirm no such account exists."""
        response = client.post(
            "/auth/reset-password",
            json={"identifier": "nobody_here", "code": "123456", "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400
        assert "not valid" in response.json()["detail"]

    def test_a_short_password_is_rejected_before_anything_happens(self, client, db, account):
        code = request_code(db)
        response = client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": "short"},
        )
        assert response.status_code == 422
        db.refresh(account)
        assert verify_password(PASSWORD, account.password_hash)

    def test_the_response_says_the_passkeys_went_too(self, client, db, account):
        options = passkey_service.registration_options(db, account)
        from test_passkeys import SoftwareAuthenticator

        passkey_service.complete_registration(
            db, account, SoftwareAuthenticator().create(options["_challenge"]), options["_challenge"]
        )
        code = request_code(db)
        response = client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )
        assert response.json()["passkeys_revoked"] == 1

    def test_a_code_cannot_be_replayed(self, client, db, account):
        code = request_code(db)
        client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )
        second = client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": "Third@7890"},
        )
        assert second.status_code == 400
        db.refresh(account)
        assert verify_password(NEW_PASSWORD, account.password_hash)


class TestSessionsEndWithThePassword:
    def test_an_existing_token_is_refused_after_a_reset(self, client, db, account):
        """The reason the password stamp exists."""
        stale = create_access_token(account.id, USERNAME, account.password_changed_at)
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {stale}"}).status_code == 200

        code = request_code(db)
        client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )

        after = client.get("/auth/me", headers={"Authorization": f"Bearer {stale}"})
        assert after.status_code == 401
        assert "sign in again" in after.json()["detail"].lower()

    def test_a_token_issued_after_the_reset_still_works(self, client, db, account):
        code = request_code(db)
        client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )
        db.refresh(account)

        fresh = create_access_token(account.id, USERNAME, account.password_changed_at)
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200

    def test_a_revoked_passkey_cannot_sign_in_afterwards(self, client, db, account):
        from test_passkeys import SoftwareAuthenticator

        authenticator = SoftwareAuthenticator()
        options = passkey_service.registration_options(db, account)
        passkey_service.complete_registration(
            db, account, authenticator.create(options["_challenge"]), options["_challenge"]
        )

        # The passkey works before the reset...
        before = client.post(
            "/auth/passkeys/login/options", json={"username": USERNAME}
        ).json()
        assert (
            client.post(
                "/auth/passkeys/login",
                json={
                    "credential": authenticator.get(before["_challenge"]),
                    "challenge": before["_challenge"],
                },
            ).status_code
            == 200
        )

        code = request_code(db)
        client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )

        # ...and cannot afterwards, even holding a valid challenge.
        after = client.post("/auth/passkeys/login/options", json={}).json()
        assert (
            client.post(
                "/auth/passkeys/login",
                json={
                    "credential": authenticator.get(after["_challenge"]),
                    "challenge": after["_challenge"],
                },
            ).status_code
            == 401
        )

    def test_an_unrelated_account_is_untouched(self, client, db, account):
        other = User(
            email="reset_other@iiitdmj.ac.in",
            full_name="Other",
            username="reset_other",
            roll_number="23BCS994",
            password_hash=hash_password("Other@12345"),
            is_email_verified=True,
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        other_token = create_access_token(other.id, "reset_other", other.password_changed_at)

        code = request_code(db)
        client.post(
            "/auth/reset-password",
            json={"identifier": USERNAME, "code": code, "new_password": NEW_PASSWORD},
        )

        assert client.get("/auth/me", headers={"Authorization": f"Bearer {other_token}"}).status_code == 200
        db.refresh(other)
        assert verify_password("Other@12345", other.password_hash)
