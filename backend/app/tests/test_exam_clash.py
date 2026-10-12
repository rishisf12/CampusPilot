"""
Tests for personal exam-clash detection.

The detector answers "which of *my* exams overlap?", so the cases that matter
are the ones that used to produce false positives: one exam split across several
halls, back-to-back slots, and open electives the student has not opted into.
"""
from datetime import date, time

import pytest
from sqlmodel import Session, delete

from core.database import create_db_and_tables, engine
from models import Course, ExamSeating
from features.exam.clash import (
    clash_summary,
    collect_student_exams,
    declared_course_codes,
    detect_student_exam_clashes,
    overlaps,
)

PROFILE = {"branch": "CSE A", "semester": 5, "elective_codes": []}
DAY = date(2026, 9, 23)


def _clock(value):
    """``"08:30"`` -> ``time(8, 30)``."""
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _row(course, *, room="L-101", roll=(1, 99), slot=("08:00", "10:00"), day=DAY, extra=False):
    """One seating-index row: a roll range sat in one room for one time band."""
    return ExamSeating(
        roll_start_prefix="23BCS",
        roll_start_num=roll[0],
        roll_end_num=roll[1],
        room=room,
        seating_date=day,
        start_time=_clock(slot[0]),
        end_time=_clock(slot[1]),
        course_code=course,
        branch="CSE",
        semester=5,
        is_extra=extra,
    )


def reset(rows=(), courses=()):
    with Session(engine) as session:
        session.exec(delete(ExamSeating))
        session.exec(delete(Course).where(Course.code.in_(
            ["HS1001", "OE3E33", "OE4M76", "ME5011"])))
        for course in courses:
            session.add(course)
        session.commit()
        for row in rows:
            session.add(row)
        session.commit()


def extra_course(code):
    return Course(code=code, name=code, semester=5, branch="ALL", is_extra=True)


@pytest.fixture(autouse=True)
def clean():
    create_db_and_tables()
    reset()
    yield
    reset()


class TestOverlaps:
    def test_same_slot(self):
        assert overlaps(time(9, 0), time(10, 0), time(9, 0), time(10, 0)) is True

    def test_partial_overlap(self):
        assert overlaps(time(9, 0), time(10, 0), time(9, 30), time(10, 30)) is True

    def test_back_to_back_is_not_a_clash(self):
        """Ending at 10:00 and starting at 10:00 is fine."""
        assert overlaps(time(9, 0), time(10, 0), time(10, 0), time(11, 0)) is False

    def test_fully_contained(self):
        assert overlaps(time(8, 0), time(12, 0), time(9, 0), time(10, 0)) is True


class TestNoFalsePositives:
    def test_one_exam_listed_in_two_halls_is_not_a_clash(self):
        """The index repeating a roll across halls for one paper = one exam."""
        reset([
            _row("CS5031", room="L-101", roll=(1, 99)),
            _row("CS5031", room="L-102", roll=(1, 99)),
        ])
        with Session(engine) as session:
            exams = collect_student_exams(session, "23BCS010", PROFILE)
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        assert len(exams) == 1
        assert exams[0]["rooms"] == ["L-101", "L-102"]
        assert clashes == []

    def test_disjoint_split_gives_each_roll_its_own_hall(self):
        """Disjoint sub-ranges: a roll belongs to exactly one hall."""
        reset([
            _row("CS5031", room="L-101", roll=(1, 50)),
            _row("CS5031", room="L-102", roll=(51, 99)),
            _row("CS5031", room="CR-101", roll=(100, 150)),
        ])
        with Session(engine) as session:
            first = collect_student_exams(session, "23BCS010", PROFILE)
            second = collect_student_exams(session, "23BCS075", PROFILE)
            third = collect_student_exams(session, "23BCS120", PROFILE)
        assert [e["rooms"] for e in first] == [["L-101"]]
        assert [e["rooms"] for e in second] == [["L-102"]]
        assert [e["rooms"] for e in third] == [["CR-101"]]

    def test_same_course_same_slot_different_rooms_is_not_a_clash(self):
        reset([
            _row("CS5031", room="L-101", roll=(1, 50)),
            _row("CS5031", room="L-102", roll=(51, 99)),
        ])
        with Session(engine) as session:
            assert detect_student_exam_clashes(session, "23BCS010", PROFILE) == []

    def test_different_days_is_not_a_clash(self):
        reset([
            _row("CS5031", room="L-101", day=date(2026, 9, 23)),
            _row("CS5032", room="L-102", day=date(2026, 9, 24)),
        ])
        with Session(engine) as session:
            assert detect_student_exam_clashes(session, "23BCS010", PROFILE) == []

    def test_back_to_back_slots_are_not_a_clash(self):
        reset([
            _row("CS5031", room="L-101", slot=("09:00", "10:00")),
            _row("CS5032", room="L-102", slot=("10:00", "11:00")),
        ])
        with Session(engine) as session:
            assert detect_student_exam_clashes(session, "23BCS010", PROFILE) == []

    def test_roll_outside_every_range_is_quiet(self):
        reset([_row("CS5031", roll=(1, 99))])
        with Session(engine) as session:
            assert detect_student_exam_clashes(session, "23BCS500", PROFILE) == []

    def test_single_exam_is_quiet(self):
        reset([_row("CS5031")])
        with Session(engine) as session:
            assert detect_student_exam_clashes(session, "23BCS010", PROFILE) == []


