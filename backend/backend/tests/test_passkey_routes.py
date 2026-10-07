"""
Route-level tests for the passkey endpoints.

`test_passkeys.py` covers the ceremony itself; this checks the HTTP surface -
status codes, auth requirements, and what is and is not disclosed. Those are the
parts a client depends on and the parts a service-level test cannot see.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine, delete, select  # noqa: E402

import core.database as database  # noqa: E402
from main import app  # noqa: E402
from models import PasskeyCredential, User  # noqa: E402
from features.auth.routes import create_access_token, hash_password  # noqa: E402
from test_passkeys import SoftwareAuthenticator, _purge  # noqa: E402


@pytest.fixture()
def client():
    engine = create_engine(database.engine.url, **database.engine_kwargs())
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as test_client:
        _purge(Session(engine))
        yield test_client
        _purge(Session(engine))


@pytest.fixture()
def account(client):
    """
    A verified account with a valid password, plus its bearer header.

    Written straight to the database rather than through `/auth/signup`, because
    signup sends a verification email and no test should touch SMTP.
    """
    with Session(database.engine) as db:
        db.add(
            User(
                email="passkey_tester@iiitdmj.ac.in",
                full_name="Pass Key",
                username="passkey_tester",
                roll_number="23BCS999",
                password_hash=hash_password("Test@12345"),
                is_email_verified=True,
            )
        )
        db.commit()

    token = client.post(
        "/auth/login", data={"username": "passkey_tester", "password": "Test@12345"}
    ).json()["access_token"]
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}}


def enrol(client, headers, authenticator=None):
    """Run a real enrolment through the routes; returns the stored description."""
    authenticator = authenticator or SoftwareAuthenticator()
    options = client.post("/auth/passkeys/register/options", headers=headers).json()
    response = client.post(
        "/auth/passkeys/register",
        headers=headers,
        json={
            "credential": authenticator.create(options["_challenge"]),
            "challenge": options["_challenge"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["passkey"], authenticator


class TestListing:
    def test_empty_for_a_fresh_account(self, client, account):
        body = client.get("/auth/passkeys", headers=account["headers"]).json()
        assert body == {"has_passkey": False, "count": 0, "passkeys": []}

    def test_reports_a_passkey_once_added(self, client, account):
        enrol(client, account["headers"])
        body = client.get("/auth/passkeys", headers=account["headers"]).json()
        assert body["has_passkey"] is True
        assert body["count"] == 1

    def test_requires_a_session(self, client):
        assert client.get("/auth/passkeys").status_code == 401


class TestEnrolmentRoutes:
    def test_needs_a_session(self, client):
        """Enrolling is handing the account a passwordless route."""
        assert client.post("/auth/passkeys/register/options", json={}).status_code == 401

    def test_rejects_a_bad_token(self, client):
        response = client.post(
            "/auth/passkeys/register/options",
            headers={"Authorization": "Bearer not-a-real-token"},
            json={},
        )
        assert response.status_code == 401

    def test_returns_options_the_browser_can_use(self, client, account):
        body = client.post("/auth/passkeys/register/options", headers=account["headers"]).json()
        assert body["rp"]["id"] == "localhost"
        assert body["_challenge"]
        assert body["user"]["name"] == "passkey_tester"
        # Discoverable, or "any passkey on this device" could not work.
        assert body["authenticatorSelection"]["residentKey"] in ("preferred", "required")

    def test_a_challenge_is_issued_per_request(self, client, account):
        first = client.post("/auth/passkeys/register/options", headers=account["headers"]).json()
        second = client.post("/auth/passkeys/register/options", headers=account["headers"]).json()
        assert first["_challenge"] != second["_challenge"]

    def test_a_spent_challenge_cannot_be_reused(self, client, account):
        authenticator = SoftwareAuthenticator()
        options = client.post("/auth/passkeys/register/options", headers=account["headers"]).json()
        credential = authenticator.create(options["_challenge"])
        body = {"credential": credential, "challenge": options["_challenge"]}

        assert client.post("/auth/passkeys/register", headers=account["headers"], json=body).status_code == 200
        second = client.post("/auth/passkeys/register", headers=account["headers"], json=body)
        assert second.status_code == 400
        assert "expired" in second.json()["detail"].lower()

    def test_a_garbage_credential_is_rejected(self, client, account):
        options = client.post("/auth/passkeys/register/options", headers=account["headers"]).json()
        response = client.post(
            "/auth/passkeys/register",
            headers=account["headers"],
            json={"credential": {"id": "nonsense"}, "challenge": options["_challenge"]},
        )
        assert response.status_code == 400


class TestSignInRoutes:
    def test_needs_no_session(self, client, account):
        """The whole point: no password and no token, just the device."""
        _, authenticator = enrol(client, account["headers"])
        options = client.post(
            "/auth/passkeys/login/options", json={"username": "passkey_tester"}
        ).json()

        response = client.post(
            "/auth/passkeys/login",
            json={
                "credential": authenticator.get(options["_challenge"]),
                "challenge": options["_challenge"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["access_token"]

    def test_the_issued_token_opens_the_api(self, client, account):
        _, authenticator = enrol(client, account["headers"])
        options = client.post(
            "/auth/passkeys/login/options", json={"username": "passkey_tester"}
        ).json()
        signed_in = client.post(
            "/auth/passkeys/login",
            json={
                "credential": authenticator.get(options["_challenge"]),
                "challenge": options["_challenge"],
            },
        ).json()

        me = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {signed_in['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["username"] == "passkey_tester"

    def test_the_password_is_not_needed_or_changed(self, client, account):
        _, authenticator = enrol(client, account["headers"])
        options = client.post(
            "/auth/passkeys/login/options", json={"username": "passkey_tester"}
        ).json()

        # No password is sent anywhere in this exchange.
        client.post(
            "/auth/passkeys/login",
            json={
                "credential": authenticator.get(options["_challenge"]),
                "challenge": options["_challenge"],
            },
        )
        # The account's password still works, untouched.
        assert client.post(
            "/auth/login", data={"username": "passkey_tester", "password": "Test@12345"}
        ).status_code == 200

    def test_can_skip_the_username(self, client, account):
        _, authenticator = enrol(client, account["headers"])
        options = client.post("/auth/passkeys/login/options", json={}).json()
        response = client.post(
            "/auth/passkeys/login",
            json={
                "credential": authenticator.get(options["_challenge"]),
                "challenge": options["_challenge"],
            },
        )
        assert response.status_code == 200

    def test_unknown_username_is_a_404(self, client, account):
        response = client.post("/auth/passkeys/login/options", json={"username": "nobody_here"})
        assert response.status_code == 404

    def test_known_username_with_no_passkey_is_a_404_too(self, client, account):
        """Identical status and wording, so accounts cannot be enumerated."""
        unknown = client.post("/auth/passkeys/login/options", json={"username": "nobody_here"})
        no_key = client.post(
            "/auth/passkeys/login/options", json={"username": "passkey_tester"}
        )
        assert unknown.status_code == no_key.status_code == 404
        assert unknown.json()["detail"] == no_key.json()["detail"]

    def test_sign_in_response_is_a_plain_401_when_it_fails(self, client, account):
        """The account must exist for a challenge to be issued at all."""
        enrol(client, account["headers"])
        options = client.post(
            "/auth/passkeys/login/options", json={"username": "passkey_tester"}
        ).json()
        # A credential id that was never registered on this account.
        response = client.post(
            "/auth/passkeys/login",
            json={"credential": {"id": "unknown"}, "challenge": options["_challenge"]},
        )
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_a_body_without_a_challenge_is_rejected(self, client):
        response = client.post("/auth/passkeys/login", json={"credential": {}})
        assert response.status_code == 422


class TestRemovalRoutes:
    def test_removes_a_passkey(self, client, account):
        stored, _ = enrol(client, account["headers"])
        response = client.delete(
            f"/auth/passkeys/{stored['credential_id']}", headers=account["headers"]
        )
        assert response.status_code == 200
        assert client.get("/auth/passkeys", headers=account["headers"]).json()["count"] == 0

    def test_the_last_passkey_can_be_removed(self, client, account):
        """A student who lost the device must be able to enrol a replacement."""
        stored, _ = enrol(client, account["headers"])
        response = client.delete(
            f"/auth/passkeys/{stored['credential_id']}", headers=account["headers"]
        )
        assert response.status_code == 200

    def test_needs_a_session(self, client, account):
        stored, _ = enrol(client, account["headers"])
        assert client.delete(f"/auth/passkeys/{stored['credential_id']}").status_code == 401

    def test_unknown_credential_is_a_404(self, client, account):
        response = client.delete("/auth/passkeys/does-not-exist", headers=account["headers"])
        assert response.status_code == 404

    def test_cannot_remove_another_students_passkey(self, client, account):
        stored, _ = enrol(client, account["headers"])

        with Session(database.engine) as db:
            other = User(
                email="other_passkey@iiitdmj.ac.in",
                full_name="Other",
                username="other_passkey",
                roll_number="23BCS998",
                password_hash=hash_password("Test@12345"),
                is_email_verified=True,
            )
            db.add(other)
            db.commit()
            db.refresh(other)
            other_id, other_username = other.id, other.username

        intruder_token = create_access_token(other_id, other_username)
        response = client.delete(
            f"/auth/passkeys/{stored['credential_id']}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert response.status_code == 404
        # And the owner's passkey survives the attempt.
        assert client.get("/auth/passkeys", headers=account["headers"]).json()["count"] == 1


class TestNoPasswordInvolvement:
    def test_enrolment_leaves_the_password_hash_alone(self, client, account):
        with Session(database.engine) as db:
            before = (
                db.exec(select(User).where(User.username == "passkey_tester"))
                .first()
                .password_hash
            )

        enrol(client, account["headers"])

        with Session(database.engine) as db:
            after = (
                db.exec(select(User).where(User.username == "passkey_tester"))
                .first()
                .password_hash
            )
        assert before == after

    def test_a_revoked_passkey_cannot_sign_in(self, client, account):
        """Removing a credential must actually close the route it opened."""
        stored, authenticator = enrol(client, account["headers"])
        assert client.delete(
            f"/auth/passkeys/{stored['credential_id']}", headers=account["headers"]
        ).status_code == 200

        options = client.post("/auth/passkeys/login/options", json={}).json()
        response = client.post(
            "/auth/passkeys/login",
            json={
                "credential": authenticator.get(options["_challenge"]),
                "challenge": options["_challenge"],
            },
        )
        assert response.status_code == 401
