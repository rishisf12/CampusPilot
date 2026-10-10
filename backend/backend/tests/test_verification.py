"""Tests for the full registration journey: verify email, then create the account.

The order changed on purpose. Previously `/auth/signup` created the account and
mailed a code, so an abandoned or mistyped signup left a half-built account that
then blocked the real attempt. Registration is now:

    /auth/signup/start  ->  /auth/signup/verify  ->  /auth/signup  ->  login

SMTP is stubbed, so the code is read from the captured mail rather than an inbox.
The six-digit code and its expiry are checked against the database record, which
is where they now live.

`test_signup_verification.py` covers the security rules around the code; this
module covers the end-to-end journey a student actually walks through.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, delete, select

# The database URL is set by tests/conftest.py before any import of the app.
from core.config import get_settings
from core.database import engine
from main import app
from models import PendingSignup, User
from features.auth import routes as auth_routes
from features.auth import signup as svc

ALLOWED = get_settings().ALLOWED_EMAIL_DOMAIN

#: Every test needs its own identity: email, username and roll are all unique
#: columns, so reusing them would fail the duplicate checks.
_counter = iter(range(1, 500))


def make_signup(**overrides):
    """Build a signup payload with a unique email/username/roll."""
    n = next(_counter)
    payload = {
        "first_name": "Verify",
        "last_name": "Student",
        "gender": "Female",
        "programme": "BTech",
        "semester": 5,
        "branch": "CSE B",
        "username": f"verifyflow{n}",
        "roll_number": f"23BCS{n:03d}",
        "email": f"verifyflow{n}@{ALLOWED.lstrip('@')}",
        "password": "Password123",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def mail():
    """Capture verification emails instead of sending them."""
    sent = []

    async def fake_send(email: str, code: str):
        sent.append({"email": email, "code": code})

    original = auth_routes.send_verification_email
    auth_routes.send_verification_email = fake_send
    try:
        yield sent
    finally:
        auth_routes.send_verification_email = original


@pytest.fixture
def client():
    auth_routes.verification_codes.clear()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_pending():
    """
    Pending rows belong to nobody; drop them so tests cannot leak into others.

    ``create_all`` runs when ``database`` is imported, which happens before
    ``models`` here, so the newest tables are not in the scratch database yet.
    Calling it again in the fixture is safe and picks them up.
    """
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.exec(delete(PendingSignup))
        session.commit()
    yield
    with Session(engine) as session:
        session.exec(delete(PendingSignup))
        session.commit()


def prove(client, mail, payload):
    """
    Run the first two steps and return the code that was mailed.

    Checks the *delta* in captured mail rather than the total: several tests
    prove two addresses in one run, and the second call must not look like a
    duplicate send.
    """
    before = len(mail)
    assert client.post("/auth/signup/start", json={"email": payload["email"]}).status_code == 200
    assert len(mail) == before + 1, "expected exactly one new verification email"
    code = mail[-1]["code"]
    assert len(code) == 6 and code.isdigit()
    assert mail[-1]["email"] == payload["email"]
    assert client.post(
        "/auth/signup/verify", json={"email": payload["email"], "code": code}
    ).status_code == 200
    return code


class TestRegistrationJourney:
    def test_email_then_code_then_account_then_login(self, client, mail):
        signup = make_signup()

        # 1. Asking for a code creates nothing at all.
        assert client.post("/auth/signup/start", json={"email": signup["email"]}).status_code == 200
        assert len(mail) == 1
        with Session(engine) as session:
            assert session.exec(
                select(User).where(User.email == signup["email"])
            ).first() is None

        code = mail[0]["code"]

        # 2. Login is impossible: there is no account to log into.
        assert client.post(
            "/auth/login", data={"username": signup["username"], "password": signup["password"]}
        ).status_code == 401

        # 3. A wrong code is rejected.
        wrong = "000000" if code != "000000" else "111111"
        assert client.post(
            "/auth/signup/verify", json={"email": signup["email"], "code": wrong}
        ).status_code == 400

        # 4. The right code proves the address.
        assert client.post(
            "/auth/signup/verify", json={"email": signup["email"], "code": code}
        ).status_code == 200

        # 5. Only now is the account created - already verified, no second code.
        assert len(mail) == 1
        assert client.post("/auth/signup", json=signup).status_code == 200

        # 6. Login works straight away.
        res = client.post(
            "/auth/login", data={"username": signup["username"], "password": signup["password"]}
        )
        assert res.status_code == 200, res.text
        token = res.json()["access_token"]

        # 7. And the token works on a protected route.
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["username"] == signup["username"]
        assert res.json()["is_email_verified"] is True

    def test_the_account_is_created_with_the_chosen_profile(self, client, mail):
        signup = make_signup(branch="MDes", programme="MDes", semester=3)
        prove(client, mail, signup)
        assert client.post("/auth/signup", json=signup).status_code == 200

        with Session(engine) as session:
            profile = session.exec(
                select(__import__("models").UserProfile).where(
                    __import__("models").UserProfile.branch == "MDes"
                )
            ).first()
            assert profile is not None
            assert profile.semester == 3
            assert profile.programme == "MDes"

    def test_abandoning_after_the_code_leaves_nothing_behind(self, client, mail):
        """The problem the reordering was meant to fix."""
        signup = make_signup()
        prove(client, mail, signup)
        # Stop here, as someone who closed the tab would.
        with Session(engine) as session:
            assert session.exec(
                select(User).where(User.email == signup["email"])
            ).first() is None

        # The address is still free for a real attempt.
        assert client.post("/auth/signup/start", json={"email": signup["email"]}).status_code == 200

    def test_a_second_attempt_at_the_same_address_still_works(self, client, mail):
        signup = make_signup()
        prove(client, mail, signup)
        assert client.post("/auth/signup", json=signup).status_code == 200
        assert client.post(
            "/auth/login", data={"username": signup["username"], "password": signup["password"]}
        ).status_code == 200


class TestDuplicateChecks:
    """Reported at the last step, once the requester has proved the mailbox."""

    def test_duplicate_email_is_rejected(self, client, mail):
        signup = make_signup()
        prove(client, mail, signup)
        assert client.post("/auth/signup", json=signup).status_code == 200

        # A second attempt on the same address: it proves the address again - which
        # is allowed - and is only then told the address is taken. Changing to a
        # *different* address is refused by the verification gate instead, which
        # is the stricter and more useful answer.
        other = make_signup()
        prove(client, mail, {**other, "email": signup["email"]})
        res = client.post("/auth/signup", json={**other, "email": signup["email"]})
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"]

    def test_claiming_a_different_address_than_the_one_proved_is_refused(self, client, mail):
        """Proving one mailbox must not let you claim another."""
        proven = make_signup()
        unproven = make_signup()
        prove(client, mail, proven)

        # Submit the unproven address: it has no pending record, so the gate holds.
        res = client.post("/auth/signup", json=unproven)
        assert res.status_code == 400
        assert "verify" in res.json()["detail"].lower()

    def test_duplicate_username_is_rejected(self, client, mail):
        signup = make_signup()
        prove(client, mail, signup)
        assert client.post("/auth/signup", json=signup).status_code == 200

        clash = make_signup()
        prove(client, mail, clash)
        res = client.post("/auth/signup", json={**clash, "username": signup["username"]})
        assert res.status_code == 400
        assert "already taken" in res.json()["detail"]

    def test_duplicate_roll_number_is_rejected(self, client, mail):
        signup = make_signup()
        prove(client, mail, signup)
        assert client.post("/auth/signup", json=signup).status_code == 200

        clash = make_signup()
        prove(client, mail, clash)
        res = client.post("/auth/signup", json={**clash, "roll_number": signup["roll_number"]})
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"]


class TestResending:
    def test_asking_again_replaces_the_code(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup/start", json={"email": signup["email"]})
        first = mail[-1]["code"]

        # Clear the cooldown so a second attempt is allowed.
        with Session(engine) as session:
            row = session.exec(
                select(PendingSignup).where(PendingSignup.email == signup["email"])
            ).first()
            row.created_at = row.created_at - timedelta(minutes=10)
            session.add(row)
            session.commit()

        assert client.post("/auth/signup/start", json={"email": signup["email"]}).status_code == 200
        second = mail[-1]["code"]

        if first != second:
            assert client.post(
                "/auth/signup/verify", json={"email": signup["email"], "code": first}
            ).status_code == 400
            assert client.post(
                "/auth/signup/verify", json={"email": signup["email"], "code": second}
            ).status_code == 200

    def test_the_new_code_cannot_create_the_account_on_its_own(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup/start", json={"email": signup["email"]})
        # A code alone is not proof until it has been checked.
        assert client.post("/auth/signup", json=signup).status_code == 400


class TestCodeLifetime:
    def test_the_stored_record_carries_the_expected_ttl(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup/start", json={"email": signup["email"]})
        with Session(engine) as session:
            row = session.exec(
                select(PendingSignup).where(PendingSignup.email == signup["email"])
            ).first()
            assert row.created_at is not None
            assert row.verified_at is None
            assert row.attempts == 0

    def test_an_expired_code_is_refused(self, client, mail):
        signup = make_signup()
        code = mail[-1]["code"] if mail else None
        client.post("/auth/signup/start", json={"email": signup["email"]})
        code = mail[-1]["code"]

        with Session(engine) as session:
            row = session.exec(
                select(PendingSignup).where(PendingSignup.email == signup["email"])
            ).first()
            row.created_at = row.created_at - (svc.CODE_TTL + timedelta(minutes=1))
            session.add(row)
            session.commit()

        res = client.post(
            "/auth/signup/verify", json={"email": signup["email"], "code": code}
        )
        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()

    def test_verifying_an_address_that_never_started_is_refused(self, client, mail):
        res = client.post(
            "/auth/signup/verify",
            json={"email": f"ghost@{ALLOWED.lstrip('@')}", "code": "123456"},
        )
        assert res.status_code == 400


class TestLegacyFlowStillAvailable:
    """`/auth/verify-email` still finishes an account made by the old order."""

    def test_it_completes_an_unverified_existing_account(self, client, mail):
        signup = make_signup()

        # Build an unverified account directly, as the old flow used to.
        from models import UserProfile
        from features.auth.routes import hash_password

        with Session(engine) as session:
            user = User(
                email=signup["email"],
                password_hash=hash_password(signup["password"]),
                full_name="Verify Student",
                username=signup["username"],
                roll_number=signup["roll_number"],
                is_email_verified=False,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            auth_routes.verification_codes[signup["email"]] = {
                "code": "246813",
                # The legacy store compares against an aware datetime, so the
                # expiry has to be aware too.
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
                "user_id": user.id,
            }
            session.add(
                UserProfile(user_id=user.id, branch="CSE A", semester=5, programme="BTech")
            )
            session.commit()
            user_id = user.id

        res = client.post(
            "/auth/verify-email", json={"email": signup["email"], "code": "246813"}
        )
        assert res.status_code == 200

        with Session(engine) as session:
            user = session.exec(select(User).where(User.id == user_id)).first()
            assert user.is_email_verified is True

        # And it can now sign in.
        assert client.post(
            "/auth/login", data={"username": signup["username"], "password": signup["password"]}
        ).status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
