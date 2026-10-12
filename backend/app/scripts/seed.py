"""Seed script: loads sample timetable, courses, attendance, and exam data."""
import sys
import logging
from pathlib import Path
from datetime import date, time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import session_scope
from models import (
    Course, AttendanceRecord, AttendanceStatus,
    TimetableSlot, UserProfile, ExamSeating
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_courses(session):
    from sqlmodel import select
    courses = [
        Course(code="CS301", name="Database Systems", semester=5, branch="CSE", is_elective=False),
        Course(code="CS302", name="Computer Networks", semester=5, branch="CSE", is_elective=False),
        Course(code="CS303", name="Operating Systems", semester=5, branch="CSE", is_elective=False),
        Course(code="CS304", name="Machine Learning", semester=5, branch="CSE", is_elective=True),
        Course(code="MA201", name="Discrete Mathematics", semester=3, branch="CSE", is_elective=False),
        Course(code="EE101", name="Basic Electrical", semester=1, branch="EE", is_elective=False),
        # Extra course (cross-semester)
        Course(code="HS101", name="Professional Ethics", semester=5, branch="CSE", is_elective=False, is_extra=True),
    ]
    result = {}
    for c in courses:
        existing = session.exec(select(Course).where(Course.code == c.code)).first()
        if existing:
            result[c.code] = existing.id
        else:
            session.add(c)
            session.flush()
            result[c.code] = c.id
    logger.info(f"Seeded {len(courses)} courses")
    return result


def seed_attendance(session, course_ids):
    today = date.today()
    records = [
        AttendanceRecord(course_id=course_ids["CS301"], date=date(today.year, today.month, 1), status=AttendanceStatus.PRESENT),
        AttendanceRecord(course_id=course_ids["CS301"], date=date(today.year, today.month, 3), status=AttendanceStatus.PRESENT),
        AttendanceRecord(course_id=course_ids["CS301"], date=date(today.year, today.month, 5), status=AttendanceStatus.ABSENT),
        AttendanceRecord(course_id=course_ids["CS301"], date=date(today.year, today.month, 8), status=AttendanceStatus.PRESENT),
        AttendanceRecord(course_id=course_ids["CS301"], date=date(today.year, today.month, 10), status=AttendanceStatus.CANCELLED),
        AttendanceRecord(course_id=course_ids["CS302"], date=date(today.year, today.month, 2), status=AttendanceStatus.PRESENT),
        AttendanceRecord(course_id=course_ids["CS302"], date=date(today.year, today.month, 4), status=AttendanceStatus.ABSENT),
        AttendanceRecord(course_id=course_ids["CS302"], date=date(today.year, today.month, 6), status=AttendanceStatus.ABSENT),
        AttendanceRecord(course_id=course_ids["CS302"], date=date(today.year, today.month, 9), status=AttendanceStatus.PRESENT),
        AttendanceRecord(course_id=course_ids["CS303"], date=date(today.year, today.month, 1), status=AttendanceStatus.PRESENT),
        AttendanceRecord(course_id=course_ids["CS303"], date=date(today.year, today.month, 3), status=AttendanceStatus.PRESENT),
        AttendanceRecord(course_id=course_ids["CS303"], date=date(today.year, today.month, 5), status=AttendanceStatus.PRESENT),
    ]
    for r in records:
        session.add(r)
    logger.info(f"Seeded {len(records)} attendance records")


def seed_timetable(session):
    slots = [
        # Mon
        TimetableSlot(day="Mon", start_time=time(9, 0), end_time=time(10, 0), room="L-101", course_code="CS301", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Mon", start_time=time(10, 0), end_time=time(11, 0), room="L-102", course_code="CS302", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Mon", start_time=time(11, 15), end_time=time(12, 15), room="L-101", course_code="CS303", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Mon", start_time=time(14, 0), end_time=time(15, 0), room="CR-201", course_code="CS304", branch_or_program="CSE", semester=5),
        # Tue
        TimetableSlot(day="Tue", start_time=time(9, 0), end_time=time(10, 0), room="L-102", course_code="CS302", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Tue", start_time=time(10, 0), end_time=time(11, 0), room="L-101", course_code="CS301", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Tue", start_time=time(11, 15), end_time=time(12, 15), room="L-201", course_code="CS303", branch_or_program="CSE", semester=5),
        # Wed
        TimetableSlot(day="Wed", start_time=time(9, 0), end_time=time(10, 0), room="L-101", course_code="CS303", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Wed", start_time=time(10, 0), end_time=time(11, 0), room="CR-201", course_code="CS304", branch_or_program="CSE", semester=5),
        # Thu
        TimetableSlot(day="Thu", start_time=time(9, 0), end_time=time(10, 0), room="L-102", course_code="CS301", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Thu", start_time=time(10, 0), end_time=time(11, 0), room="L-101", course_code="CS302", branch_or_program="CSE", semester=5),
        # Fri
        TimetableSlot(day="Fri", start_time=time(9, 0), end_time=time(10, 0), room="L-101", course_code="CS303", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Fri", start_time=time(10, 0), end_time=time(11, 0), room="L-102", course_code="CS301", branch_or_program="CSE", semester=5),
    ]
    for s in slots:
        session.add(s)
    logger.info(f"Seeded {len(slots)} timetable slots")


def seed_profile(session):
    profile = UserProfile(id=1, semester=5, branch="CSE", elective_codes=["CS304"])
    session.merge(profile)
    logger.info("Seeded user profile")


def seed_exams(session):
    exams = [
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=50, room="L-101", exam_date=date(2026, 12, 15), start_time=time(9, 0), end_time=time(12, 0), course_code="CS301"),
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=51, roll_end_num=100, room="L-102", exam_date=date(2026, 12, 15), start_time=time(9, 0), end_time=time(12, 0), course_code="CS301"),
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=100, room="CR-201", exam_date=date(2026, 12, 17), start_time=time(9, 0), end_time=time(12, 0), course_code="CS302"),
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=100, room="L-201", exam_date=date(2026, 12, 19), start_time=time(14, 0), end_time=time(17, 0), course_code="CS303"),
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=30, room="CR-202", exam_date=date(2026, 12, 21), start_time=time(9, 0), end_time=time(12, 0), course_code="CS304"),
    ]
    for e in exams:
        session.add(e)
    logger.info(f"Seeded {len(exams)} exam seating records")


def main():
    from core.database import create_db_and_tables
    create_db_and_tables()
    with session_scope() as session:
        course_ids = seed_courses(session)
        seed_attendance(session, course_ids)
        seed_timetable(session)
        seed_profile(session)
        seed_exams(session)
    logger.info("Seeding complete.")


if __name__ == "__main__":
    main()