class TestRealClashes:
    def test_two_regular_courses_at_the_same_time(self):
        reset([
            _row("CS5031", room="L-101"),
            _row("CS5032", room="L-102"),
        ])
        with Session(engine) as session:
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        assert len(clashes) == 1
        assert clashes[0]["date"] == "2026-09-23"
        assert clashes[0]["day"] == "Wednesday"
        assert clashes[0]["start_time"] == "08:00"
        assert {c["course_code"] for c in clashes[0]["courses"]} == {"CS5031", "CS5032"}

    def test_rooms_are_reported_for_both_courses(self):
        reset([
            _row("CS5031", room="L-101"),
            _row("CS5032", room="CR-202"),
        ])
        with Session(engine) as session:
            clash = detect_student_exam_clashes(session, "23BCS010", PROFILE)[0]
        rooms = {c["course_code"]: c["rooms"] for c in clash["courses"]}
        assert rooms == {"CS5031": ["L-101"], "CS5032": ["CR-202"]}

    def test_partial_overlap_reports_the_union_of_the_slot(self):
        reset([
            _row("CS5031", room="L-101", slot=("09:00", "10:30")),
            _row("CS5032", room="L-102", slot=("10:00", "11:00")),
        ])
        with Session(engine) as session:
            clash = detect_student_exam_clashes(session, "23BCS010", PROFILE)[0]
        assert clash["start_time"] == "09:00"
        assert clash["end_time"] == "11:00"

    def test_extra_course_clashing_with_a_regular_course(self):
        """The case this feature exists for."""
        reset(
            [
                _row("CS5031", room="L-101"),
                _row("HS1001", room="L-102", extra=True),
            ],
            courses=[extra_course("HS1001")],
        )
        with Session(engine) as session:
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        assert len(clashes) == 1
        flagged = [c for c in clashes[0]["courses"] if c["is_extra"]]
        assert flagged and flagged[0]["course_code"] == "HS1001"

    def test_two_declared_extras_clashing(self):
        reset(
            [
                _row("OE3E33", room="L-101", extra=True),
                _row("OE4M76", room="L-102", extra=True),
            ],
            courses=[Course(code="OE3E33", name="OE3E33", semester=5, branch="CSE", is_elective=True)],
        )
        profile = {"branch": "CSE A", "semester": 5, "elective_codes": ["OE3E33", "OE4M76"]}
        with Session(engine) as session:
            clashes = detect_student_exam_clashes(session, "23BCS010", profile)
        assert len(clashes) == 1

    def test_three_way_clash_reports_every_pair(self):
        reset([
            _row("CS5031", room="L-101"),
            _row("CS5032", room="L-102"),
            _row("CS5033", room="L-103"),
        ])
        with Session(engine) as session:
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        assert len(clashes) == 3  # three unordered pairs

    def test_clashes_are_sorted_by_date_then_time(self):
        reset([
            _row("CS5031", room="L-101", slot=("15:00", "17:00"), day=date(2026, 9, 25)),
            _row("CS5032", room="L-102", slot=("15:00", "17:00"), day=date(2026, 9, 25)),
            _row("CS5033", room="L-103", slot=("09:00", "10:00"), day=date(2026, 9, 22)),
            _row("CS5034", room="L-104", slot=("09:00", "10:00"), day=date(2026, 9, 22)),
        ])
        with Session(engine) as session:
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        assert [(c["date"], c["start_time"]) for c in clashes] == [
            ("2026-09-22", "09:00"),
            ("2026-09-25", "15:00"),
        ]


class TestUndeclaredSharedCourses:
    def test_undeclared_open_elective_never_clashes(self):
        """An OE paper the student has not opted into must not create a clash."""
        reset([
            _row("CS5031", room="L-101"),
            _row("OE3E33", room="L-102", extra=True),
        ])
        with Session(engine) as session:
            exams = collect_student_exams(session, "23BCS010", PROFILE)
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        assert [e["course_code"] for e in exams] == ["CS5031"]
        assert clashes == []

    def test_declared_elective_is_included(self):
        reset([
            _row("CS5031", room="L-101"),
            _row("OE3E33", room="L-102", extra=True),
        ])
        profile = {"branch": "CSE A", "semester": 5, "elective_codes": ["OE3E33"]}
        with Session(engine) as session:
            exams = collect_student_exams(session, "23BCS010", profile)
        assert "OE3E33" in [e["course_code"] for e in exams]

    def test_declared_codes_merge_electives_and_extra_courses(self):
        reset(courses=[extra_course("HS1001")])
        profile = {"branch": "CSE A", "semester": 5, "elective_codes": ["oe3e33"]}
        with Session(engine) as session:
            codes = declared_course_codes(session, profile)
        assert codes == {"OE3E33", "HS1001"}


class TestSummary:
    def test_counts_and_extra_flag(self):
        reset(
            [
                _row("CS5031", room="L-101"),
                _row("HS1001", room="L-102", extra=True),
            ],
            courses=[extra_course("HS1001")],
        )
        with Session(engine) as session:
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        summary = clash_summary(clashes)
        assert summary["clash_count"] == 1
        assert summary["dates_affected"] == ["2026-09-23"]
        assert summary["involves_extra_course"] is True

    def test_summary_when_clean(self):
        reset([_row("CS5031")])
        with Session(engine) as session:
            clashes = detect_student_exam_clashes(session, "23BCS010", PROFILE)
        assert clash_summary(clashes) == {
            "clash_count": 0,
            "dates_affected": [],
            "involves_extra_course": False,
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])