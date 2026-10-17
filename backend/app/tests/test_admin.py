"""Admin role gates: /admin/* + secured upload/delete endpoints.

401 anon, 403 student, 200 admin.
"""
import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from core.database import engine
from features.auth.routes import create_access_token
from main import app
from models import User, UserRole


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


def test_admin_stats_gates(anon_client, admin_headers, student_headers):
    assert anon_client.get("/admin/stats").status_code == 401
    assert anon_client.get("/admin/stats", headers=student_headers).status_code == 403
    r = anon_client.get("/admin/stats", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert {"total", "admins", "students", "verified"} <= set(r.json())


def test_admin_users_list_and_role_validation(anon_client, admin_headers, student_headers):
    assert anon_client.get("/admin/users").status_code == 401
    assert anon_client.get("/admin/users", headers=student_headers).status_code == 403
    r = anon_client.get("/admin/users", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 2

    victim = r.json()["users"][0]["id"]
    assert anon_client.patch(f"/admin/users/{victim}/role", json={"role": "admin"}).status_code == 401
    assert (
        anon_client.patch(
            f"/admin/users/{victim}/role", json={"role": "admin"}, headers=student_headers
        ).status_code
        == 403
    )
    bad = anon_client.patch(
        f"/admin/users/{victim}/role", json={"role": "superuser"}, headers=admin_headers
    )
    assert bad.status_code == 400


def test_timetable_upload_needs_admin(anon_client, student_headers):
    files = {"file": ("t.csv", io.BytesIO(b"day,start,end,room,code\nMon,10:00,11:00,R1,C1\n"), "text/csv")}
    assert anon_client.post("/timetable/upload", files=files).status_code == 401
    assert anon_client.post("/timetable/upload", files=files, headers=student_headers).status_code == 403
    assert anon_client.delete("/timetable/").status_code == 401
    assert anon_client.delete("/timetable/", headers=student_headers).status_code == 403


def test_exam_uploads_individual_allowed(anon_client, student_headers):
    """
    Exam uploads are no longer admin-only.

    Anonymous callers still get 401. A signed-in account gets past the
    permission gate - an invalid file now fails in the parser (400), and the
    scoping of what it does upload is covered in test_exam_personal_uploads.py.
    """
    # An empty file parses to zero rows: past the gate now, refused by the parser.
    files = {"file": ("e.csv", io.BytesIO(b""), "text/csv")}
    for url in ("/exam/seating/upload", "/exam/timetable/upload"):
        assert anon_client.post(url, files=files).status_code == 401
        assert anon_client.post(url, files=files, headers=student_headers).status_code == 400
    for url in ("/exam/timetable", "/exam/seating"):
        assert anon_client.delete(url).status_code == 401
        # Clearing only ever touches the caller's own scope, so a student's
        # delete is a no-op the server confirms rather than a refusal.
        assert anon_client.delete(url, headers=student_headers).status_code == 204


def test_reinforcement_needs_admin(anon_client, admin_headers, student_headers):
    assert anon_client.get("/reinforcement/").status_code == 401
    assert anon_client.get("/reinforcement/", headers=student_headers).status_code == 403
    assert anon_client.get("/reinforcement/", headers=admin_headers).status_code == 200


def test_teams_moderation_gates(anon_client, admin_headers, student_headers):
    assert anon_client.get("/admin/teams").status_code == 401
    assert anon_client.get("/admin/teams", headers=student_headers).status_code == 403
    r = anon_client.get("/admin/teams", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert "teams" in r.json()
    assert anon_client.delete("/admin/teams/999999", headers=student_headers).status_code == 403
    assert anon_client.delete("/admin/teams/999999").status_code == 401
    assert anon_client.delete("/admin/teams/999999", headers=admin_headers).status_code == 404
