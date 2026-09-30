"""Attendance service: business logic for attendance calculations."""
import logging
from datetime import date
from typing import List, Optional
from sqlmodel import Session, select
from models import Course, AttendanceRecord, AttendanceStatus
from config import settings

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
    return max(0, int((numerator / denominator)) + 1)


def get_course_summary(session: Session, course_id: int) -> dict:
    """Get attendance summary for a single course."""
    course = session.get(Course, course_id)
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


def get_overall_summary(session: Session) -> dict:
    """Get overall attendance summary across all courses."""
    courses = session.exec(select(Course)).all()
    course_summaries = []
    total_present = 0
    total_absent = 0

    for course in courses:
        summary = get_course_summary(session, course.id)
        if summary:
            course_summaries.append(summary)
            total_present += summary["present"]
            total_absent += summary["absent"]

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
    record = session.get(AttendanceRecord, record_id)
    if not record:
        return False
    session.delete(record)
    logger.info(f"Deleted attendance record {record_id}")
    return True