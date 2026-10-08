"""Schedule service: live schedule logic based on system time and user profile."""
import logging
from datetime import datetime, time
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from zoneinfo import ZoneInfo

from core.config import settings, DAY_TO_INT
from models import TimetableSlot, UserProfile, Course

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


def get_user_profile(session: Session) -> UserProfile:
    """Get or create user profile."""
    profile = session.get(UserProfile, 1)
    if not profile:
        profile = UserProfile(id=1, semester=1, branch="CSE", elective_codes=[])
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def get_relevant_slots(session: Session, profile: UserProfile) -> List[TimetableSlot]:
    """
    Get timetable slots relevant to the user:
    - Same semester
    - Same branch OR branch matches user's branch
    - Elective courses the user selected
    - Extra courses (is_extra=True)
    """
    # Base query: same semester
    query = select(TimetableSlot).where(TimetableSlot.semester == profile.semester)

    slots = session.exec(query).all()

    # Filter by branch/program match or elective or extra
    relevant = []
    elective_set = set(profile.elective_codes)

    # Get extra course codes
    extra_courses = session.exec(select(Course).where(Course.is_extra == True)).all()
    extra_codes = {c.code for c in extra_courses}

    for slot in slots:
        # Match branch
        branch_match = (
            slot.branch_or_program.lower() == profile.branch.lower() or
            profile.branch.lower() in slot.branch_or_program.lower() or
            slot.branch_or_program.lower() in profile.branch.lower()
        )

        # Match elective
        elective_match = slot.course_code in elective_set

        # Match extra
        extra_match = slot.course_code in extra_codes

        if branch_match or elective_match or extra_match:
            relevant.append(slot)

    return relevant


def get_current_and_next_class(session: Session) -> Dict[str, Any]:
    """
    Returns current class (if any) and next class based on system time.
    """
    now = get_now()
    current_day = get_current_day()
    current_time = get_current_time()

    profile = get_user_profile(session)
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