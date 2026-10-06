"""Attendance service: business logic for attendance calculations."""
import logging
from datetime import date
from typing import List, Optional

from sqlmodel import Session, select

from core.config import settings
from models import AttendanceRecord, AttendanceStatus, Course, TimetableSlot
from features.exam.parser import (
    branch_matches,
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
    ``course_code`` in ``TimetableSlot`` becomes a course, carrying the branch and
    semester inferred from the slot so the attendance list can be filtered.

    If the same (course_code, semester) appears for multiple branches in the
    timetable (e.g. Saturday sem-1 "Extra" classes shared by CSE, ECE, ME, SM,
    DS), the course is marked as branch="ALL" so it is visible to every branch.
    """
    slots = session.exec(select(TimetableSlot)).all()

    # First pass: collect branches per (code, semester)
    from collections import defaultdict
    branches_by_code_sem = defaultdict(set)
    semesters_by_code = defaultdict(set)
    for slot in slots:
        code = (slot.course_code or "").strip().upper()
        if not code:
            continue
        branch = normalize_branch(slot.branch_or_program) or infer_branch_from_course(code)
        semester = slot.semester or infer_semester_from_course(code)
        if branch:
            branches_by_code_sem[(code, semester)].add(branch)
        semesters_by_code[code].add(semester)

    # Determine which (code, semester) pairs are shared across branches
    shared = {
        (code, sem)
        for (code, sem), branches in branches_by_code_sem.items()
        if len(branches) > 1
    }

    created = 0
    for slot in slots:
        code = (slot.course_code or "").strip().upper()
        if not code:
            continue
        branch = normalize_branch(slot.branch_or_program) or infer_branch_from_course(code)
        semester = slot.semester or infer_semester_from_course(code)

        # If this course+semester is shared, force branch="ALL" (normalizes to
        # None in branch_family, so branch_matches returns True for everyone).
        if (code, semester) in shared:
            branch = "ALL"

        course = session.exec(select(Course).where(Course.code == code)).first()
        if course is None:
            course = Course(
                code=code,
                name=code,
                semester=semester or 1,
                branch=branch or "ALL",
                is_elective=is_open_elective(code),
            )
            session.add(course)
            created += 1
        else:
            # Refresh the stored metadata against the newly uploaded grid.
            changed = False
            # If this course+semester is shared across branches, force branch="ALL"
            # regardless of what it was before.
            if (code, semester) in shared:
                if course.branch != "ALL":
                    course.branch = "ALL"
                    changed = True
            elif branch and course.branch in (None, "", "ALL"):
                course.branch = branch
                changed = True
            if semester and course.semester != semester:
                course.semester = semester
                changed = True
            if changed:
                session.add(course)

    session.commit()
    logger.info("Synced %d course(s) from timetable (%d new)", len(slots), created)
    return created


def get_subjects(
    session: Session,
    profile: Optional[dict] = None,
) -> List[dict]:
    """
    Courses the student can mark attendance for, filtered by their profile.

    Only electives the student explicitly opted into (profile.elective_codes)
    are included. Other electives are hidden unless they also match branch and
    semester (which open electives usually don't).
    """
    courses = session.exec(select(Course)).all()
    electives = {
        code.strip().upper()
        for code in (profile or {}).get("elective_codes", [])
        if code and code.strip()
    }

    result: List[dict] = []
    for course in courses:
        code = (course.code or "").upper()
        if profile:
            is_profile_elective = code in electives
            branch_ok = branch_matches(course.branch, profile.get("branch")) if course.branch else True
            semester_ok = (
                not profile.get("semester")
                or not course.semester
                or course.semester == profile["semester"]
            )
            if not (is_profile_elective or (branch_ok and semester_ok)):
                continue
        summary = get_course_summary(session, course.id)
        result.append(summary)
    return result


def get_course_calendar(session: Session, course_id: int) -> List[dict]:
    """
    Per-date attendance records for a course, oldest first.

    This is the "course calendar" backing the attendance calendar view.
    """
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        return []

    records = session.exec(
        select(AttendanceRecord).where(AttendanceRecord.course_id == course_id)
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


def get_course_summary(session: Session, course_id: int) -> dict:
    """Get attendance summary for a single course."""
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        return None

    records = session.exec(
        select(AttendanceRecord).where(AttendanceRecord.course_id == course_id)
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
            summary = get_course_summary(session, course.id)
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


def mark_attendance(session: Session, course_id: int, dt: date, status: AttendanceStatus) -> AttendanceRecord:
    """Create or update attendance record for a course on a date."""
    existing = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id == course_id,
            AttendanceRecord.date == dt
        )
    ).first()

    if existing:
        existing.status = status
        session.add(existing)
        logger.info(f"Updated attendance: course={course_id}, date={dt}, status={status}")
        return existing

    record = AttendanceRecord(course_id=course_id, date=dt, status=status)
    session.add(record)
    logger.info(f"Created attendance: course={course_id}, date={dt}, status={status}")
    return record


def delete_attendance(session: Session, record_id: int) -> bool:
    """Delete attendance record by ID."""
    record = session.exec(
        select(AttendanceRecord).where(AttendanceRecord.id == record_id)
    ).first()
    if not record:
        return False
    session.delete(record)
    logger.info(f"Deleted attendance record {record_id}")
    return True