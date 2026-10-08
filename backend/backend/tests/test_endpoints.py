"""Smoke test: every GET endpoint responds without a 500.

These routes each read settings, query the database and build a response, so a
single call covers a surprising amount of wiring. Several of these endpoints used
to fail with ``AttributeError: 'Settings' object has no attribute ...``.
"""
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

# The database URL is set by tests/conftest.py before any import of the app.
from core.database import create_db_and_tables, engine
from main import app
from models import (
    AttendanceRecord,
    AttendanceStatus,
    Course,
    ExamSeating,
    MidSemSchedule,
    TimetableSlot,
    User,
    UserProfile,
)
from features.auth.routes import create_access_token

SEED_ROWS = [
    TimetableSlot(
        day="Mon", start_time=time(9, 0), end_time=time(10, 0), room="L-101",
        course_code="CS5031", branch_or_program="BTech CSE", semester=5,
    ),
    TimetableSlot(
        day="Mon", start_time=time(11, 0), end_time=time(12, 0), room="CR-102",
        course_code="ME5011", branch_or_program="BTech ME", semester=5,
    ),
    ExamSeating(
        roll_start_prefix="23BCS", roll_start_num=3, roll_end_num=109, room="L-201",
        seating_date=date(2026, 9, 21), start_time=time(8, 0), end_time=time(10, 0),
        course_code="CS8036", branch="CSE", semester=7,
    ),
    MidSemSchedule(
        schedule_date=date(2025, 9, 29), start_time=time(10, 30), end_time=time(12, 30),
        course_code="CS8036", room="L-102", branch="CSE", semester=7,
    ),
    # Same branch and day, but this student's own semester.
    MidSemSchedule(
        schedule_date=date(2025, 9, 29), start_time=time(15, 30), end_time=time(17, 30),
        course_code="CS5031", room="L-103", branch="CSE", semester=5,
    ),
    # A different branch: must stay hidden from a CSE student.
    MidSemSchedule(
        schedule_date=date(2025, 9, 30), start_time=time(10, 30), end_time=time(12, 30),
        course_code="ME5011", room="L-104", branch="ME", semester=5,
    ),
]


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with Session(engine) as session:
        user = User(
            email="smoke@iiitdmj.ac.in", password_hash="x", full_name="Smoke Test",
            username="smokeuser", roll_number="23BCS050", is_email_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        session.add(UserProfile(user_id=user.id, programme="BTech", semester=5, branch="CSE A"))
        session.add(Course(code="CS5031", name="CS5031", semester=5, branch="CSE"))
        for row in SEED_ROWS:
            session.add(row)
        session.commit()

        course = session.exec(select(Course).where(Course.code == "CS5031")).first()
        session.add(AttendanceRecord(course_id=course.id, date=date(2026, 1, 5),
                                     status=AttendanceStatus.PRESENT))
        session.commit()
        user_id = user.id  # read inside the session; the instance detaches after

    with TestClient(app) as test_client:
        yield test_client, create_access_token(user_id, "smokeuser")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


GET_ENDPOINTS = [
    "/health",
    "/auth/me",
    "/profile/",
    "/profile/options",
    "/timetable/slots",
    "/timetable/options",
    "/schedule/now",
    "/schedule/courses/extra",
    "/rooms/vacant",
    "/rooms/vacant?mode=manual&day=Mon&hour=10:30",
    "/rooms/all",
    "/exam/status",
    "/exam/timetable",
    "/exam/seating",
    "/exam/lookup?roll=23BCS050",
    "/exam/quick-lookup?roll=23BCS050",
    "/attendance/summary",
    "/attendance/subjects",
    "/attendance/records",
    "/attendance/course/1",
    "/attendance/sync",
    "/feedback/mine",
    # /feedback/responses is admin-only; covered in test_feedback.py.
]


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_get_endpoint_does_not_500(client, path):
    """Every read endpoint must return a real response, never a 500."""
    test_client, token = client
    res = test_client.get(path, headers=auth(token))
    assert res.status_code != 500, f"{path} -> {res.status_code} {res.text[:300]}"
    assert res.status_code < 400, f"{path} -> {res.status_code} {res.text[:300]}"


def test_schedule_now_uses_college_hours(client):
    """Regression: /schedule/now raised on settings.college_start_hour."""
    test_client, token = client
    body = test_client.get("/schedule/now", headers=auth(token)).json()
    assert "current_class" in body
    assert "current_time" in body


def test_rooms_vacant_reports_timetable_state(client):
    """Regression: /rooms/vacant 500'd with an empty timetable."""
    test_client, token = client
    body = test_client.get("/rooms/vacant", headers=auth(token)).json()
    assert body["has_timetable"] is True
    assert "L-101" in body["vacant_rooms"]


def test_timetable_options_lists_discovered_values(client):
    test_client, token = client
    body = test_client.get("/timetable/options", headers=auth(token)).json()
    expected_slots = sum(1 for row in SEED_ROWS if isinstance(row, TimetableSlot))
    assert body["total_slots"] == expected_slots
    assert "CS5031" in body["courses"]
    assert "ME5011" in body["courses"]
    assert 5 in body["semesters"]


def test_exam_lookup_finds_the_seeded_range(client):
    """Rule 2: a continuous range yields the exact room."""
    test_client, token = client
    body = test_client.get("/exam/lookup?roll=23BCS050", headers=auth(token)).json()
    assert body["exams"], body
    exam = body["exams"][0]
    assert exam["room"] == "L-201"
    assert exam["course_code"] == "CS8036"
    assert exam["rule"] == 2
    assert exam["date"] == "2026-09-21"


def test_exam_timetable_is_grouped_by_day(client):
    test_client, token = client
    body = test_client.get("/exam/timetable", headers=auth(token)).json()
    assert body["days"], body
    # Only the student's own semester (5) survives the profile filter.
    assert [day["date"] for day in body["days"]] == ["2025-09-29"]
    first = body["days"][0]
    assert first["day"] == "Monday"
    assert [e["course_code"] for e in first["exams"]] == ["CS5031"]
    assert first["exams"][0]["room"] == "L-103"


def test_exam_data_is_scoped_by_profile(client):
    """A CSE A sem-5 student sees neither the ME paper nor the sem-7 paper."""
    test_client, token = client
    body = test_client.get("/exam/timetable", headers=auth(token)).json()
    assert body["profile"] == {"branch": "CSE A", "semester": 5}
    codes = [e["course_code"] for day in body["days"] for e in day["exams"]]
    assert "ME5011" not in codes
    assert "CS8036" not in codes
    assert codes == ["CS5031"]


def test_attendance_subjects_are_synced_from_the_timetable(client):
    """Attendance sync turns timetable course codes into markable subjects."""
    test_client, token = client
    body = test_client.get("/attendance/subjects", headers=auth(token)).json()
    codes = [s["course_code"] for s in body["subjects"]]
    assert "CS5031" in codes


def test_attendance_calendar_is_returned_per_course(client):
    test_client, token = client
    courses = test_client.get("/attendance/subjects", headers=auth(token)).json()["subjects"]
    course_id = next(c["course_id"] for c in courses if c["course_code"] == "CS5031")
    body = test_client.get(f"/attendance/course/{course_id}", headers=auth(token)).json()
    assert "calendar" in body
    assert body["calendar"][0]["status"] == "Present"


def test_quick_lookup_returns_only_date_room_course(client):
    test_client, token = client
    exams = test_client.get("/exam/quick-lookup?roll=23BCS050", headers=auth(token)).json()["exams"]
    assert exams
    assert set(exams[0]) == {"date", "day", "room", "course_code"}


def test_pdf_download_is_a_pdf(client):
    test_client, token = client
    res = test_client.get("/exam/pdf?roll=23BCS050", headers=auth(token))
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])