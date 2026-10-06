"""Tests for joining seating-index rooms onto timetable rows."""
from datetime import date, time

import pytest
from sqlmodel import Session, delete

# The database URL is set by tests/conftest.py before any import of the app.
from core.database import create_db_and_tables, engine  # noqa: E402
from models import ExamSeating  # noqa: E402
from features.exam.lookup import fill_rooms_from_seating  # noqa: E402


@pytest.fixture(scope="module")
def seeded():
    create_db_and_tables()
    # Own the CS5031 rows so the shared scratch database cannot interfere.
    with Session(engine) as session:
        session.exec(delete(ExamSeating).where(ExamSeating.course_code == "CS5031"))
        session.commit()
        session.add_all([
            # Most rows put this course in L-201, so L-201 should win.
            ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=50,
                        room="L-201", seating_date=date(2026, 9, 21),
                        start_time=time(10), end_time=time(12),
                        course_code="CS5031", branch="CSE", semester=5),
            ExamSeating(roll_start_prefix="23BCS", roll_start_num=51, roll_end_num=99,
                        room="L-201", seating_date=date(2026, 9, 21),
                        start_time=time(10), end_time=time(12),
                        course_code="CS5031", branch="CSE", semester=5),
            ExamSeating(roll_start_prefix="23BCS", roll_start_num=100, roll_end_num=120,
                        room="CR-101", seating_date=date(2026, 9, 21),
                        start_time=time(10), end_time=time(12),
                        course_code="CS5031", branch="CSE", semester=5),
            # A different day for the same course.
            ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=99,
                        room="L-999", seating_date=date(2026, 9, 23),
                        start_time=time(10), end_time=time(12),
                        course_code="CS5031", branch="CSE", semester=5),
        ])
        session.commit()
    yield
    with Session(engine) as session:
        session.exec(delete(ExamSeating).where(ExamSeating.course_code == "CS5031"))
        session.commit()


def test_room_is_taken_from_the_same_date(seeded):
    rows = [{
        "course_code": "CS5031",
        "schedule_date": "2026-09-21",
        "room": "",
    }]
    with Session(engine) as session:
        fill_rooms_from_seating(session, rows)
    # L-201 covers 150 students vs 21 for CR-101, so L-201 wins.
    assert rows[0]["room"] == "L-201"


def test_specific_day_wins_over_the_global_mode(seeded):
    rows = [{
        "course_code": "CS5031",
        "schedule_date": "2026-09-23",
        "room": "",
    }]
    with Session(engine) as session:
        fill_rooms_from_seating(session, rows)
    assert rows[0]["room"] == "L-999"


def test_unknown_course_is_left_alone(seeded):
    rows = [{"course_code": "ZZ9999", "schedule_date": "2026-09-21", "room": ""}]
    with Session(engine) as session:
        fill_rooms_from_seating(session, rows)
    assert rows[0]["room"] == ""


def test_existing_rooms_are_never_overwritten(seeded):
    rows = [{"course_code": "CS5031", "schedule_date": "2026-09-21", "room": "L-105"}]
    with Session(engine) as session:
        fill_rooms_from_seating(session, rows)
    assert rows[0]["room"] == "L-105"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])