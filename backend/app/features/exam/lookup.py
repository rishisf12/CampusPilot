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
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlmodel import Session, select

from models import ExamSeating, MidSemSchedule
from features.exam.reconcile import align_rows, timetable_slots
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


def owner_scope(model, owner_id: Optional[int]):
    """
    Where clause scoping exam rows to one account's view.

    Rows an individual uploaded live in their account; everyone reads the
    public (admin-uploaded) rows, ``uploaded_by`` ``NULL``. ``owner_id=None``
    skips scoping entirely - the builder keeps matching the whole store, as
    tests that seed rows directly expect.
    """
    if owner_id is None:
        return None
    return or_(model.uploaded_by.is_(None), model.uploaded_by == owner_id)


def find_candidate_rows(
    session: Session, roll: str, owner_id: Optional[int] = None
) -> List[ExamSeating]:
    """Every stored row whose roll range contains ``roll``."""
    prefix, num = parse_roll(roll)
    query = select(ExamSeating).where(ExamSeating.roll_start_prefix == prefix.upper())
    scope = owner_scope(ExamSeating, owner_id)
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
    scope_schedule = owner_scope(MidSemSchedule, owner_id)
    scope_seating = owner_scope(ExamSeating, owner_id)
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

    # The timetable decides when a paper is; the index says who sits where.
    # A row stored against a slot the timetable contradicts is moved onto the
    # timetable's slot, so the lookup cannot answer with a time the published
    # timetable does not carry.
    align_rows(dicts, timetable_slots(session, owner_id=owner_id))

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

    exams = _dedupe(exams)
    exams.sort(key=lambda e: (e["date"] or "", e["start_time"] or "", e["course_code"] or ""))
    return {
        "roll": roll,
        "exams": exams,
        "profile_filter_applied": profile_filter_applied,
        "rules_used": sorted(set(rules_used)),
    }


def _dedupe(exams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    One paper once.

    The same upload can sit in the store twice - the admin's public copy and
    the copy in one account - and both are in view for that account. They are
    the same paper, so the student should be told once: a repeated card
    reads as two exams, and the second one is usually the one that looks
    wrong.
    """
    seen = set()
    unique: List[Dict[str, Any]] = []
    for exam in exams:
        key = (
            (exam.get("course_code") or "").upper(),
            exam.get("date"),
            exam.get("start_time"),
            (exam.get("room") or "").strip().upper(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(exam)
    return unique


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
    roll: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Resolve the hall for each timetable row.

    The mid-sem timetable PDF lists only date/time/course - sometimes with a
    hall of its own - while the seating index is the document that names the
    hall a roll sits in. Candidate hall rows come from the account's view of
    the index: the public rows plus the reader's own.

    The hall is taken from the *same slot* first - the course, the day and the
    band - so a course that runs in more than one band gets the hall of the
    band it runs in, not the hall of another one.

    When the reader's own roll is given, the block that holds that roll wins:
    that is the reader's hall, and it beats both a hall printed in the
    timetable and a course-wide guess. A reader's own block and the
    timetable's printed hall disagreeing is a question about one student, and
    the seating index is the document about seats.
    """
    if not rows:
        return rows

    codes = {r["course_code"] for r in rows if r.get("course_code")}
    seatings = []
    if codes:
        query = select(ExamSeating).where(ExamSeating.course_code.in_(codes))
        scope = owner_scope(ExamSeating, owner_id)
        if scope is not None:
            query = query.where(scope)
        seatings = session.exec(query).all()

    # course code -> (date, start, end) -> {room: count}
    by_slot: Dict[str, Dict[Tuple[str, str, str], Dict[str, int]]] = {}
    # course code -> date -> {room: count}
    by_date: Dict[str, Dict[str, Dict[str, int]]] = {}
    for seating in seatings:
        if not seating.room or not seating.seating_date:
            continue
        room = seating.room
        slot_key = (
            seating.seating_date.isoformat(),
            seating.start_time.strftime("%H:%M") if seating.start_time else "",
            seating.end_time.strftime("%H:%M") if seating.end_time else "",
        )
        per_slot = by_slot.setdefault(seating.course_code, {}).setdefault(slot_key, {})
        per_slot[room] = per_slot.get(room, 0) + 1
        per_date = by_date.setdefault(seating.course_code, {}).setdefault(
            seating.seating_date.isoformat(), {}
        )
        per_date[room] = per_date.get(room, 0) + 1

    # The reader's own block, when their roll is given: their hall, not a
    # guess. Keyed by the band too, so a course that runs in two bands gives
    # the hall of the band it runs in.
    own: Dict[Tuple[str, str, str, str], str] = {}
    if roll:
        try:
            for seating in find_candidate_rows(session, roll, owner_id=owner_id):
                if not seating.room or not seating.seating_date:
                    continue
                key = (
                    seating.course_code,
                    seating.seating_date.isoformat(),
                    seating.start_time.strftime("%H:%M") if seating.start_time else "",
                    seating.end_time.strftime("%H:%M") if seating.end_time else "",
                )
                own.setdefault(key, seating.room)
        except ValueError:
            own = {}

    for row in rows:
        course = row.get("course_code")
        if not course:
            continue
        slots = by_slot.get(course) or {}
        slot_key = (
            row.get("schedule_date") or "",
            row.get("start_time") or "",
            row.get("end_time") or "",
        )
        # The reader's own block in this band: their hall, whatever the
        # timetable printed and whatever the course-wide guess would be.
        own_room = own.get((course, slot_key[0], slot_key[1], slot_key[2]))
        if own_room:
            row["room"] = own_room
            continue
        if row.get("room"):
            continue
        # The hall of that exact band, else the hall of that day, else the
        # course's commonest hall.
        counts = slots.get(slot_key)
        if not counts:
            counts = (by_date.get(course) or {}).get(row.get("schedule_date"))
        if not counts:
            merged: Counter = Counter()
            for per_slot in slots.values():
                merged.update(per_slot)
            counts = dict(merged)
        if not counts:
            continue
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