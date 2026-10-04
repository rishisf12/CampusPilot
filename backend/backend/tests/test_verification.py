"""Tests for signup -> email verification -> login.

The SMTP sender is replaced with a stub so the flow can be exercised without
sending real mail; the 6-digit code and its 10-minute expiry are verified
directly against the in-memory store the routes use.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

# The database URL is set by tests/conftest.py before any import of the app.
from config import get_settings  # noqa: E402
from database import engine  # noqa: E402
from main import app  # noqa: E402
from routes import auth as auth_routes  # noqa: E402

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


class TestEmailVerificationFlow:
    def test_full_signup_verify_login(self, client, mail):
        signup = make_signup()

        # 1. Signup sends a 6-digit code.
        res = client.post("/auth/signup", json=signup)
        assert res.status_code == 200, res.text
        assert len(mail) == 1
        assert mail[0]["email"] == signup["email"]
        code = mail[0]["code"]
        assert len(code) == 6 and code.isdigit()

        # 2. Login is blocked while the address is unverified.
        res = client.post("/auth/login", data={
            "username": signup["username"], "password": signup["password"],
        })
        assert res.status_code == 403

        # 3. A wrong code is rejected.
        res = client.post("/auth/verify-email", json={
            "email": signup["email"], "code": "000000" if code != "000000" else "111111",
        })
        assert res.status_code == 400
        assert res.json()["detail"] == "Invalid verification code"

        # 4. The right code verifies the account.
        res = client.post("/auth/verify-email", json={
            "email": signup["email"], "code": code,
        })
        assert res.status_code == 200, res.text

        # 5. Login now succeeds and returns a token.
        res = client.post("/auth/login", data={
            "username": signup["username"], "password": signup["password"],
        })
        assert res.status_code == 200
        token = res.json()["access_token"]
        assert token.count(".") == 2  # header.payload.signature

        # 6. The token works on a protected route.
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["username"] == signup["username"]
        assert res.json()["is_email_verified"] is True

    def test_signup_creates_a_profile_with_the_chosen_branch(self, client, mail):
        signup = make_signup(branch="MDes", programme="MDes", semester=3)
        assert client.post("/auth/signup", json=signup).status_code == 200

        with Session(engine) as session:
            from sqlmodel import select

            from models import UserProfile

            profile = session.exec(
                select(UserProfile).where(UserProfile.branch == "MDes")
            ).first()
            assert profile is not None
            assert profile.semester == 3
            assert profile.programme == "MDes"

    def test_duplicate_email_is_rejected(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        res = client.post("/auth/signup", json=make_signup(email=signup["email"]))
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"]

    def test_duplicate_username_is_rejected(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        res = client.post("/auth/signup", json=make_signup(username=signup["username"]))
        assert res.status_code == 400
        assert "already taken" in res.json()["detail"]

    def test_duplicate_roll_number_is_rejected(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        res = client.post("/auth/signup", json=make_signup(roll_number=signup["roll_number"]))
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"]

    def test_resend_code_replaces_the_previous_one(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        first = mail[0]["code"]

        res = client.post("/auth/resend-code", json={"email": signup["email"]})
        assert res.status_code == 200
        second = mail[-1]["code"]

        # Only the newest code is valid.
        res = client.post("/auth/verify-email", json={
            "email": signup["email"], "code": first,
        })
        if first == second:
            assert res.status_code == 200
        else:
            assert res.status_code == 400

        if first != second:
            res = client.post("/auth/verify-email", json={
                "email": signup["email"], "code": second,
            })
            assert res.status_code == 200

    def test_resend_rejects_unknown_email(self, client, mail):
        res = client.post("/auth/resend-code", json={
            "email": f"ghost@{ALLOWED.lstrip('@')}",
        })
        assert res.status_code == 404

    def test_resend_rejects_a_verified_account(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        client.post("/auth/verify-email", json={
            "email": signup["email"], "code": mail[0]["code"],
        })
        res = client.post("/auth/resend-code", json={"email": signup["email"]})
        assert res.status_code == 400
        assert "already verified" in res.json()["detail"]

    def test_verifying_twice_is_rejected(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        code = mail[0]["code"]
        client.post("/auth/verify-email", json={"email": signup["email"], "code": code})
        res = client.post("/auth/verify-email", json={"email": signup["email"], "code": code})
        assert res.status_code == 400
        assert "No verification code found" in res.json()["detail"]

    def test_code_expires_after_ten_minutes(self, client, mail):
        """The stored code carries a 10-minute expiry."""
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        record = auth_routes.verification_codes[signup["email"]]
        ttl = record["expires_at"] - datetime.now(timezone.utc)
        assert timedelta(minutes=9) < ttl <= timedelta(minutes=10)

    def test_expired_code_is_rejected(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        record = auth_routes.verification_codes[signup["email"]]
        record["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        res = client.post("/auth/verify-email", json={
            "email": signup["email"], "code": mail[0]["code"],
        })
        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()

    def test_verifying_an_unknown_email_is_rejected(self, client, mail):
        res = client.post("/auth/verify-email", json={
            "email": f"nobody@{ALLOWED.lstrip('@')}", "code": "123456",
        })
        assert res.status_code == 400

    def test_wrong_password_is_rejected(self, client, mail):
        signup = make_signup()
        client.post("/auth/signup", json=signup)
        client.post("/auth/verify-email", json={
            "email": signup["email"], "code": mail[0]["code"],
        })
        res = client.post("/auth/login", data={
            "username": signup["username"], "password": "WrongPassword",
        })
        assert res.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])