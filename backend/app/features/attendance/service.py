"""Attendance service: business logic for attendance calculations."""
import logging
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import or_
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


def sync_courses_from_timetable(session: Session, owner: Optional[int] = None) -> int:
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

    When ``owner`` is given, only that scope's slots (public plus the owner's
    personal rows) are considered - an admin's upload syncs every public slot,
    an individual's upload syncs only their own.
    """
    from collections import defaultdict
    from models import Course, TimetableSlot

    query = select(TimetableSlot)
    if owner is not None:
        query = query.where(or_(TimetableSlot.uploaded_by.is_(None), TimetableSlot.uploaded_by == owner))
    slots = session.exec(query).all()

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

    # Commit only when something was actually created: this runs on every
    # exam request, and an empty sync should not open a write transaction.
    if created:
        session.commit()
    logger.info("Synced courses from timetable: %d unique codes", len(codes_in_timetable))
    return created


def get_subjects(
    session: Session,
    profile: Optional[dict] = None,
) -> List[dict]:
    """
    Courses the student can mark attendance for, filtered by their profile.

    Includes:
      - Core courses whose timetable slot matches the profile's branch + semester
      - Open electives the student opted into (profile.elective_codes)
      - Extra courses (Course.is_extra=True)

    Excludes:
      - Courses from other branches or semesters
      - Postgraduate courses for undergraduate profiles

    The result always tracks the profile: change branch/semester/electives and
    the subject list changes with it. TimetableSlot (not CourseOffering) is used
    because the upload flow populates TimetableSlot but never creates
    CourseOffering rows, so the old normalized-schema path returned an empty
    course set and the fallback path leaked every branch's courses.
    """
    from sqlmodel import select
    from models import Course, TimetableSlot
    from features.exam.parser import (
        branch_family,
        infer_branch_from_course_code,
        is_open_elective,
        is_postgrad_course,
        normalize_branch,
    )

    user_id = profile.get("user_id") if profile else None

    if not profile:
        # No profile: return all courses (admin fallback)
        courses = session.exec(select(Course)).all()
        result = []
        for course in courses:
            summary = get_course_summary(session, course.id, user_id)
            if summary:
                result.append(summary)
        return result

    branch = profile.get("branch")
    semester = profile.get("semester")
    elective_codes = {
        code.strip().upper()
        for code in (profile or {}).get("elective_codes", [])
        if code and code.strip()
    }
    programme = (profile.get("programme") or "").upper()
    is_postgrad_profile = programme in ("MTECH", "ME", "MDES", "PHD")
    profile_branch_norm = normalize_branch(branch) if branch else None
    profile_family = branch_family(branch)

    # ---- 1. Collect relevant course codes from timetable slots ----
    relevant_codes: set[str] = set()

    slots_query = select(TimetableSlot).where(TimetableSlot.semester == semester)
    if user_id is not None:
        slots_query = slots_query.where(
            or_(TimetableSlot.uploaded_by.is_(None), TimetableSlot.uploaded_by == user_id)
        )
    slots = session.exec(slots_query).all()

    for slot in slots:
        code = (slot.course_code or "").strip().upper()
        if not code:
            continue

        # Skip postgraduate courses for undergraduate profiles
        if is_postgrad_course(code) and not is_postgrad_profile:
            continue

        # Open electives: branch-agnostic, only if the student opted in
        if is_open_elective(code):
            if code in elective_codes:
                relevant_codes.add(code)
            continue

        # Core course: match by branch family (consistent with the frontend
        # useProfileCourses filter). A CSE A student sees CSE B papers too.
        slot_branch = slot.branch_or_program
        matched = False
        slot_family = branch_family(slot_branch) if slot_branch else None
        if slot_family and profile_family:
            matched = slot_family == profile_family
        if not matched and profile_family:
            # Fallback: derive branch from the course code prefix itself
            course_branch = infer_branch_from_course_code(code)
            if course_branch and course_branch == profile_family:
                matched = True
        if not matched:
            # Last resort: exact normalized branch match (e.g. shared cells
            # where slot_branch names the precise section). Only when both
            # sides resolve to a real branch - otherwise an unrecognized
            # branch would falsely match another unrecognized one.
            if slot_branch and profile_branch_norm:
                slot_branch_norm = normalize_branch(slot_branch)
                if slot_branch_norm == profile_branch_norm:
                    matched = True

        if matched:
            relevant_codes.add(code)

    # ---- 2. Extra courses (is_extra=True) always appear for this user ----
    for course in session.exec(select(Course).where(Course.is_extra == True)).all():
        code = (course.code or "").strip().upper()
        if code:
            relevant_codes.add(code)

    # ---- 3. Elected electives always appear ----
    for code in elective_codes:
        relevant_codes.add(code)

    # ---- 4. Build summaries for the relevant courses ----
    result: List[dict] = []
    # Build a code -> instructor map from timetable slots so each subject
    # carries its teacher name. Look at ALL slots for the semester (not just
    # branch-filtered ones) so a course's instructor is found even when the
    # row is listed under a different section of the same branch.
    instructor_map: Dict[str, str] = {}
    instructor_query = select(TimetableSlot)
    if user_id is not None:
        instructor_query = instructor_query.where(
            or_(TimetableSlot.uploaded_by.is_(None), TimetableSlot.uploaded_by == user_id)
        )
    all_slots = session.exec(instructor_query).all()
    for slot in all_slots:
        code = (slot.course_code or "").strip().upper()
        inst = (slot.instructor or "").strip()
        if code and inst and inst.upper() not in ("LAB", "VF", "STAFF", "TBA"):
            instructor_map.setdefault(code, inst)
    # Also fall back to the Course table's instructor field.
    course_instructor_map: Dict[str, str] = {}
    for code in sorted(relevant_codes):
        course = session.exec(select(Course).where(Course.code == code)).first()
        if course and (course.instructor or "").strip():
            course_instructor_map[code] = course.instructor.strip()
    for code in sorted(relevant_codes):
        course = session.exec(select(Course).where(Course.code == code)).first()
        if course:
            summary = get_course_summary(session, course.id, user_id)
            if summary:
                # Prefer timetable-slot instructor, fall back to course instructor.
                summary["instructor"] = (
                    instructor_map.get(code)
                    or course_instructor_map.get(code)
                    or ""
                )
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

    total_held = present + absent
    pct = calculate_percentage(present, absent) if total_held > 0 else None

    return {
        "course_id": course.id,
        "course_code": course.code,
        "course_name": course.name,
        "instructor": course.instructor,
        "present": present,
        "absent": absent,
        "cancelled": cancelled,
        "total_held": total_held,
        "percentage": pct,
        "has_records": total_held > 0,
        "status": get_status(pct) if pct is not None else "No records",
        "can_miss": classes_can_miss(present, absent),
        "must_attend": classes_to_attend(present, absent),
    }


def get_overall_summary(session: Session, profile: Optional[dict] = None) -> dict:
    """
    Overall attendance summary.

    When a profile is supplied the totals cover only that student's subjects, so
    a shared database does not mix in other branches' courses.
    """
    user_id = profile.get("user_id") if profile else None
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
    total_held = total_present + total_absent
    overall_pct = calculate_percentage(total_present, total_absent) if total_held > 0 else None

    return {
        "overall_percentage": overall_pct,
        "overall_status": get_status(overall_pct) if overall_pct is not None else "No records",
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