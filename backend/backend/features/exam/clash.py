"""
Personal exam-clash detection.

The question this answers is narrow and practical: *of the exams I actually sit,
which ones land on the same day at the same time?*  That happens most often when
an extra or back-log course is scheduled against a regular one.

Two things make this non-trivial, and both are handled here:

1. A class-room index lists **every** roll range, so a roll number matches rows
   belonging to other semesters and branches as well - ``23BCS125`` appears in
   the sem-8 ``CS8036`` paper and the sem-1 ``NS1001`` paper.  The student's set
   is therefore taken from :func:`services.exam_lookup.lookup_roll`, i.e. exactly
   the set the Quick Roll Lookup shows, so the clash list can never disagree with
   what the user sees.

2. One exam is often split across several halls, producing several rows for the
   same course and slot.  Those are collapsed into a single exam with a list of
   rooms, because a clash is about the student's *time*, not the hall.

Deliberately **not** a pairwise scan of the whole index: comparing every row
against every other reports thousands of false positives on real data, since one
large exam legitimately repeats a room, a time band and overlapping roll ranges.
"""
import logging
from datetime import time as time_type
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from models import Course
from features.exam.lookup import lookup_roll
from features.exam.parser import is_open_elective

logger = logging.getLogger(__name__)


def declared_course_codes(session: Session, profile: Optional[Dict[str, Any]] = None) -> set:
    """
    Course codes the student has actually opted into.

    Two places record this: electives chosen in the profile (``OE…`` codes) and
    extra/back-log courses created through the profile screen (``Course.is_extra``).
    Both are needed - an undeclared open elective must never be treated as the
    student's paper, or it invents clashes that do not exist.
    """
    codes = {
        str(code).strip().upper()
        for code in (profile or {}).get("elective_codes", [])
        if code and str(code).strip()
    }
    for course in session.exec(select(Course).where(Course.is_extra == True)).all():
        if course.code:
            codes.add(course.code.strip().upper())
    return codes


def _parse_time(value: Optional[str]) -> Optional[int]:
    """``"15:00"`` -> minutes since midnight."""
    if not value:
        return None
    try:
        hour, minute = value.split(":")[:2]
        return int(hour) * 60 + int(minute)
    except (ValueError, AttributeError):
        return None


def collect_student_exams(
    session: Session,
    roll: str,
    profile: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    The student's own exams, de-duplicated per course and time slot.

    Each entry looks like::

        {"course_code": "OE3E33", "date": "2026-09-23",
         "start_time": "15:00", "end_time": "17:00",
         "rooms": ["L-104"], "is_extra": True}

    Open electives and extra courses are kept only when the student has declared
    them, because an index lists every branch's elective papers and they are not
    all the student's.
    """
    result = lookup_roll(session, roll.strip().upper(), profile)
    declared = declared_course_codes(session, profile)

    exams: Dict[tuple, Dict[str, Any]] = {}
    for exam in result.get("exams", []):
        if not exam.get("date"):
            continue
        code = (exam["course_code"] or "").upper()
        shared = bool(exam.get("is_extra")) or is_open_elective(code)
        if shared and code not in declared:
            logger.debug("Skipping undeclared shared course %s for %s", code, roll)
            continue

        key = (code, exam["date"], exam.get("start_time"), exam.get("end_time"))
        entry = exams.get(key)
        if entry is None:
            entry = exams[key] = {
                "course_code": code,
                "date": exam["date"],
                "start_time": exam.get("start_time"),
                "end_time": exam.get("end_time"),
                "rooms": [],
                "is_extra": shared,
            }
        room = exam.get("room")
        if room and room not in entry["rooms"]:
            entry["rooms"].append(room)

    for entry in exams.values():
        entry["rooms"].sort()

    return sorted(
        exams.values(),
        key=lambda e: (e["date"], e["start_time"] or "", e["course_code"]),
    )


def detect_student_exam_clashes(
    session: Session,
    roll: str,
    profile: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Return the student's overlapping exams, grouped by date and time band.

    Each entry describes one busy slot and the courses competing for it::

        {"date": "2026-09-23", "day": "Wednesday",
         "start_time": "15:00", "end_time": "17:00",
         "courses": [{"course_code": "OE3E33", "rooms": ["L-104"]},
                     {"course_code": "HS1001", "rooms": ["L-105"]}]}
    """
    exams = collect_student_exams(session, roll, profile)
    if len(exams) < 2:
        return []

    clashes: List[Dict[str, Any]] = []

    for index, first in enumerate(exams):
        first_start, first_end = _parse_time(first["start_time"]), _parse_time(first["end_time"])
        if first_start is None or first_end is None:
            continue
        for second in exams[index + 1:]:
            if first["date"] != second["date"]:
                continue
            second_start = _parse_time(second["start_time"])
            second_end = _parse_time(second["end_time"])
            if second_start is None or second_end is None:
                continue
            # Half-open comparison: a paper ending at 10:00 does not clash with
            # one starting at 10:00.
            if not (first_start < second_end and second_start < first_end):
                continue
            clashes.append({
                "date": first["date"],
                "day": _weekday(first["date"]),
                "start_time": second["start_time"] if second_start < first_start else first["start_time"],
                "end_time": first["end_time"] if first_end > second_end else second["end_time"],
                "courses": [
                    {"course_code": first["course_code"], "rooms": first["rooms"],
                     "is_extra": first["is_extra"]},
                    {"course_code": second["course_code"], "rooms": second["rooms"],
                     "is_extra": second["is_extra"]},
                ],
            })

    clashes.sort(key=lambda c: (c["date"], c["start_time"]))
    logger.info(
        "Exam clash check for %s: %d exam(s), %d clash(es)",
        roll, len(exams), len(clashes),
    )
    return clashes


def _weekday(iso_date: str) -> Optional[str]:
    from datetime import date as date_type

    try:
        return date_type.fromisoformat(iso_date).strftime("%A")
    except ValueError:
        return None


def clash_summary(clashes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts for the response envelope."""
    return {
        "clash_count": len(clashes),
        "dates_affected": sorted({clash["date"] for clash in clashes}),
        "involves_extra_course": any(
            course["is_extra"]
            for clash in clashes
            for course in clash["courses"]
        ),
    }


# Kept for callers that pass time objects rather than "HH:MM" strings.
def overlaps(a_start: time_type, a_end: time_type, b_start: time_type, b_end: time_type) -> bool:
    """True when two time ranges overlap (start-inclusive, end-exclusive)."""

    def to_minutes(t) -> int:
        return t.hour * 60 + t.minute

    return to_minutes(a_start) < to_minutes(b_end) and to_minutes(b_start) < to_minutes(a_end)