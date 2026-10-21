"""Exam API routes: timetable + seating upload, day-grouped lists, roll lookup, PDF."""
import logging
from collections import OrderedDict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import Session, delete, select

from core.database import get_session
from models import ExamSeating, ExamUpload, MidSemSchedule, User
from core.deps import get_current_admin, get_current_user
from core.files import UPLOAD_DIR, save_upload, validate_upload
from features.exam.clash import (
    clash_summary,
    collect_student_exams,
    detect_student_exam_clashes,
)
from features.exam.lookup import lookup_roll
from features.exam.reconcile import align_rows, timetable_slots
from features.exam.service import papers_for_roll, student_papers
from features.exam.parser import (
    exam_row_visible,
    is_open_elective,
    parse_mid_sem_file,
    parse_seating_index_file,
    roll_in_range,
)
from features.exam.pdf import generate_exam_pdf
from features.profile.service import elective_codes, get_profile_for_user, profile_to_filter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Exam"])


def _upload_meta(file: UploadFile) -> tuple[Path, bool]:
    """
    Validate and persist an upload; returns ``(saved_path, is_csv)``.

    Accepts PDF, CSV, and Excel (.xlsx).  Excel is treated like CSV: parsed
    row-by-row rather than as table images.
    """
    validate_upload(file, "exam PDF/CSV/Excel")
    saved_path = save_upload(file, "exam")
    is_csv = saved_path.suffix.lower() == ".csv"
    return saved_path, is_csv


def _is_admin(user: User) -> bool:
    """Whether the signed-in user may upload for everybody."""
    return (user.role or "student") == "admin"


def _upload_owner(user: User) -> Optional[int]:
    """
    Whose data an upload writes.

    An admin's upload carries no owner - it is the public index every account
    reads. An individual's upload is stamped with their id and stays personal.
    """
    return None if _is_admin(user) else user.id


def _delete_scope(model, owner: Optional[int]):
    """
    Where clause clearing exactly one upload scope in ``model``.

    ``owner=None`` targets the public (admin) rows - an admin replacing the
    index must not sweep away what individuals uploaded to their own accounts.
    A user id targets that one account's rows only.
    """
    return model.uploaded_by.is_(None) if owner is None else model.uploaded_by == owner


def _account_scope(model, user: User):
    """
    Where clause reading exam rows in this account.

    Every account sees the public (admin-uploaded) rows plus its own personal
    ones; nobody ever sees another individual's upload. For an admin this
    reduces to the public rows, which is exactly what the admin maintains.
    """
    return or_(model.uploaded_by.is_(None), model.uploaded_by == user.id)


def _record_upload(
    session: Session,
    kind: str,
    saved_path: Path,
    original_name: Optional[str],
    owner: Optional[int],
) -> None:
    """
    Remember which section an uploaded file belongs to, and for whom.

    Only the newest file per section and scope is referenced, so the preview
    always matches the data actually in use in that scope. Older files are left
    on disk rather than deleted: the timetable and seating uploads share a
    filename prefix, so there is no safe way to tell a superseded file from the
    other section's current one.
    """
    session.exec(
        delete(ExamUpload).where(ExamUpload.kind == kind, _delete_scope(ExamUpload, owner))
    )
    session.add(
        ExamUpload(
            kind=kind,
            filename=saved_path.name,
            original_name=original_name,
            size_bytes=saved_path.stat().st_size,
            uploaded_at=datetime.now(),
            uploaded_by=owner,
        )
    )
    session.commit()


# ---------------------------------------------------------------------------
# Seating index upload
# ---------------------------------------------------------------------------

