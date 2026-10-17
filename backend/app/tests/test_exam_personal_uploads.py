"""Personal exam uploads.

Uploading stopped being admin-only: an admin's file is the public index every
account reads, and an individual's upload replaces - and is visible in - their
own account alone. These tests walk that scope through the API.
"""
import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from core.database import engine
from features.auth.routes import create_access_token
from main import app
from models import User, UserRole

# Codes the parser accepts (`[A-Z]{2,3}\d{1,4}`) and that no other test file
# could plausibly seed: ZS/ZZ keep them outside every real branch's range.
PUBLIC_CSV = (
    "date,time,course_code,semester,branch\n"
    "2026-05-20,10:00 AM - 12:00 PM,ZS1001,3,CSE\n"
    "2026-05-22,2:00 PM - 4:00 PM,ZS1001,3,CSE\n"
).encode("utf-8")

PRIVATE_CSV = (
    "date,time,course_code,semester,branch\n"
    "2026-05-21,10:00 AM - 12:00 PM,ZZ1001,3,CSE\n"
).encode("utf-8")

PRIVATE_CSV_SWAPPED = (
    "date,time,course_code,semester,branch\n"
    "2026-05-21,10:00 AM - 12:00 PM,ZZ1002,3,CSE\n"
).encode("utf-8")


def _csv(content: bytes) -> dict:
    return {"file": ("exam.csv", io.BytesIO(content), "text/csv")}


@pytest.fixture
def anon_client():
    with TestClient(app) as c:
        yield c


def _headers(username: str, role: UserRole):
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if user is None:
            user = User(
                email=f"{username}@iiitdmj.ac.in",
                password_hash="x",
                full_name=username,
                username=username,
                roll_number="23BCS981",
                is_email_verified=True,
                role=role,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
        else:
            user.role = role
            s.add(user)
            s.commit()
        user_id = user.id
    return {"Authorization": f"Bearer {create_access_token(user_id, username)}"}


@pytest.fixture
def admin():
    return _headers("examupload_admin", UserRole.ADMIN)


@pytest.fixture
def student_a():
    return _headers("examupload_a", UserRole.STUDENT)


@pytest.fixture
def student_b():
    return _headers("examupload_b", UserRole.STUDENT)


def _timetable_rows(client, headers):
    return client.get("/exam/status", headers=headers).json()["timetable_rows"]


def _course_options(client, headers):
    return client.get("/exam/options", headers=headers).json()["courses"]


def _upload(client, headers, content):
    return client.post("/exam/timetable/upload", files=_csv(content), headers=headers)


def test_public_upload_reaches_every_account_alike(anon_client, admin, student_a, student_b):
    """An admin's upload is the public index: identical counts in every account."""
    response = _upload(anon_client, admin, PUBLIC_CSV)
    assert response.status_code == 200, response.text
    # No scoping note on the public path.
    assert "your account" not in response.json()["message"]

    assert _timetable_rows(anon_client, student_a) == _timetable_rows(anon_client, student_b)
    assert "ZS1001" in _course_options(anon_client, student_b)

    # The admin's own account also reads the rows they uploaded.
    assert "ZS1001" in _course_options(anon_client, admin)


def test_personal_upload_visible_only_to_its_account(anon_client, admin, student_a, student_b):
    """A student's upload shows in their account; nobody else's account grows."""
    public_rows_a = _timetable_rows(anon_client, student_a)
    public_rows_b = _timetable_rows(anon_client, student_b)
    public_rows_admin = _timetable_rows(anon_client, admin)
    assert public_rows_a == public_rows_b, "public rows must reach accounts equally"

    response = _upload(anon_client, student_a, PRIVATE_CSV)
    assert response.status_code == 200, response.text
    assert "your account" in response.json()["message"]

    assert _timetable_rows(anon_client, student_a) == public_rows_a + 1
    assert _timetable_rows(anon_client, student_b) == public_rows_b
    assert _timetable_rows(anon_client, admin) == public_rows_admin

    courses_a = _course_options(anon_client, student_a)
    assert "ZZ1001" in courses_a
    assert "ZZ1001" not in _course_options(anon_client, student_b)
    assert "ZZ1001" not in _course_options(anon_client, admin)


def test_reupload_replaces_not_appends(anon_client, student_a):
    """A second personal upload takes the first one's place."""
    _upload(anon_client, student_a, PRIVATE_CSV)
    rows_after_first = _timetable_rows(anon_client, student_a)

    assert _upload(anon_client, student_a, PRIVATE_CSV_SWAPPED).status_code == 200

    assert _timetable_rows(anon_client, student_a) == rows_after_first
    assert "ZZ1002" in _course_options(anon_client, student_a)
    assert "ZZ1001" not in _course_options(anon_client, student_a)


def test_individual_removal_leaves_the_public_data_alone(anon_client, student_a):
    """Removing clarity: a student's delete clears only their own upload."""
    _upload(anon_client, student_a, PRIVATE_CSV_SWAPPED)
    rows_with_personal = _timetable_rows(anon_client, student_a)

    response = anon_client.delete("/exam/timetable", headers=student_a)
    assert response.status_code == 204

    assert _timetable_rows(anon_client, student_a) == rows_with_personal - 1
