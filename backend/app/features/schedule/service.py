"""Schedule service: live schedule logic based on system time and user profile."""
import logging
from datetime import datetime, time
from typing import List, Optional, Dict, Any
from sqlalchemy import or_
from sqlmodel import Session, select
from zoneinfo import ZoneInfo

from core.config import settings, DAY_TO_INT
from models import TimetableSlot, UserProfile, Course, User

logger = logging.getLogger(__name__)

# Timezone for server clock
TZ = ZoneInfo(settings.timezone)


def get_now() -> datetime:
    """Current server time in configured timezone."""
    return datetime.now(TZ)


def get_current_day() -> str:
    """Current day as 'Mon', 'Tue', etc."""
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][get_now().weekday()]


def get_current_time() -> time:
    """Current time component."""
    return get_now().time()


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def minutes_to_time(m: int) -> time:
    h = m // 60
    mi = m % 60
    return time(h, mi)


def is_time_between(check: time, start: time, end: time) -> bool:
    """Check if check time is in [start, end) - start inclusive, end exclusive."""
    return time_to_minutes(start) <= time_to_minutes(check) < time_to_minutes(end)


def get_user_profile(session: Session, user: User) -> UserProfile:
    """Get or create user profile for the given user."""
    # The profile lives behind one canonical owner so branch/branch-id handling
    # stays in one place.
    from features.profile.service import get_profile_for_user

    return get_profile_for_user(session, user)


def get_relevant_slots(session: Session, profile: UserProfile) -> List[TimetableSlot]:
    """
    Get timetable slots relevant to the user:
    - Same semester
    - Matching branch (resolved from the profile's branch)
    - Elective courses the user selected (NOT branch-specific)
    - Extra courses (is_extra=True)
    - Postgraduate courses only for postgraduate programmes
    """
    from features.profile.service import profile_to_filter
    from features.exam.parser import branch_family, is_open_elective, is_postgrad_course, normalize_branch

    filters = profile_to_filter(profile, session)
    profile_branch = filters.get("branch")
    profile_family = branch_family(filters.get("branch"))
    profile_programme = (filters.get("programme") or "").upper()

    # Base query: same semester, scoped to public slots plus the user's own
    # personal uploads so nobody sees another individual's timetable.
    query = select(TimetableSlot).where(TimetableSlot.semester == profile.semester)
    if profile.user_id is not None:
        query = query.where(
            or_(TimetableSlot.uploaded_by.is_(None), TimetableSlot.uploaded_by == profile.user_id)
        )

    slots = session.exec(query).all()

    # Filter by branch/program match or elective or extra
    relevant = []
    elective_set = set(profile.elective_codes or [])

    # Get extra course codes
    extra_courses = session.exec(select(Course).where(Course.is_extra == True)).all()
    extra_codes = {c.code for c in extra_courses}

    for slot in slots:
        code = slot.course_code
        
        # Check if this is a postgraduate course (MTech/ME)
        if is_postgrad_course(code):
            # Only show postgraduate courses for postgraduate programmes (MTech, ME, MDes, PhD)
            if profile_programme not in ("MTECH", "ME", "MDES", "PHD"):
                continue  # Skip postgrad course for UG students
        
        # Check if this is an open elective (OE prefix)
        if is_open_elective(code):
            # Electives are NOT branch-specific — only show if student opted in
            elective_match = code in elective_set
            branch_match = elective_match  # Only show if opted in
        else:
            # For core courses, use the slot's branch_or_program directly
            # The timetable has separate entries for CSE-A and CSE-B with different branch_or_program values
            slot_branch = slot.branch_or_program
            if slot_branch:
                # Normalize both for comparison (e.g., "CSE-A" vs "CSE A")
                slot_branch_norm = normalize_branch(slot_branch)
                profile_branch_norm = normalize_branch(profile.branch) if profile.branch else None
                branch_match = (slot_branch_norm == profile_branch_norm)
            else:
                # Fallback: derive from course code prefix
                from features.exam.parser import infer_branch_from_course_code
                course_branch = infer_branch_from_course_code(code)
                profile_family = branch_family(filters.get("branch"))
                branch_match = course_branch == profile_family
            elective_match = False  # Not an elective

        # Match extra
        extra_match = code in extra_codes

        if branch_match or elective_match or extra_match:
            relevant.append(slot)

    return relevant


def get_current_and_next_class(session: Session, user: User) -> Dict[str, Any]:
    """
    Returns current class (if any) and next class based on system time.
    """
    now = get_now()
    current_day = get_current_day()
    current_time = get_current_time()

    profile = get_user_profile(session, user)
    relevant_slots = get_relevant_slots(session, profile)

    # Filter to today's slots
    today_slots = [s for s in relevant_slots if s.day == current_day]

    # Sort by start_time
    today_slots.sort(key=lambda s: time_to_minutes(s.start_time))

    current_class = None
    next_class = None

    for slot in today_slots:
        if is_time_between(current_time, slot.start_time, slot.end_time):
            current_class = slot
        elif (
            time_to_minutes(slot.start_time) > time_to_minutes(current_time)
            and next_class is None
        ):
            next_class = slot

    # If no next class today, check tomorrow
    if next_class is None:
        tomorrow_idx = (DAY_TO_INT[current_day] + 1) % 7
        tomorrow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][tomorrow_idx]
        tomorrow_slots = [s for s in relevant_slots if s.day == tomorrow]
        tomorrow_slots.sort(key=lambda s: time_to_minutes(s.start_time))
        if tomorrow_slots:
            next_class = tomorrow_slots[0]

    def slot_to_dict(slot: Optional[TimetableSlot]) -> Optional[Dict]:
        if not slot:
            return None
        # Course is looked up by code, not id
        course_obj = session.exec(select(Course).where(Course.code == slot.course_code)).first()
        return {
            "course_code": slot.course_code,
            "course_name": course_obj.name if course_obj else slot.course_code,
            "instructor": slot.instructor,
            "room": slot.room,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "day": slot.day,
            "branch_or_program": slot.branch_or_program,
        }

    # Check if within college hours
    # The hours live as module-level constants in config, not on `settings`.
    college_start = time(COLLEGE_START_HOUR, 0)
    college_end = time(COLLEGE_END_HOUR, 0)

    # Handle lunch break
    lunch_start = time(LUNCH_START_HOUR, 0)
    lunch_end = time(LUNCH_END_HOUR, 0)
    in_lunch = is_time_between(current_time, lunch_start, lunch_end)

    before_hours = time_to_minutes(current_time) < time_to_minutes(college_start)
    after_hours = time_to_minutes(current_time) >= time_to_minutes(college_end)

    message = None
    if before_hours:
        message = f"College hasn't started yet (starts at {college_start.strftime('%H:%M')})"
    elif after_hours:
        message = f"College hours ended (ends at {college_end.strftime('%H:%M')})"
    elif in_lunch:
        message = "Lunch break"
    elif not current_class and not next_class:
        message = "No classes scheduled right now"

    return {
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "current_day": current_day,
        "current_class": slot_to_dict(current_class),
        "next_class": slot_to_dict(next_class),
        "message": message,
        "in_college_hours": not (before_hours or after_hours),
        "is_lunch": in_lunch,
    }


# Import constants from config
from core.config import COLLEGE_START_HOUR, COLLEGE_END_HOUR, LUNCH_START_HOUR, LUNCH_END_HOUR