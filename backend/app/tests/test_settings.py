"""Tests for the per-user settings endpoints.

Covers the three behaviours the client depends on and that are easy to get wrong:
an unset account reads empty rather than 404, a patch merges instead of
replacing (so two settings changed at once do not erase one another), and a null
value drops a single key rather than the whole document.

The 401 paths are asserted too. Settings are per user, so an endpoint that
answers an anonymous caller with 200 leaks nothing today - but it would the
moment a default document were ever returned instead of {}.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from core.config import get_settings
from core.database import create_db_and_tables, engine
from features.settings.models import UserSettings
from main import app
from models import User, UserProfile

settings = get_settings()
ALLOWED = settings.ALLOWED_EMAIL_DOMAIN


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def account():
    """A signed-in student, plus a header ready to authenticate as them."""
    username = "settings_student"
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username == username)
        ).first()
        if user is None:
            user = User(
                email=f"{username}@{ALLOWED.lstrip('@')}",
                password_hash="$sha256_crypt$placeholder",
                full_name="Settings Student",
                username=username,
                roll_number="23BCS900",
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


@pytest.fixture(autouse=True)
def clean(account):
    """Start each test from an empty document so order cannot matter."""
    with Session(engine) as session:
        session.exec(delete(UserSettings))
        session.commit()
    yield
    with Session(engine) as session:
        session.exec(delete(UserSettings))
        session.commit()


class TestRead:
    def test_an_account_with_nothing_saved_reads_empty(self, client, account):
        """200 with {}, not 404 - the client renders registry defaults."""
        response = client.get("/settings", headers=account)
        assert response.status_code == 200
        assert response.json() == {"settings": {}}

    def test_refuses_an_anonymous_caller(self, client):
        assert client.get("/settings").status_code == 401

    def test_refuses_a_malformed_token(self, client):
        assert client.get("/settings", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


class TestWrite:
    def test_a_patch_is_stored_and_read_back(self, client, account):
        patch = client.patch(
            "/settings", headers=account, json={"settings": {"theme": "dark"}}
        )
        assert patch.status_code == 200
        assert patch.json() == {"settings": {"theme": "dark"}}
        assert client.get("/settings", headers=account).json() == {"settings": {"theme": "dark"}}

    def test_a_second_patch_merges_rather_than_replaces(self, client, account):
        """Two settings changed separately must both survive.

        Replacing the document would mean changing the theme silently undoing the
        notification toggle, which is exactly the bug a KV row invites.
        """
        client.patch("/settings", headers=account, json={"settings": {"theme": "dark"}})
        merged = client.patch(
            "/settings", headers=account, json={"settings": {"density": True}}
        )
        assert merged.json() == {"settings": {"theme": "dark", "density": True}}

    def test_null_removes_one_key_and_keeps_the_rest(self, client, account):
        client.patch(
            "/settings",
            headers=account,
            json={"settings": {"theme": "dark", "density": True}},
        )
        after = client.patch(
            "/settings", headers=account, json={"settings": {"density": None}}
        )
        assert after.json() == {"settings": {"theme": "dark"}}

    def test_values_of_any_json_shape_round_trip(self, client, account):
        """The server stores the document it is given and does not type-check it."""
        payload = {"a_string": "x", "a_number": 3, "a_bool": False, "a_list": [1, 2]}
        client.patch("/settings", headers=account, json={"settings": payload})
        assert client.get("/settings", headers=account).json()["settings"] == payload

    def test_refuses_an_anonymous_write(self, client):
        assert (
            client.patch("/settings", json={"settings": {"theme": "dark"}}).status_code
            == 401
        )


class TestValidation:
    def test_rejects_an_empty_setting_name(self, client, account):
        """An empty key would be unrepresentable in the client registry."""
        response = client.patch("/settings", headers=account, json={"settings": {"": 1}})
        assert response.status_code == 400

    def test_rejects_an_over_long_setting_name(self, client, account):
        response = client.patch(
            "/settings", headers=account, json={"settings": {"x" * 200: 1}}
        )
        assert response.status_code == 400


class TestClear:
    def test_delete_empties_the_document(self, client, account):
        client.patch(
            "/settings", headers=account, json={"settings": {"theme": "dark"}}
        )
        assert client.delete("/settings", headers=account).json() == {"settings": {}}
        assert client.get("/settings", headers=account).json() == {"settings": {}}

    def test_refuses_an_anonymous_clear(self, client):
        assert client.delete("/settings").status_code == 401