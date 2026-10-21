"""The exam papers an account sits.

The exam timetable screen and the roll lookup show the same list, because a
student must never be told two different things about the same exam: the
timetable screen says *what* they sit, the lookup says *where* they sit. The
list is built once, here, and both read it - so the two cannot drift apart.

Where the list comes from:

- the **exam timetable** says which paper is on which day and in which band;
- the account's **profile** says which of those papers are theirs (their
  branch, their semester, the electives they opted into);
- the **seating index** says which hall the roll sits in.

The timetable is the published document, so it decides the slot; the index
supplies the hall (see :mod:`features.exam.reconcile`).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from features.attendance.service import get_subjects, sync_courses_from_timetable
from features.exam.lookup import (
    fill_rooms_from_seating,
    find_candidate_rows,
    owner_scope,
)
from features.exam.parser import split_course_codes
from models import MidSemSchedule

logger = logging.getLogger(__name__)


def student_course_map(
    session: Session, profile_filter: Dict[str, Any]
) -> Dict[str, str]:
    """
    The courses the account's profile lists, as ``code -> instructor``.

    The Profile/Subjects screen builds its list with
    ``sync_courses_from_timetable`` plus ``get_subjects`` - branch family and
    semester matching for core courses, opted-in open electives, extra courses
    and a resolved instructor. The exam timetable intersects against that very
    list so all three views agree on what the student attends; a profile with
    no subjects therefore yields an empty exam list rather than the old
    branch-wide one.
    """
    sync_courses_from_timetable(session)
    subjects = get_subjects(session, profile_filter)
    by_code: Dict[str, str] = {}
    for subject in subjects:
        code = (subject.get("course_code") or "").strip().upper()
        if not code:
            continue
        instructor = (subject.get("instructor") or "").strip()
        if code not in by_code:
            by_code[code] = instructor
    return by_code


def student_papers(
    session: Session,
    profile_filter: Dict[str, Any],
    owner_id: Optional[int] = None,
    roll: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    The exam papers the account sits, with the hall each one is in.

    The papers come from the exam timetable, narrowed to the courses the
    profile's subjects give the student. The timetable PDF has no hall
    column, so the hall is borrowed from the seating index - the block
    holding the account's own roll when there is one, since that is the
    student's own hall rather than a course-wide guess.
    """
    study = student_course_map(session, profile_filter)
    if not study:
        return []

    stored = session.exec(
        select(MidSemSchedule).where(owner_scope(MidSemSchedule, owner_id))
    ).all()
    rows: List[Dict[str, Any]] = []
    for item in stored:
        codes = split_course_codes(item.course_code or "")
        mine = next((c for c in codes if c.upper() in study), None)
        if mine is None:
            continue
        rows.append(
            {
                "id": item.id,
                "schedule_date": (
                    item.schedule_date.isoformat() if item.schedule_date else None
                ),
                "day": item.schedule_date.strftime("%A") if item.schedule_date else None,
                "start_time": item.start_time.strftime("%H:%M") if item.start_time else None,
                "end_time": item.end_time.strftime("%H:%M") if item.end_time else None,
                "course_code": item.course_code,
                "room": item.room,
                "branch": item.branch,
                "semester": item.semester,
                "is_extra": bool(
                    item.group and str(item.group).upper().startswith("OE")
                ),
                "instructor": study[mine.upper()],
            }
        )

    fill_rooms_from_seating(session, rows, owner_id=owner_id, roll=roll)
    return rows


def _same_slot(row: Any, paper: Dict[str, Any]) -> bool:
    """Does a seating row sit in the band this paper runs in?"""
    date = paper.get("schedule_date")
    if date and row.seating_date and row.seating_date.isoformat() != date:
        return False
    start = paper.get("start_time")
    if start and row.start_time and row.start_time.strftime("%H:%M") != start:
        return False
    end = paper.get("end_time")
    if end and row.end_time and row.end_time.strftime("%H:%M") != end:
        return False
    return True


def papers_for_roll(
    session: Session,
    roll: str,
    papers: List[Dict[str, Any]],
    owner_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    The account's papers, with the hall the given roll sits in for each.

    The seating index is the document that names the hall, and the roll says
    which block the student is in: the block that holds the roll is the one
    whose hall is the answer. A paper the index has no block for keeps the
    hall the timetable borrowed, so a paper is never dropped because the
    index is thin - a missing hall is better than a missing exam.
    """
    candidates = find_candidate_rows(session, roll, owner_id=owner_id)

    exams: List[Dict[str, Any]] = []
    for paper in papers:
        codes = {
            code.upper() for code in split_course_codes(paper.get("course_code") or "")
        }
        block = None
        for row in candidates:
            if (row.course_code or "").upper() not in codes:
                continue
            if not _same_slot(row, paper):
                continue
            block = row
            break
        exams.append(
            {
                "seating_id": block.id if block is not None else None,
                "course_code": paper.get("course_code"),
                "date": paper.get("schedule_date"),
                "schedule_date": paper.get("schedule_date"),
                "day": paper.get("day"),
                "start_time": paper.get("start_time"),
                "end_time": paper.get("end_time"),
                "room": (block.room if block is not None else paper.get("room")) or "",
                "branch": paper.get("branch"),
                "semester": paper.get("semester"),
                "instructor": paper.get("instructor"),
                "source": "seating_index" if block is not None else "timetable",
                "rule": 2,
                "is_extra": bool(paper.get("is_extra")),
            }
        )

    exams.sort(
        key=lambda e: (e["date"] or "", e["start_time"] or "", e["course_code"] or "")
    )
    return exams
