"""Room service: vacant room finder logic."""
import logging
from datetime import time, datetime
from typing import List, Dict, Any
from sqlmodel import Session, select

from core.config import (
    COLLEGE_END_HOUR,
    COLLEGE_START_HOUR,
    DAYS_ORDER,
    LUNCH_END_HOUR,
    LUNCH_START_HOUR,
    settings,
)
from models import TimetableSlot

logger = logging.getLogger(__name__)

# Timezone for server clock
from zoneinfo import ZoneInfo
TZ = ZoneInfo(settings.timezone)


def is_overlapping(start: time, end: time, query_time: time) -> bool:
    """
    Check if a time slot overlaps with a query time.
    Start-inclusive, end-exclusive: [start, end)
    """
    return start <= query_time < end


def get_all_rooms(session: Session) -> List[str]:
    """Get unique list of all rooms from timetable."""
    slots = session.exec(select(TimetableSlot)).all()
    rooms = {slot.room for slot in slots if slot.room}
    return sorted(rooms)


def get_occupied_rooms_at(session: Session, day: str, query_time: time) -> List[Dict[str, Any]]:
    """
    Get rooms occupied at a specific day and time.
    Returns list of {room, course_code, start_time, end_time}.
    """
    slots = session.exec(
        select(TimetableSlot).where(TimetableSlot.day == day)
    ).all()

    occupied = []
    for slot in slots:
        if is_overlapping(slot.start_time, slot.end_time, query_time):
            occupied.append({
                "room": slot.room,
                "course_code": slot.course_code,
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
            })
    return occupied


def get_vacant_rooms(
    session: Session,
    day: str,
    query_time: time
) -> Dict[str, Any]:
    """
    Get vacant and occupied rooms for a given day and time.

    Returns an empty result with ``has_timetable: False`` when no timetable has
    been uploaded yet, instead of raising.
    """
    all_rooms = get_all_rooms(session)
    occupied = get_occupied_rooms_at(session, day, query_time)
    occupied_rooms = {o["room"] for o in occupied}
    vacant = [r for r in all_rooms if r not in occupied_rooms]

    # Determine time window description
    time_window = f"{query_time.strftime('%H:%M')}"

    # Check if within college hours
    college_start = time(COLLEGE_START_HOUR, 0)
    college_end = time(COLLEGE_END_HOUR, 0)
    lunch_start = time(LUNCH_START_HOUR, 0)
    lunch_end = time(LUNCH_END_HOUR, 0)

    in_college_hours = college_start <= query_time < college_end
    in_lunch = lunch_start <= query_time < lunch_end
    is_weekend = day in ("Sat", "Sun")

    message = None
    if not all_rooms:
        message = "No timetable uploaded yet - upload the class timetable to see vacant rooms."
    elif is_weekend:
        message = "Weekend - no regular classes"
    elif not in_college_hours:
        message = f"Outside college hours ({college_start.strftime('%H:%M')}-{college_end.strftime('%H:%M')})"
    elif in_lunch:
        message = "Lunch break"

    return {
        "day": day,
        "time": query_time.strftime("%H:%M"),
        "vacant_rooms": vacant,
        "occupied_rooms": occupied,
        "time_window": time_window,
        "in_college_hours": in_college_hours,
        "is_lunch": in_lunch,
        "is_weekend": is_weekend,
        "has_timetable": bool(all_rooms),
        "message": message,
    }


def get_vacant_rooms_live(session: Session) -> Dict[str, Any]:
    """
    Get vacant rooms right now (live mode).
    Uses server system clock in configured timezone.
    """
    now = datetime.now(TZ)
    day = DAYS_ORDER[now.weekday()]
    query_time = now.time()
    return get_vacant_rooms(session, day, query_time)


def get_vacant_rooms_manual(session: Session, day: str, hour: str) -> Dict[str, Any]:
    """
    Get vacant rooms for a manual day and hour override.
    hour format: "HH:MM" (24h)
    """
    # Validate day
    day = day[:3].capitalize()
    if day not in DAYS_ORDER:
        raise ValueError(f"Invalid day: {day}. Must be one of {DAYS_ORDER}")

    # Parse time
    try:
        h, mi = map(int, hour.split(":"))
        query_time = time(h, mi)
    except Exception:  # noqa: BLE001 - raw query string in, one clear ValueError out
        # from None: the message below already states what was wrong with the
        # input, so chaining the underlying error adds no diagnostic value.
        raise ValueError(f"Invalid time format: {hour}. Use HH:MM (24h)") from None

    return get_vacant_rooms(session, day, query_time)