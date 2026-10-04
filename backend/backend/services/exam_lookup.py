"""
Roll-number exam lookup.

Implements the three agreed rules, in order:

1. **Profile sync filter** - rows are filtered against the student's branch,
   semester and elective codes so a lookup only shows papers that are theirs.
2. **Continuous roll range -> exact room** - regular papers list an unbroken
   ``start..end`` roll range, so a matching row yields the exact hall.
3. **Extra courses -> filter by profile extras, then estimate the room** -
   open electives are shared across branches.  They are shown only when the
   student opted into that elective code; if the index carries no hall the room
   is estimated from the timetable or from sibling rows in the same slot.
"""
import logging
from collections import Counter
from datetime import date as date_type
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from models import ExamSeating, MidSemSchedule
from services.exam_parser import (
    branch_family,
    exam_row_visible,
    is_open_elective,
    parse_roll,
)

logger = logging.getLogger(__name__)


def _row_to_dict(row: ExamSeating) -> Dict[str, Any]:
    """Normalise a stored seating row into a plain dict for filtering."""
    return {
        "id": row.id,
        "roll_start_prefix": row.roll_start_prefix,
        "roll_start_num": row.roll_start_num,
        "roll_end_num": row.roll_end_num,
        "room": row.room,
        "seating_date": row.seating_date,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "course_code": row.course_code,
        "branch": row.branch,
        "semester": row.semester,
        "is_extra": bool(row.is_extra),
    }


def find_candidate_rows(session: Session, roll: str) -> List[ExamSeating]:
    """Every stored row whose roll range contains ``roll``."""
    prefix, num = parse_roll(roll)
    rows = session.exec(
        select(ExamSeating).where(ExamSeating.roll_start_prefix == prefix.upper())
    ).all()
    return [row for row in rows if row.roll_start_num <= num <= row.roll_end_num]


def estimate_extra_room(
    session: Session,
    row: ExamSeating,
    profile: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Rule 3 fallback: estimate the hall for a shared/extra course.

    Preference order: the mid-sem timetable entry for the same course, then the
    most common hall among rows sharing the student's branch in the same slot.
    """
    course_code = (row.course_code or "").upper()
    if course_code:
        schedules = session.exec(
            select(MidSemSchedule).where(MidSemSchedule.course_code == course_code)
        ).all()
        if row.seating_date:
            same_day = [s for s in schedules if s.schedule_date == row.seating_date]
        else:
            same_day = schedules
        for schedule in same_day:
            if schedule.room:
                return schedule.room
        for schedule in schedules:
            if schedule.room:
                return schedule.room

    # Fall back to the modal hall for this branch in this slot.
    slots = session.exec(
        select(ExamSeating).where(
            ExamSeating.seating_date == row.seating_date,
            ExamSeating.start_time == row.start_time,
        )
    ).all()
    wanted_family = branch_family((profile or {}).get("branch"))
    matching = [
        s.room
        for s in slots
        if s.room and (not wanted_family or branch_family(s.branch) == wanted_family)
    ]
    if matching:
        return Counter(matching).most_common(1)[0][0]
    return row.room or ""


def lookup_roll(
    session: Session,
    roll: str,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve an exam schedule for ``roll``.

    Returns the exams for the roll plus which rule produced each row, so the UI
    can show exact matches and estimated halls differently.
    """
    roll = roll.strip().upper()
    candidates = find_candidate_rows(session, roll)
    if not candidates:
        return {"roll": roll, "exams": [], "profile_filter_applied": False, "rules_used": []}

    dicts = [_row_to_dict(row) for row in candidates]
    extras = list(profile.get("elective_codes") or []) if profile else []

    # --- Rule 1: keep the filter in sync with the profile -------------------
    visible = [d for d in dicts if exam_row_visible(d, profile, extras)]
    profile_filter_applied = bool(visible) and len(visible) < len(dicts)
    working = visible or dicts

    exams: List[Dict[str, Any]] = []
    rules_used: List[int] = []

    # --- Rule 2: continuous ranges give an exact hall -----------------------
    regular_rows = [
        d for d in working if not d["is_extra"] and is_continuous_range_dict(d)
    ]

    # --- Rule 3: extra courses, filtered by opted-in electives ---------------
    extra_rows = [d for d in working if d["is_extra"] or is_open_elective(d["course_code"])]

    for d in regular_rows:
        exams.append(_build_result_dict(d, d["room"], "seating_index", 2))
        rules_used.append(2)

    for d in extra_rows:
        if extras and d["course_code"] not in {c.upper() for c in extras}:
            continue  # elective the student did not opt into
        room = estimate_extra_room(session, _restore_obj(d), profile)
        exams.append(_build_result_dict(d, room, "elective", 3))
        rules_used.append(3)

    if not exams:
        # Nothing survived filtering - fall back to every raw match so the
        # student still sees where their roll sits.
        for d in dicts:
            exams.append(_build_result_dict(d, d["room"], "seating_index", 2))
        profile_filter_applied = False
        rules_used = [2]

    exams.sort(key=lambda e: (e["date"] or "", e["start_time"] or "", e["course_code"] or ""))
    return {
        "roll": roll,
        "exams": exams,
        "profile_filter_applied": profile_filter_applied,
        "rules_used": sorted(set(rules_used)),
    }


def is_continuous_range_dict(row: Dict[str, Any]) -> bool:
    """
    True when the row describes an unbroken roll range (rule 2).

    A single-roll row (``start == end``) still counts as a range, but a span
    wider than 400 students is treated as a scattered list rather than a range.
    """
    span = (row.get("roll_end_num") or 0) - (row.get("roll_start_num") or 0)
    return 0 <= span <= 400


def _build_result_dict(
    row: Dict[str, Any],
    room: str,
    source: str,
    rule: int,
) -> Dict[str, Any]:
    exam_date = row.get("seating_date")
    start = row.get("start_time")
    end = row.get("end_time")
    return {
        "seating_id": row.get("id"),
        "course_code": row.get("course_code"),
        "date": exam_date.isoformat() if isinstance(exam_date, date_type) else None,
        "day": exam_date.strftime("%A") if isinstance(exam_date, date_type) else None,
        "start_time": start.strftime("%H:%M") if start else None,
        "end_time": end.strftime("%H:%M") if end else None,
        "room": room,
        "branch": row.get("branch"),
        "semester": row.get("semester"),
        "source": source,
        "rule": rule,
        "is_extra": bool(row.get("is_extra")),
    }


def _restore_obj(row: Dict[str, Any]) -> ExamSeating:
    """Rebuild a transient (unsaved) ORM object from a row dict."""
    return ExamSeating(**row)


def lookup_roll_quick(session: Session, roll: str) -> List[Dict[str, Any]]:
    """
    Quick lookup used by the Exam page: no profile filter, minimal fields.

    Deliberately passes ``profile=None`` so every roll range in the index is
    considered, and returns only date, room and course code.
    """
    result = lookup_roll(session, roll, profile=None)
    return [
        {"date": exam["date"], "room": exam["room"], "course_code": exam["course_code"]}
        for exam in result["exams"]
    ]