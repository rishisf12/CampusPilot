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

from sqlalchemy import or_
from sqlmodel import Session, select

from models import ExamSeating, MidSemSchedule
from features.exam.parser import (
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


def _account_scope(owner_id: Optional[int]):
    """
    Where clause scoping seating rows to one account's view.

    Rows an individual uploaded live in their account; everyone reads the
    public (admin-uploaded) rows, ``uploaded_by`` ``NULL``. ``owner_id=None``
    skips scoping entirely - the builder keeps matching the whole store, as
    tests that seed rows directly expect.
    """
    if owner_id is None:
        return None
    return or_(ExamSeating.uploaded_by.is_(None), ExamSeating.uploaded_by == owner_id)


def find_candidate_rows(
    session: Session, roll: str, owner_id: Optional[int] = None
) -> List[ExamSeating]:
    """Every stored row whose roll range contains ``roll``."""
    prefix, num = parse_roll(roll)
    query = select(ExamSeating).where(ExamSeating.roll_start_prefix == prefix.upper())
    scope = _account_scope(owner_id)
    if scope is not None:
        query = query.where(scope)
    rows = session.exec(query).all()
    return [row for row in rows if row.roll_start_num <= num <= row.roll_end_num]


def estimate_extra_room(
    session: Session,
    row: ExamSeating,
    profile: Optional[Dict[str, Any]] = None,
    owner_id: Optional[int] = None,
) -> str:
    """
    Rule 3 fallback: estimate the hall for a shared/extra course.

    Preference order: the mid-sem timetable entry for the same course, then the
    most common hall among rows sharing the student's branch in the same slot.
    Both sources are scoped to the account doing the lookup.
    """
    course_code = (row.course_code or "").upper()
    scope_schedule = _account_scope(owner_id)
    scope_seating = _account_scope(owner_id)
    if course_code:
        query = select(MidSemSchedule).where(MidSemSchedule.course_code == course_code)
        if scope_schedule is not None:
            query = query.where(scope_schedule)
        schedules = session.exec(query).all()
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
    query = select(ExamSeating).where(
        ExamSeating.seating_date == row.seating_date,
        ExamSeating.start_time == row.start_time,
    )
    if scope_seating is not None:
        query = query.where(scope_seating)
    slots = session.exec(query).all()
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
    owner_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Resolve an exam schedule for ``roll``.

    Returns the exams for the roll plus which rule produced each row, so the UI
    can show exact matches and estimated halls differently. Rows read belong to
    the public index plus ``owner_id``'s account; ``None`` reads everything,
    which is for direct service use, never the API.
    """
    roll = roll.strip().upper()
    candidates = find_candidate_rows(session, roll, owner_id=owner_id)
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
        room = estimate_extra_room(session, _restore_obj(d), profile, owner_id=owner_id)
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
    Rows missing either bound are never continuous.
    """
    start = row.get("roll_start_num")
    end = row.get("roll_end_num")
    if start is None or end is None:
        return False
    return 0 <= (end - start) <= 400


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


def fill_rooms_from_seating(
    session: Session,
    rows: List[Dict[str, Any]],
    owner_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fill in rooms for timetable rows that have none.

    The mid-sem timetable PDF lists only date/time/course, while the seating
    index is the document that names the hall.  Matching on course code and date
    therefore gives each exam its room without a second upload step. Candidate
    hall rows come from the account's view of the index: the public rows plus
    the reader's own.
    """
    missing = [r for r in rows if not r.get("room") and r.get("course_code")]
    if not missing:
        return rows

    codes = {r["course_code"] for r in missing}
    query = select(ExamSeating).where(ExamSeating.course_code.in_(codes))
    scope = _account_scope(owner_id)
    if scope is not None:
        query = query.where(scope)
    seatings = session.exec(query).all()

    # course code -> date -> {room: count}
    by_course: Dict[str, Dict[str, Dict[str, int]]] = {}
    for seating in seatings:
        if not seating.room or not seating.seating_date:
            continue
        per_date = by_course.setdefault(seating.course_code, {})
        per_date.setdefault(seating.seating_date.isoformat(), {})
        counts = per_date[seating.seating_date.isoformat()]
        counts[seating.room] = counts.get(seating.room, 0) + 1

    for row in missing:
        per_date = by_course.get(row["course_code"])
        if not per_date:
            continue
        # Prefer the hall used on the same date; fall back to the most common one.
        counts = per_date.get(row.get("schedule_date")) or max(
            per_date.values(), key=lambda c: max(c.values())
        )
        row["room"] = max(counts.items(), key=lambda kv: kv[1])[0]
    return rows


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