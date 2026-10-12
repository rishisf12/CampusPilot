"""Attendance service: business logic for attendance calculations."""
import logging
from datetime import date
from typing import List, Optional

from sqlmodel import Session, select

from core.config import settings
from models import AttendanceRecord, AttendanceStatus, Course, TimetableSlot
from features.exam.parser import (
    branch_matches,
    branch_family,
    infer_branch_from_course,
    infer_semester_from_course,
    is_open_elective,
    normalize_branch,
)

logger = logging.getLogger(__name__)


def calculate_percentage(present: int, absent: int) -> float:
    """Calculate attendance percentage. Returns 100.0 if no classes held."""
    total = present + absent
    if total == 0:
        return 100.0
    return round((present / total) * 100, 2)


def get_status(percentage: float) -> str:
    """Return status label based on thresholds from config."""
    if percentage >= settings.attendance_safe:
        return "Safe"
    if percentage >= settings.attendance_warning:
        return "Warning"
    return "Critical"


def classes_can_miss(present: int, absent: int, target: float = 75.0) -> int:
    """How many more classes can be missed and still stay at target%."""
    # Solve: present / (present + absent + x) >= target/100
    # x <= (present * 100 / target) - present - absent
    if present == 0:
        return 0
    max_total = int((present * 100) // target)
    can_miss = max_total - present - absent
    return max(0, can_miss)


def classes_to_attend(present: int, absent: int, target: float = 75.0) -> int:
    """Consecutive classes needed to attend to reach target%."""
    # Solve: (present + x) / (present + absent + x) >= target/100
    # x >= (target * (present + absent) - 100 * present) / (100 - target)
    if present + absent == 0:
        return 0
    if present / (present + absent) * 100 >= target:
        return 0
    numerator = target * (present + absent) - 100 * present
    denominator = 100 - target
    result = numerator / denominator
    return max(0, int(result) + (1 if result > int(result) else 0))


def sync_courses_from_timetable(session: Session) -> int:
    """
    Create/refresh ``Course`` rows from the uploaded weekly timetable.

    This is the "attendance sync from timetable data" step: every distinct
    ``course_code`` in ``TimetableSlot`` becomes a course entry in the
    ``course`` table. Branch and semester information is now tracked via the
    ``course_offering`` and ``timetable_slot_branch`` normalized tables, not
    on the ``course`` table itself.

    If the same (course_code, semester) appears for multiple branches in the
    timetable (e.g. Saturday sem-1 "Extra" classes shared by CSE, ECE, ME, SM,
    DS), the course is simply ensured to exist; filtering is handled by the
    ``course_offering`` / ``timetable_slot_branch`` lookups in ``get_subjects()``.
    """
    from collections import defaultdict
    from sqlmodel import select
    from models import Course, TimetableSlot

    slots = session.exec(select(TimetableSlot)).all()

    # Collect unique course codes from slots
    codes_in_timetable: set[str] = {
        (slot.course_code or "").strip().upper()
        for slot in slots
        if slot.course_code
    }

    # Ensure each code exists in the course table
    created = 0
    for code in codes_in_timetable:
        course = session.exec(select(Course).where(Course.code == code)).first()
        if course is None:
            course = Course(code=code, name=code)
            session.add(course)
            created += 1

    session.commit()
    logger.info("Synced courses from timetable: %d unique codes", len(codes_in_timetable))
    return created


def get_subjects(
    session: Session,
    profile: Optional[dict] = None,
) -> List[dict]:
    """
    Courses the student can mark attendance for, filtered by their profile.

    Only courses that actually appear in the student's timetable are included.
    Electives the student explicitly opted into (profile.elective_codes)
    are included. Other electives are hidden unless they also match branch and
    semester (which open electives usually don't).
    
    Uses the new normalized schema: course_offering, timetable_slot_branch, branch.
    """
    from sqlmodel import select
    from models import Course, TimetableSlot, CourseOffering, Branch, TimetableSlotBranch

    user_id = profile.get("user_id") if profile else None

    if profile:
        branch = profile.get("branch")
        semester = profile.get("semester")
        elective_codes = {
            code.strip().upper()
            for code in (profile or {}).get("elective_codes", [])
            if code and code.strip()
        }

        # Find the branch record for this student
        branch_record = None
        if branch:
            branch_record = session.exec(
                select(Branch).where(Branch.code == branch)
            ).first()

        if branch_record:
            # Use the new normalized schema: find course_offerings for this branch + semester
            offering_ids = session.exec(
                select(CourseOffering.id).where(
                    CourseOffering.branch_id == branch_record.id,
                    CourseOffering.semester == semester
                )
            ).all()
            
            # Get course codes from these offerings
            slot_codes = set()
            if offering_ids:
                offerings = session.exec(
                    select(CourseOffering).where(CourseOffering.id.in_(offering_ids))
                ).all()
                slot_codes = {o.course_id for o in offerings}  # course_ids
                # Get actual course codes
                course_ids = list(slot_codes)
                courses_map = {c.id: c.code.upper() for c in session.exec(
                    select(Course).where(Course.id.in_(course_ids))
                ).all()}
                slot_codes = set(courses_map.values())
        else:
            # Fallback: use timetable_slot.offering_id (populated for single-branch courses)
            # This replaces the old regex on branch_or_program with the normalized FK
            slot_codes = set()
            slot_query = select(TimetableSlot).where(TimetableSlot.semester == semester)
            if offering_id is not None:
                # Use the offering_id from the first matching slot as a guide,
                # but we need to find all slots with the same offering_id
                # Get a reference offering_id from slots matching the branch
                ref_offering = session.exec(
                    select(TimetableSlot.offering_id).where(
                        TimetableSlot.semester == semester
                    ).limit(1)
                ).first()
                if ref_offering:
                    slot_query = slot_query.where(
                        TimetableSlot.offering_id == ref_offering
                    )
            slot_results = session.exec(slot_query).all()
            slot_codes = {
                (slot.course_code or "").upper()
                for slot in slot_results
                if slot.course_code
            }

        # Now query courses that are either in the timetable or are elected electives
        result: List[dict] = []
        for course in session.exec(select(Course)).all():
            code = (course.code or "").upper()
            is_profile_elective = code in elective_codes
            in_timetable = code in slot_codes

            if not (is_profile_elective or in_timetable):
                continue

            summary = get_course_summary(session, course.id, user_id)
            if summary:
                result.append(summary)
        return result

    # No profile: return all courses (fallback for admin)
    courses = session.exec(select(Course)).all()
    result = []
    for course in courses:
        summary = get_course_summary(session, course.id, user_id)
        if summary:
            result.append(summary)
    return result


def get_course_calendar(session: Session, course_id: int, user_id: int) -> List[dict]:
    """
    Per-date attendance records for a course, oldest first.

    This is the "course calendar" backing the attendance calendar view.
    Filtered by user_id to ensure multi-user isolation.
    """
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        return []

    records = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id == course_id,
            AttendanceRecord.user_id == user_id
        )
    ).all()
    records.sort(key=lambda r: r.date)

    return [
        {
            "id": record.id,
            "date": record.date.isoformat(),
            "day": record.date.strftime("%A"),
            "status": record.status.value
            if hasattr(record.status, "value")
            else str(record.status),
        }
        for record in records
    ]


