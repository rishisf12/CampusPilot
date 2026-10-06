"""Feedback: submit text + file, identity snapshotted; admin replies."""
import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

# The database URL is set by tests/conftest.py before any import of the app.
from core.database import create_db_and_tables, engine  # noqa: E402
from main import app  # noqa: E402
from models import Feedback, User, UserProfile  # noqa: E402
from features.auth.routes import create_access_token  # noqa: E402


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with Session(engine) as session:
        user = User(
            email="fb@iiitdmj.ac.in", password_hash="x", full_name="Fb Test",
            username="fbuser", roll_number="23BCS051", is_email_verified=True,
            role="student",
        )
        admin = User(
            email="fbadmin@iiitdmj.ac.in", password_hash="x", full_name="Fb Admin",
            username="fbadmin", roll_number="23BCS052", is_email_verified=True,
            role="admin",
        )
        session.add(user)
        session.add(admin)
        session.commit()
        session.refresh(user)
        session.refresh(admin)
        session.add(UserProfile(
            user_id=user.id, first_name="Fb", last_name="Test",
            programme="BTech", semester=1, branch="SM",
        ))
        session.commit()
        user_id, admin_id = user.id, admin.id

    with TestClient(app) as test_client:
        yield {
            "client": test_client,
            "student": create_access_token(user_id, "fbuser"),
            "admin": create_access_token(admin_id, "fbadmin"),
        }


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_submit_snapshots_identity_from_profile(client):
    """Name/phone/email come from the profile + account when not supplied."""
    res = client["client"].post(
        "/feedback/",
        data={"message": "Please add dark mode", "phone": "9876543210"},
        headers=auth(client["student"]),
    )
    assert res.status_code == 201, res.text[:300]
    body = res.json()
    assert body["message"] == "Please add dark mode"
    assert body["name"] == "Fb Test"
    assert body["phone"] == "9876543210"
    assert body["email"] == "fb@iiitdmj.ac.in"
    assert body["replies"] == []


def test_phone_is_saved_back_to_profile(client):
    """A phone typed in feedback auto-fills next time via the profile."""
    body = client["client"].get("/profile/", headers=auth(client["student"])).json()
    assert body["phone"] == "9876543210"


def test_empty_message_is_rejected(client):
    res = client["client"].post(
        "/feedback/", data={"message": "   "}, headers=auth(client["student"])
    )
    assert res.status_code in (400, 422)


def test_mine_returns_own_submissions(client):
    body = client["client"].get("/feedback/mine", headers=auth(client["student"])).json()
    assert isinstance(body, list) and len(body) >= 1
    assert body[0]["message"] == "Please add dark mode"


def test_responses_is_admin_only(client):
    """Students get 403; admins see every response with name/phone/email."""
    denied = client["client"].get("/feedback/responses", headers=auth(client["student"]))
    assert denied.status_code == 403

    body = client["client"].get("/feedback/responses", headers=auth(client["admin"])).json()
    assert isinstance(body, list) and len(body) >= 1
    first = body[0]
    assert {"name", "phone", "email", "message"} <= set(first)


def test_admin_reply_appears_under_student_entry(client):
    """The reply lands at the bottom of the student's own feedback."""
    mine = client["client"].get("/feedback/mine", headers=auth(client["student"])).json()
    feedback_id = mine[0]["id"]

    reply = client["client"].post(
        f"/feedback/{feedback_id}/reply",
        json={"message": "Dark mode is on the roadmap."},
        headers=auth(client["admin"]),
    )
    assert reply.status_code == 201, reply.text[:300]

    mine_after = client["client"].get("/feedback/mine", headers=auth(client["student"])).json()
    entry = next(item for item in mine_after if item["id"] == feedback_id)
    assert [r["message"] for r in entry["replies"]] == ["Dark mode is on the roadmap."]


def test_student_cannot_reply(client):
    mine = client["client"].get("/feedback/mine", headers=auth(client["student"])).json()
    res = client["client"].post(
        f"/feedback/{mine[0]['id']}/reply",
        json={"message": "I reply to myself"},
        headers=auth(client["student"]),
    )
    assert res.status_code == 403


def test_reply_to_missing_feedback_is_404(client):
    res = client["client"].post(
        "/feedback/999999/reply",
        json={"message": "hello?"},
        headers=auth(client["admin"]),
    )
    assert res.status_code == 404


def test_attachment_is_stored(client):
    res = client["client"].post(
        "/feedback/",
        data={"message": "See screenshot"},
        files={"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=auth(client["student"]),
    )
    assert res.status_code == 201, res.text[:300]
    body = res.json()
    assert body["attachment_original"] == "note.txt"

    with Session(engine) as session:
        row = session.exec(select(Feedback).where(Feedback.id == body["id"])).first()
        assert row is not None and row.attachment_filename is not None


def test_executable_attachment_is_rejected(client):
    res = client["client"].post(
        "/feedback/",
        data={"message": "bad file"},
        files={"file": ("run.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=auth(client["student"]),
    )
    assert res.status_code == 400