@router.post("/seating/upload")
async def upload_seating_index(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Upload the seating-index PDF/CSV.

    Parses every roll range into ``ExamSeating`` and replaces the previous
    index *for that scope*: an admin refreshes the public index, an individual
    replaces the seating table in their own account.
    """
    owner = _upload_owner(user)
    saved_path, is_csv = _upload_meta(file)

    try:
        result = parse_seating_index_file(saved_path, is_csv=is_csv)
    except Exception as exc:
        logger.exception("Seating index parse failed")
        raise HTTPException(status_code=400, detail=f"Failed to parse seating index: {exc}") from exc

    rows = result["rows"]
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No seating rows found. Check that the PDF is a readable Class room Index.",
        )

    session.exec(delete(ExamSeating).where(_delete_scope(ExamSeating, owner)))
    # The timetable decides when a paper is; the index says who sits where.
    # Aligning the rows as they are stored keeps the index and the timetable
    # telling the same story from the moment the file lands.
    moved = align_rows(rows, timetable_slots(session, owner_id=user.id))
    for row in rows:
        session.add(ExamSeating(uploaded_by=owner, **row))
    session.commit()
    _record_upload(session, "seating", saved_path, file.filename, owner)

    stats = result["stats"]
    logger.info(
        "Seating index stored: %s rows (%s skipped, %s aligned to the timetable)",
        stats["rows_parsed"],
        stats.get("rows_skipped"),
        moved,
    )
    note = "" if owner is None else " (visible only in your account)"
    aligned = (
        f" - {moved} row(s) moved onto the exam timetable's slots"
        if moved
        else ""
    )
    return {
        "message": f"Seating index uploaded: {stats['rows_parsed']} rows parsed{note}{aligned}",
        "rows_inserted": stats["rows_parsed"],
        "rows_skipped": stats.get("rows_skipped", 0),
        "rows_aligned": moved,
    }


@router.post("/upload")
async def upload_exam_seating_legacy(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Backwards-compatible alias of :func:`upload_seating_index`."""
    return await upload_seating_index(file=file, session=session, user=user)


# ---------------------------------------------------------------------------
# Mid-sem timetable upload
# ---------------------------------------------------------------------------

@router.post("/timetable/upload")
async def upload_mid_sem_timetable(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Upload the mid-sem exam timetable PDF/CSV into ``MidSemSchedule``.

    Scope follows the uploader: an admin refreshes the paper list every account
    reads; an individual's upload replaces their own account's copy of it.
    """
    owner = _upload_owner(user)
    saved_path, is_csv = _upload_meta(file)

    try:
        result = parse_mid_sem_file(saved_path, is_csv=is_csv)
    except Exception as exc:
        logger.exception("Mid-sem timetable parse failed")
        raise HTTPException(status_code=400, detail=f"Failed to parse exam timetable: {exc}") from exc

    rows = result["rows"]
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No timetable rows found. Check that the PDF is a readable exam timetable.",
        )

    session.exec(delete(MidSemSchedule).where(_delete_scope(MidSemSchedule, owner)))
    for row in rows:
        session.add(MidSemSchedule(uploaded_by=owner, **row))
    session.commit()
    _record_upload(session, "timetable", saved_path, file.filename, owner)

    logger.info("Mid-sem timetable stored: %s rows", result["stats"]["rows_parsed"])
    note = "" if owner is None else " (visible only in your account)"
    return {
        "message": f"Exam timetable uploaded: {result['stats']['rows_parsed']} rows parsed{note}",
        "rows_inserted": result["stats"]["rows_parsed"],
    }


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def _group_by_day(rows: List[Dict[str, Any]], date_key: str) -> "OrderedDict[str, List[Dict[str, Any]]]":
    """Group rows by ISO date, sorted chronologically."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get(date_key) or "unscheduled", []).append(row)

    ordered: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for key in sorted(grouped, key=lambda k: (k == "unscheduled", k)):
        ordered[key] = sorted(
            grouped[key],
            key=lambda r: (r.get("start_time") or "", r.get("course_code") or ""),
        )
    return ordered


@router.get("/options")
def exam_options(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Branch / semester / course options discovered in the uploaded exam data.

    Aggregates from both the mid-sem timetable (``MidSemSchedule``) and the
    seating index (``ExamSeating``), so profile dropdowns reflect the real
    exam data no matter which section was uploaded. Only this account's view
    counts: the public rows plus whatever the account uploaded itself.
    """
    from features.exam.parser import normalize_branch

    slots = session.exec(
        select(MidSemSchedule).where(_account_scope(MidSemSchedule, user))
    ).all()
    seatings = session.exec(
        select(ExamSeating).where(_account_scope(ExamSeating, user))
    ).all()

    branches: "OrderedDict[str, int]" = OrderedDict()
    for item in list(slots) + list(seatings):
        branch = normalize_branch(getattr(item, "branch", None) or "")
        if branch:
            branches[branch] = branches.get(branch, 0) + 1

    semesters = sorted(
        {item.semester for item in list(slots) + list(seatings) if item.semester}
    )
    courses = sorted(
        {
            (item.course_code or "").upper()
            for item in list(slots) + list(seatings)
            if item.course_code
        }
    )

    return {
        "branches": list(branches),
        "branch_counts": branches,
        "semesters": semesters,
        "courses": courses,
        "total_rows": len(slots) + len(seatings),
    }


@router.get("/timetable")
def list_exam_timetable(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Mid-sem timetable for the signed-in student, grouped by day.

    The profile decides: papers show only for courses the student's subjects
    list gives them - the synced course_code + instructor set the Profile
    screen shows - with the instructor carried onto each row.

    The same list is what the roll lookup answers from, so the two screens
    can never disagree about what the student sits.
    """
    profile = get_profile_for_user(session, user)
    profile_filter = profile_to_filter(profile, session)

    # The papers come from the timetable, narrowed to the student's courses;
    # the hall is borrowed from the seating index (the timetable PDF has no
    # hall column) - the block holding the student's own roll when there is
    # one, since that is their hall rather than a course-wide guess.
    rows = student_papers(
        session,
        profile_filter,
        owner_id=user.id,
        roll=(user.roll_number or None),
    )

    grouped = _group_by_day(rows, "schedule_date")
    return {
        "total": len(rows),
        "profile": {"branch": profile_filter["branch"], "semester": profile_filter["semester"]},
        "days": [
            {"date": key, "day": (key if key == "unscheduled" else _weekday(key)), "exams": exams}
            for key, exams in grouped.items()
        ],
    }


def _weekday(iso_date: str) -> Optional[str]:
    from datetime import date as date_type

    try:
        return date_type.fromisoformat(iso_date).strftime("%A")
    except ValueError:
        return None


@router.get("/clashes")
def list_exam_clashes(
    roll: Optional[str] = Query(
        None,
        description="Roll number; defaults to the signed-in student's own roll number",
    ),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Exams the student sits that overlap in date and time.

    This is the "am I double-booked?" check: it compares only the student's own
    papers, so a large exam split across several halls does not register as a
    clash, and an open elective they have not opted into is never counted.
    """
    target = (roll or user.roll_number or "").strip().upper()
    if not target:
        raise HTTPException(
            status_code=400,
            detail="No roll number on the account and none was supplied.",
        )

    profile = profile_to_filter(get_profile_for_user(session, user))
    # The same papers the roll lookup and the timetable screen use: a clash
    # between two papers the student does not sit is not a clash of theirs.
    papers = student_papers(
        session, profile, owner_id=user.id, roll=(user.roll_number or None)
    )
    try:
        clashes = detect_student_exam_clashes(
            session, target, profile, owner_id=user.id, papers=papers or None
        )
        exams = collect_student_exams(
            session, target, profile, owner_id=user.id, papers=papers or None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "roll": target,
        "exam_count": len(exams),
        "exams": exams,
        "clashes": clashes,
        **clash_summary(clashes),
    }


@router.get("/seating")
def list_exam_seating(
    roll: Optional[str] = Query(
        None,
        description="Roll number; defaults to the signed-in student's own roll number",
    ),
    limit: int = Query(200, ge=1, le=2000),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Seating-index rows for the signed-in student, grouped by day.

    Two-layer filtering:

    1. **Profile sync filter** - rows are filtered against the student's branch,
       semester and elective codes so only papers that are theirs appear.
    2. **Roll number range match** - when a roll is asked for (``roll`` query
       parameter), each row's roll range is checked against it and only rows
       whose range contains the roll pass.

    The roll is *not* taken from the profile by default: the index is a
    document that covers many batches, and a student whose roll the index
    does not cover would be shown an empty index and told nothing was
    uploaded. Asking for a roll is how you narrow it to one person.
    """
    profile = get_profile_for_user(session, user)
    profile_filter = profile_to_filter(profile, session)
    extras = elective_codes(profile)

    # Layer 2 target roll: only when one is asked for.
    target_roll = (roll or "").strip().upper() or None

    stored = session.exec(
        select(ExamSeating).where(_account_scope(ExamSeating, user))
    ).all()
    # The index is stored against the slot the document gave it; the timetable
    # is the published one. Showing the timetable's slot keeps this list, the
    # timetable screen and the roll lookup on the same answer even for a file
    # uploaded before the two were reconciled.
    slots = timetable_slots(session, owner_id=user.id)
    rows: List[Dict[str, Any]] = []
    for item in stored:
        row = {
            "id": item.id,
            "seating_date": item.seating_date.isoformat() if item.seating_date else None,
            "roll_start_prefix": item.roll_start_prefix,
            "roll_start_num": item.roll_start_num,
            "roll_end_num": item.roll_end_num,
            "room": item.room,
            "start_time": item.start_time.strftime("%H:%M") if item.start_time else None,
            "end_time": item.end_time.strftime("%H:%M") if item.end_time else None,
            "course_code": item.course_code,
            "branch": item.branch,
            "semester": item.semester,
            "is_extra": bool(item.is_extra),
        }
        aligned = {
            "course_code": row["course_code"],
            "seating_date": item.seating_date,
            "start_time": item.start_time,
            "end_time": item.end_time,
        }
        if align_rows([aligned], slots):
            row["seating_date"] = (
                aligned["seating_date"].isoformat()
                if aligned["seating_date"]
                else None
            )
            row["start_time"] = (
                aligned["start_time"].strftime("%H:%M")
                if aligned["start_time"]
                else None
            )
            row["end_time"] = (
                aligned["end_time"].strftime("%H:%M")
                if aligned["end_time"]
                else None
            )

        # Layer 1: profile sync (branch / semester / electives).
        if not exam_row_visible(row, profile_filter, extras):
            continue

        # Layer 2: roll number range match. Only applies when we have a roll
        # to match against; without one, every profile-visible row is shown.
        if target_roll:
            try:
                if not roll_in_range(
                    target_roll,
                    row["roll_start_prefix"],
                    row["roll_start_num"],
                    row["roll_end_num"],
                ):
                    continue
            except ValueError:
                # Malformed roll in the stored row - skip it.
                continue

        rows.append(row)

    # The same upload can sit in the store twice - the admin's public copy and
    # the copy in one account - and both are in view for that account. They are
    # the same block, so the student should be shown it once.
    rows = _dedupe_seating_rows(rows)

    grouped = _group_by_day(rows, "seating_date")
    return {
        "total": len(rows),
        "profile": {"branch": profile_filter["branch"], "semester": profile_filter["semester"]},
        "roll": target_roll,
        "days": [
            {
                "date": key,
                "day": (key if key == "unscheduled" else _weekday(key)),
                "rooms": exams[:limit],
            }
            for key, exams in grouped.items()
        ],
    }


def _dedupe_seating_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One block once: the same course, hall, band and roll range."""
    seen = set()
    unique: List[Dict[str, Any]] = []
    for row in rows:
        key = (
            row.get("course_code"),
            row.get("seating_date"),
            row.get("start_time"),
            row.get("end_time"),
            (row.get("room") or "").upper(),
            row.get("roll_start_prefix"),
            row.get("roll_start_num"),
            row.get("roll_end_num"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


# ---------------------------------------------------------------------------
# Exam slot listing and editing (mirrors /timetable/slots)
# ---------------------------------------------------------------------------

class ExamSlotEdit(BaseModel):
    schedule_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    room: str | None = None
    course_code: str | None = None
    branch: str | None = None
    semester: int | None = None


class ExamSlotResponse(BaseModel):
    id: int
    schedule_date: str | None = None
    day: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    room: str | None = None
    course_code: str | None = None
    branch: str | None = None
    semester: int | None = None
    is_extra: bool

    class Config:
        from_attributes = True


@router.get("/slots", response_model=List[ExamSlotResponse])
def list_exam_slots(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List exam timetable slots the account may see (ungrouped, for editing)."""
    slots = session.exec(
        select(MidSemSchedule).where(_account_scope(MidSemSchedule, user))
    ).all()
    return [
        ExamSlotResponse(
            id=slot.id,
            schedule_date=slot.schedule_date.isoformat() if slot.schedule_date else None,
            day=slot.schedule_date.strftime("%A") if slot.schedule_date else None,
            start_time=slot.start_time.strftime("%H:%M") if slot.start_time else None,
            end_time=slot.end_time.strftime("%H:%M") if slot.end_time else None,
            room=slot.room,
            course_code=slot.course_code,
            branch=slot.branch,
            semester=slot.semester,
            is_extra=bool(slot.group and str(slot.group).upper().startswith("OE")),
        )
        for slot in slots
    ]


@router.put("/slot/{slot_id}", response_model=ExamSlotResponse)
def edit_exam_slot(
    slot_id: int,
    payload: ExamSlotEdit,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Edit a single exam timetable slot."""
    slot = session.get(MidSemSchedule, slot_id)
    if not slot or slot.uploaded_by is not None:
        # Personal rows live in one student's account; this endpoint maintains
        # the public timetable, so a personal id is simply not an exam slot
        # here.
        raise HTTPException(status_code=404, detail="Exam slot not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key in ("start_time", "end_time") and value:
            from features.exam.parser import parse_meridiem_time
            parsed = parse_meridiem_time(value)
            if not parsed:
                raise HTTPException(status_code=400, detail=f"Invalid time format: {value}")
            setattr(slot, key, parsed)
        elif key == "schedule_date" and value:
            from features.exam.parser import parse_human_date
            parsed = parse_human_date(value)
            if not parsed:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {value}")
            setattr(slot, key, parsed)
        else:
            setattr(slot, key, value)

    session.add(slot)
    session.commit()
    session.refresh(slot)
    return ExamSlotResponse(
        id=slot.id,
        schedule_date=slot.schedule_date.isoformat() if slot.schedule_date else None,
        day=slot.schedule_date.strftime("%A") if slot.schedule_date else None,
        start_time=slot.start_time.strftime("%H:%M") if slot.start_time else None,
        end_time=slot.end_time.strftime("%H:%M") if slot.end_time else None,
        room=slot.room,
        course_code=slot.course_code,
        branch=slot.branch,
        semester=slot.semester,
        is_extra=bool(slot.group and str(slot.group).upper().startswith("OE")),
    )


# ---------------------------------------------------------------------------
# Roll lookup
# ---------------------------------------------------------------------------

@router.get("/lookup")
def lookup_exam(
    roll: str = Query(..., description="Roll number (e.g., 23BCS100)"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Roll-based exam lookup.

    The papers are the account's own: the same list the Exam Timetable tab
    shows, so the two screens can never disagree about what the student
    sits. The roll decides the hall - the seating index says which block
    that roll is in, and the block names the room.

    A paper the index has no block for keeps the hall the timetable
    borrowed, so a paper is never dropped because the index is thin: a
    missing hall is better than a missing exam.
    """
    roll = roll.strip().upper()

    profile_filter = profile_to_filter(get_profile_for_user(session, user))
    papers = student_papers(
        session, profile_filter, owner_id=user.id, roll=(user.roll_number or None)
    )
    if papers:
        try:
            exams = papers_for_roll(session, roll, papers, owner_id=user.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "roll": roll,
            "exams": exams,
            "profile_filter_applied": True,
            "rules_used": [2],
        }

    # No papers of their own - no profile, no timetable. The seating index
    # alone can answer, so the roll still finds its hall.
    try:
        return lookup_roll(session, roll, None, owner_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/quick-lookup")
def quick_lookup_exam(
    roll: str = Query(..., description="Roll number (e.g., 23BCS100)"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Quick Roll Lookup: only date, room and course code.

    The same answer as ``/exam/lookup``, with the fields trimmed: the
    account's own papers, and the hall the roll sits in for each.
    """
    result = lookup_exam(roll=roll, session=session, user=user)
    exams = [
        {
            "date": exam.get("date"),
            "day": exam.get("day"),
            "room": exam.get("room"),
            "course_code": exam.get("course_code"),
        }
        for exam in result["exams"]
    ]
    return {"roll": result["roll"], "exams": exams}


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

@router.get("/pdf")
def download_exam_pdf(
    roll: str = Query(..., description="Roll number (e.g., 23BCS100)"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Generate a personalised exam timetable PDF for one roll."""
    roll = roll.strip().upper()

    # The same answer the screen shows, so the PDF and the card agree.
    result = lookup_exam(roll=roll, session=session, user=user)

    if not result["exams"]:
        raise HTTPException(
            status_code=404, detail=f"No exam schedule found for roll {roll}"
        )

    pdf_bytes = generate_exam_pdf(
        roll,
        [
            {
                "exam_date": exam["date"],
                "start_time": exam["start_time"],
                "end_time": exam["end_time"],
                "course_code": exam["course_code"],
                "room": exam["room"],
            }
            for exam in result["exams"]
        ],
    )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=exam_timetable_{roll}.pdf"},
    )


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

@router.get("/status")
def exam_status(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Row counts in this account: the public rows plus the account's own."""
    scope_timetable = _account_scope(MidSemSchedule, user)
    scope_seating = _account_scope(ExamSeating, user)
    timetable_rows = len(session.exec(select(MidSemSchedule).where(scope_timetable)).all())
    seating_rows = len(session.exec(select(ExamSeating).where(scope_seating)).all())
    return {
        "timetable_rows": timetable_rows,
        "seating_rows": seating_rows,
        "has_timetable": timetable_rows > 0,
        "has_seating": seating_rows > 0,
    }


UPLOAD_KINDS = {"timetable", "seating"}


def _latest_upload(session: Session, kind: str, user: User) -> Optional[ExamUpload]:
    """The newest file recorded for a section in this account, or ``None``."""
    return session.exec(
        select(ExamUpload)
        .where(ExamUpload.kind == kind, _account_scope(ExamUpload, user))
        .order_by(ExamUpload.id.desc())
    ).first()


def _resolve_upload_path(filename: str) -> Path:
    """
    Resolve a stored filename inside ``uploads/``.

    The name comes from the database, never from the request body, but it is
    still resolved and checked to be inside the upload directory so a stray
    ``..`` can never escape it.
    """
    candidate = (UPLOAD_DIR / Path(filename).name).resolve()
    root = UPLOAD_DIR.resolve()
    if root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid upload path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on the server")
    return candidate


@router.get("/uploads/latest")
def latest_exam_upload(
    kind: str = Query("timetable", description="`timetable` or `seating`"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Metadata for the newest file uploaded to a section in this account, for the
    preview button: the public file or, when this account uploaded one itself,
    whichever landed last.

    Returns ``{"available": false}`` rather than 404 when nothing has been
    uploaded, so the UI can simply hide the button.
    """
    if kind not in UPLOAD_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {sorted(UPLOAD_KINDS)}")

    record = _latest_upload(session, kind, user)
    if record is None:
        return {"available": False, "kind": kind}

    try:
        exists = _resolve_upload_path(record.filename).is_file()
    except HTTPException:
        exists = False

    return {
        "available": exists,
        "kind": kind,
        "filename": record.filename,
        "original_name": record.original_name or record.filename,
        "size_bytes": record.size_bytes,
        "uploaded_at": record.uploaded_at.isoformat() if record.uploaded_at else None,
        "preview_url": f"/exam/uploads/preview?kind={kind}",
    }


@router.get("/uploads/preview")
def preview_exam_upload(
    kind: str = Query("timetable", description="`timetable` or `seating`"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Stream the newest file uploaded to a section in this account, inline."""
    if kind not in UPLOAD_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {sorted(UPLOAD_KINDS)}")

    record = _latest_upload(session, kind, user)
    if record is None:
        raise HTTPException(status_code=404, detail="No file has been uploaded for this section")

    path = _resolve_upload_path(record.filename)
    media_type = "text/csv" if path.suffix.lower() == ".csv" else "application/pdf"
    return FileResponse(
        path,
        media_type=media_type,
        # `inline` so the browser renders it in a tab instead of downloading it.
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.delete("/timetable", status_code=204)
def clear_exam_timetable(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Remove one exam timetable upload.

    An admin clears the public index - the paper list every account reads. An
    individual clears the copy in their own account; nobody else's changes.
    """
    owner = _upload_owner(user)
    session.exec(delete(MidSemSchedule).where(_delete_scope(MidSemSchedule, owner)))
    session.exec(
        delete(ExamUpload).where(
            ExamUpload.kind == "timetable", _delete_scope(ExamUpload, owner)
        )
    )
    session.commit()
    return


@router.delete("/seating", status_code=204)
def clear_exam_seating(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Remove one seating-index upload.

    An admin clears the public seating index; an individual clears their own.
    """
    owner = _upload_owner(user)
    session.exec(delete(ExamSeating).where(_delete_scope(ExamSeating, owner)))
    session.exec(
        delete(ExamUpload).where(
            ExamUpload.kind == "seating", _delete_scope(ExamUpload, owner)
        )
    )
    session.commit()
    return


@router.post("/debug/parse-exam")
async def debug_parse_exam(
    file: UploadFile = File(...),
    kind: str = Query("timetable", description="`timetable` or `seating`"),
    _: User = Depends(get_current_admin),
):
    """Return the raw extraction alongside the parse result, for troubleshooting."""
    if kind not in ("timetable", "seating"):
        raise HTTPException(status_code=400, detail="kind must be 'timetable' or 'seating'")
    validate_upload(file, "exam PDF/CSV/Excel")
    saved_path = save_upload(file, "debug_exam")
    suffix = saved_path.suffix.lower()

    if suffix == ".csv":
        import csv

        with saved_path.open(newline="", encoding="utf-8") as handle:
            raw_rows = list(csv.DictReader(handle))
        parser = parse_mid_sem_file if kind == "timetable" else parse_seating_index_file
        return {
            "file_type": "csv",
            "kind": kind,
            "raw_rows": raw_rows,
            "parsed_result": parser(saved_path, is_csv=True),
        }

    if suffix == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(saved_path, read_only=True)
        sheets_info = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append([str(v) if v is not None else "" for v in row])
            sheets_info[sheet_name] = {"rows": rows[:50], "total_rows": ws.max_row}
        wb.close()
        parser = parse_mid_sem_file if kind == "timetable" else parse_seating_index_file
        return {
            "file_type": "excel",
            "kind": kind,
            "sheets": sheets_info,
            "parsed_result": parser(saved_path),
        }

    # PDF: return raw tables AND raw text
    import pdfplumber

    tables, texts = [], []
    with pdfplumber.open(saved_path) as pdf:
        for index, page in enumerate(pdf.pages):
            for table in page.extract_tables():
                cleaned = [[(cell or "").strip() for cell in row] for row in table]
                tables.append({"page": index + 1, "table": cleaned})
            texts.append({"page": index + 1, "text": page.extract_text() or ""})

    parser = parse_mid_sem_file if kind == "timetable" else parse_seating_index_file
    return {
        "file_type": "pdf",
        "kind": kind,
        "raw_tables": tables,
        "raw_texts": texts,
        "parsed_result": parser(saved_path, is_csv=False),
    }