def get_course_summary(session: Session, course_id: int, user_id: int) -> dict:
    """Get attendance summary for a single course, filtered by user_id."""
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        return None

    records = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id == course_id,
            AttendanceRecord.user_id == user_id
        )
    ).all()

    present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    cancelled = sum(1 for r in records if r.status == AttendanceStatus.CANCELLED)

    pct = calculate_percentage(present, absent)

    return {
        "course_id": course.id,
        "course_code": course.code,
        "course_name": course.name,
        "present": present,
        "absent": absent,
        "cancelled": cancelled,
        "total_held": present + absent,
        "percentage": pct,
        "status": get_status(pct),
        "can_miss": classes_can_miss(present, absent),
        "must_attend": classes_to_attend(present, absent),
    }


def get_overall_summary(session: Session, profile: Optional[dict] = None) -> dict:
    """
    Overall attendance summary.

    When a profile is supplied the totals cover only that student's subjects, so
    a shared database does not mix in other branches' courses.
    """
    if profile:
        course_summaries = get_subjects(session, profile)
    else:
        course_summaries = []
        for course in session.exec(select(Course)).all():
            summary = get_course_summary(session, course.id, user_id)
            if summary:
                course_summaries.append(summary)

    total_present = sum(s["present"] for s in course_summaries)
    total_absent = sum(s["absent"] for s in course_summaries)
    overall_pct = calculate_percentage(total_present, total_absent)

    return {
        "overall_percentage": overall_pct,
        "overall_status": get_status(overall_pct),
        "total_present": total_present,
        "total_absent": total_absent,
        "courses": course_summaries,
    }


def mark_attendance(session: Session, course_id: int, dt: date, status: AttendanceStatus, user_id: int) -> AttendanceRecord:
    """Create or update attendance record for a course on a date, scoped to user_id."""
    existing = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id == course_id,
            AttendanceRecord.date == dt,
            AttendanceRecord.user_id == user_id
        )
    ).first()

    if existing:
        existing.status = status
        session.add(existing)
        logger.info(f"Updated attendance: user={user_id}, course={course_id}, date={dt}, status={status}")
        return existing

    record = AttendanceRecord(user_id=user_id, course_id=course_id, date=dt, status=status)
    session.add(record)
    logger.info(f"Created attendance: user={user_id}, course={course_id}, date={dt}, status={status}")
    return record


def delete_attendance(session: Session, record_id: int, user_id: int) -> bool:
    """Delete attendance record by ID, scoped to user_id to prevent cross-user deletion."""
    record = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.id == record_id,
            AttendanceRecord.user_id == user_id
        )
    ).first()
    if not record:
        return False
    session.delete(record)
    logger.info(f"Deleted attendance record {record_id} for user {user_id}")
    return True