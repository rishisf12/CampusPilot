"""Tests for the administrator's own profile.

Two things are being defended:

1. **The admin has a profile of their own.** Not the student one: no roll
   number, no branch, no elective list - the things an operator actually
   works with instead.
2. **Nothing of anybody else's.** The endpoints return the admin's own
   profile and their own actions; a student cannot reach them at all.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from core.database import engine
from features.auth.routes import create_access_token
from main import app
from models import AdminProfile, AuditLog, User, UserRole


@pytest.fixture
def anon_client():
    with TestClient(app) as c:
        yield c


def _ensure(username, email, role):
    want = UserRole.ADMIN if role == "admin" else UserRole.STUDENT
    with Session(engine) as s:
        u = s.exec(select(User).where(User.username == username)).first()
        if u is None:
            u = User(
                email=email,
                password_hash="x",
                full_name=username,
                username=username,
                roll_number="23BCS990",
                is_email_verified=True,
                role=want,
            )
            s.add(u)
            s.commit()
            s.refresh(u)
        else:
            u.role = want
            s.add(u)
            s.commit()
        uid = u.id
    return {"Authorization": f"Bearer {create_access_token(uid, username)}"}


@pytest.fixture
def admin_headers():
    return _ensure("admintest", "admintest@iiitdmj.ac.in", "admin")


@pytest.fixture
def student_headers():
    return _ensure("stutest", "stutest@iiitdmj.ac.in", "student")


def _admin_id(username="admintest"):
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        return user.id if user else None


def test_the_admin_profile_is_their_own(anon_client, admin_headers):
    response = anon_client.get("/profile/admin", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    # Their own account, and their own console.
    assert body["email"] == "admintest@iiitdmj.ac.in"
    assert body["role"] == "admin"
    assert body["theme"] in {"system", "light", "dark"}
    assert body["default_window_days"] >= 1
    # And none of the student profile's fields.
    for student_field in (
        "roll_number",
        "branch",
        "semester",
        "elective_codes",
        "attendance_target",
        "section",
        "programme",
    ):
        assert student_field not in body, student_field


def test_a_student_cannot_reach_the_admin_profile(anon_client, student_headers):
    assert anon_client.get("/profile/admin", headers=student_headers).status_code == 403
    assert anon_client.put("/profile/admin", headers=student_headers, json={}).status_code == 403
    assert anon_client.get("/profile/admin/activity", headers=student_headers).status_code == 403


def test_anonymous_cannot_reach_it_either(anon_client):
    assert anon_client.get("/profile/admin").status_code == 401
    assert anon_client.get("/profile/admin/activity").status_code == 401


def test_the_admin_can_set_their_own_console(anon_client, admin_headers):
    response = anon_client.put(
        "/profile/admin",
        headers=admin_headers,
        json={
            "display_name": "Platform Operator",
            "job_title": "Infrastructure",
            "theme": "dark",
            "density": "compact",
            "default_subsection": "C_W_SECURITY",
            "default_window_days": 30,
            "pinned_panels": ["health", "security"],
            "notify_channels": ["email", "telegram"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Platform Operator"
    assert body["theme"] == "dark"
    assert body["default_subsection"] == "C_W_SECURITY"
    assert body["default_window_days"] == 30
    assert body["pinned_panels"] == ["health", "security"]
    assert body["notify_channels"] == ["email", "telegram"]


def test_a_nonsense_preference_is_refused(anon_client, admin_headers):
    for payload in (
        {"theme": "neon"},
        {"density": "enormous"},
        {"default_subsection": "NOT_A_SUBSECTION"},
        {"default_window_days": 900},
        {"notify_channels": ["carrier-pigeon"]},
    ):
        response = anon_client.put("/profile/admin", headers=admin_headers, json=payload)
        assert response.status_code == 422, payload


def test_the_activity_feed_is_the_admins_own(anon_client, admin_headers):
    admin_id = _admin_id()
    with Session(engine) as s:
        s.add(
            AuditLog(
                actor_id=admin_id,
                actor_email="admintest@iiitdmj.ac.in",
                actor_role="admin",
                action="profile.read",
                target_type="admin_profile",
                target_id=str(admin_id),
            )
        )
        s.add(
            AuditLog(
                actor_id=999999,
                actor_email="someoneelse@iiitdmj.ac.in",
                actor_role="admin",
                action="something.else",
                target_type="other",
                target_id="1",
            )
        )
        s.commit()

    response = anon_client.get("/profile/admin/activity", headers=admin_headers)
    assert response.status_code == 200
    actions = [item["action"] for item in response.json()]
    assert "profile.read" in actions
    # Somebody else's action is not in their feed.
    assert "something.else" not in actions
