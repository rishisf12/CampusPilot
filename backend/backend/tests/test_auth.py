"""Tests for the auth flow: signup validation, login, and token-protected routes."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

# The database URL is set by tests/conftest.py before any import of the app.
from core.config import get_settings  # noqa: E402
from core.database import create_db_and_tables, engine  # noqa: E402
from main import app  # noqa: E402
from models import User, UserProfile  # noqa: E402

settings = get_settings()

ALLOWED = settings.ALLOWED_EMAIL_DOMAIN


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with TestClient(app) as test_client:
        yield test_client


def make_verified_user(username="student", roll="23BCS125"):
    with Session(engine) as session:
        user = User(
            email=f"{username}@{ALLOWED.lstrip('@')}",
            password_hash="$sha256_crypt$placeholder",
            full_name="Test Student",
            username=username,
            roll_number=roll,
            is_email_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(UserProfile(user_id=user.id, semester=5, branch="CSE A"))
        session.commit()
        token = jwt.encode(
            {
                "sub": str(user.id),
                "username": username,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
    return {"Authorization": f"Bearer {token}"}


class TestSignupValidation:
    def test_rejects_foreign_email_domain(self, client):
        res = client.post("/auth/signup", json={
            "first_name": "A", "last_name": "B", "gender": "Male",
            "programme": "BTech", "semester": 1, "branch": "CSE A",
            "username": "foreignuser", "roll_number": "23BCS999",
            "email": "someone@gmail.com", "password": "Password1",
        })
        assert res.status_code == 422

    def test_rejects_short_password(self, client):
        res = client.post("/auth/signup", json={
            "first_name": "A", "last_name": "B", "gender": "Male",
            "programme": "BTech", "semester": 1, "branch": "CSE A",
            "username": "shortpw", "roll_number": "23BCS998",
            "email": f"shortpw@{ALLOWED.lstrip('@')}", "password": "abc",
        })
        assert res.status_code == 422

    def test_allowed_domain_is_the_college_domain(self):
        assert ALLOWED == "@iiitdmj.ac.in"


class TestLogin:
    def test_login_is_an_oauth2_password_form(self, client):
        """The frontend posts URLSearchParams, so the form parser must accept it."""
        res = client.post("/auth/login", data={
            "username": "nobody", "password": "whatever",
        })
        # Reaches the handler (401), rather than failing form parsing (422).
        assert res.status_code == 401

    def test_login_rejects_unknown_user(self, client):
        res = client.post("/auth/login", data={"username": "ghost", "password": "x"})
        assert res.status_code == 401

    def test_login_blocks_unverified_email(self, client):
        from passlib.hash import sha256_crypt

        with Session(engine) as session:
            session.add(User(
                email=f"unverified@{ALLOWED.lstrip('@')}",
                password_hash=sha256_crypt.hash("Password1"),
                full_name="Unverified",
                username="unverifieduser",
                roll_number="23BCS997",
                is_email_verified=False,
            ))
            session.commit()

        res = client.post("/auth/login", data={
            "username": "unverifieduser", "password": "Password1",
        })
        assert res.status_code == 403
        assert "not verified" in res.json()["detail"].lower()


class TestProtectedRoutes:
    def test_me_requires_a_token(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_me_rejects_garbage_token(self, client):
        res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert res.status_code == 401

    def test_me_reads_the_authorization_header(self, client):
        """Regression: /me used to read the header as a query param and 401'd."""
        headers = make_verified_user()
        res = client.get("/auth/me", headers=headers)
        assert res.status_code == 200, res.text
        assert res.json()["username"] == "student"
        assert res.json()["roll_number"] == "23BCS125"

    def test_profile_requires_a_token(self, client):
        assert client.get("/profile/").status_code == 401

    def test_exam_endpoints_require_a_token(self, client):
        for path in ("/exam/status", "/exam/timetable", "/exam/seating", "/exam/lookup?roll=23BCS125"):
            assert client.get(path).status_code == 401, path

    def test_profile_is_scoped_to_the_user(self, client):
        headers = make_verified_user("scoped")
        res = client.get("/profile/", headers=headers)
        assert res.status_code == 200
        assert res.json()["user_id"] is not None
        assert res.json()["branch"] == "CSE A"

    def test_branch_options_are_exact(self, client):
        headers = make_verified_user("optionsuser")
        res = client.get("/profile/options", headers=headers)
        assert res.status_code == 200
        assert res.json()["branches"] == [
            "CSE A", "CSE B", "DS", "ECE", "ME", "SM", "PG", "MDes",
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])