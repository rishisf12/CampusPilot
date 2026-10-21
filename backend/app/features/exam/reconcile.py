"""
Reconcile the seating index with the exam timetable.

Two documents describe the same exam. The **timetable** says *when* a paper
is - the day, the band it runs in, the course. The **seating index** says
*where* and *who* - the hall, and the roll ranges that sit in it.

They are uploaded separately, so they can disagree: a typo in one, a header
the parser read differently in the other. When they do, the student gets two
answers to one question - the timetable screen says 3 PM, the roll lookup
says 11 AM - and neither looks obviously wrong.

The timetable is the published document, so it decides the slot. The seating
index keeps the roll ranges and the hall. The rule is applied in three
places, so all three views agree:

- as a seating index is uploaded, the rows are aligned as they are stored;
- when a roll is looked up, the answer carries the timetable's slot;
- when the seating index is listed, the rows carry the timetable's slot.

A course the timetable does not mention keeps the slot the index gave it: the
rule never invents an exam, and it never guesses between two real ones.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import time as time_type
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Slot:
    """A paper's place in time: the day, and the band it runs in."""

    date: Optional[date_type]
    start: Optional[time_type]
    end: Optional[time_type]

    def key(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """A comparable key - the slot as strings, for grouping."""
        return (
            self.date.isoformat() if self.date else None,
            self.start.strftime("%H:%M") if self.start else None,
            self.end.strftime("%H:%M") if self.end else None,
        )


def _codes(value: Any) -> List[str]:
    """
    The course codes in a cell.

    A cell may hold several courses ("CS8031/CS8032"), and the batch
    suffixes the parser knows about are dropped. The parser is imported
    lazily so this module stays free of the PDF machinery.
    """
    if not value:
        return []
    from features.exam.parser import split_course_codes

    return [code.upper() for code in split_course_codes(str(value))]


def slots_by_course(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Slot]]:
    """
    The slots the timetable gives each course.

    ``rows`` are timetable rows as dicts with ``course_code``,
    ``schedule_date``, ``start_time`` and ``end_time``. A row with no date
    cannot place anything, so it is skipped.
    """
    slots: Dict[str, List[Slot]] = {}
    for row in rows:
        slot = Slot(
            date=row.get("schedule_date"),
            start=row.get("start_time"),
            end=row.get("end_time"),
        )
        if slot.date is None:
            continue
        for code in _codes(row.get("course_code")):
            known = slots.setdefault(code, [])
            if slot not in known:
                known.append(slot)
    return slots


def resolve_slot(
    slots: Sequence[Slot], own_date: Optional[date_type]
) -> Optional[Slot]:
    """
    The slot a seating row should take for a course.

    The day is the anchor: the exam is the one on that day, and what the two
    documents can disagree about is the *band* it runs in. So the slot is the
    timetable's for that course on that day.

    A course the timetable places in several bands that day is left alone:
    choosing between two real exams would be a guess, and a wrong exam is
    worse than the document's own wording. A course the timetable does not
    mention on that day keeps the slot the index gave it - the rule never
    invents an exam, and never moves a paper to another day, because a
    mid-sem timetable and an end-sem index share course codes and swapping
    one for the other would be a disaster.
    """
    if not slots or own_date is None:
        return None
    same_day = [slot for slot in slots if slot.date == own_date]
    if len(same_day) == 1:
        return same_day[0]
    return None


def align_row(row: Dict[str, Any], slots: Dict[str, List[Slot]]) -> bool:
    """
    Move one seating row onto the timetable's slot for its course.

    ``row`` is a seating row as a dict - ``course_code``, ``seating_date``,
    ``start_time``, ``end_time``. Returns True when the row moved.
    """
    code = (row.get("course_code") or "").strip().upper()
    if not code:
        return False
    slot = resolve_slot(slots.get(code, []), row.get("seating_date"))
    if slot is None:
        return False
    if (
        row.get("seating_date"),
        row.get("start_time"),
        row.get("end_time"),
    ) == (slot.date, slot.start, slot.end):
        return False
    row["seating_date"] = slot.date
    row["start_time"] = slot.start
    row["end_time"] = slot.end
    return True


def align_rows(
    rows: List[Dict[str, Any]], slots: Dict[str, List[Slot]]
) -> int:
    """Align a list of seating rows; returns how many moved."""
    return sum(1 for row in rows if align_row(row, slots))


def timetable_slots(
    session, owner_id: Optional[int] = None
) -> Dict[str, List[Slot]]:
    """
    The slots the timetable gives, as one account sees them.

    Every account reads the public timetable plus its own; nobody reads
    another individual's. ``owner_id=None`` reads the whole store, which is
    for maintenance rather than for the API.
    """
    from sqlalchemy import or_
    from sqlmodel import select

    from models import MidSemSchedule

    query = select(MidSemSchedule)
    if owner_id is not None:
        query = query.where(
            or_(
                MidSemSchedule.uploaded_by.is_(None),
                MidSemSchedule.uploaded_by == owner_id,
            )
        )
    stored = session.exec(query).all()
    return slots_by_course(
        [
            {
                "course_code": row.course_code,
                "schedule_date": row.schedule_date,
                "start_time": row.start_time,
                "end_time": row.end_time,
            }
            for row in stored
        ]
    )


def stored_seating_rows(
    session, owner_id: Optional[int] = None
) -> List[Any]:
    """The stored seating rows an account may read, as ORM objects."""
    from sqlalchemy import or_
    from sqlmodel import select

    from models import ExamSeating

    query = select(ExamSeating)
    if owner_id is not None:
        query = query.where(
            or_(
                ExamSeating.uploaded_by.is_(None),
                ExamSeating.uploaded_by == owner_id,
            )
        )
    return list(session.exec(query).all())


def reconcile_stored(session, owner_id: Optional[int] = None) -> int:
    """
    Move the stored seating rows onto the timetable's slots.

    The repair, for a database that was filled before the rule existed.
    Returns the number of rows that moved.
    """
    slots = timetable_slots(session, owner_id=owner_id)
    if not slots:
        return 0

    moved = 0
    for row in stored_seating_rows(session, owner_id=owner_id):
        as_dict = {
            "course_code": row.course_code,
            "seating_date": row.seating_date,
            "start_time": row.start_time,
            "end_time": row.end_time,
        }
        if not align_row(as_dict, slots):
            continue
        row.seating_date = as_dict["seating_date"]
        row.start_time = as_dict["start_time"]
        row.end_time = as_dict["end_time"]
        session.add(row)
        moved += 1
    if moved:
        session.commit()
    return moved
