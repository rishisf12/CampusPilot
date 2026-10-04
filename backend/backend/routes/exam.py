"""Exam API routes: timetable + seating upload, day-grouped lists, roll lookup, PDF."""
import logging
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session, delete, select

from database import get_session
from models import ExamSeating, MidSemSchedule, User
from routes.deps import get_current_user
from services.exam_lookup import fill_rooms_from_seating, lookup_roll
from services.exam_parser import (
    exam_row_visible,
    parse_mid_sem_file,
    parse_seating_index_file,
)
from services.exam_pdf import generate_exam_pdf
from services.profile_service import elective_codes, get_profile_for_user, profile_to_filter
from utils.file_prompt import save_upload, validate_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Exam"])


def _upload_meta(file: UploadFile) -> tuple[Path, bool]:
    """Validate and persist an upload; returns ``(saved_path, is_csv)``."""
    validate_upload(file, "exam PDF/CSV")
    saved_path = save_upload(file, "exam")
    return saved_path, saved_path.suffix.lower() == ".csv"


# ---------------------------------------------------------------------------
# Seating index upload
# ---------------------------------------------------------------------------

@router.post("/seating/upload")
async def upload_seating_index(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """
    Upload the seating-index PDF/CSV.

    Parses every roll range into ``ExamSeating`` and replaces the previous index.
    """
    saved_path, is_csv = _upload_meta(file)

    try:
        result = parse_seating_index_file(saved_path, is_csv=is_csv)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Seating index parse failed")
        raise HTTPException(status_code=400, detail=f"Failed to parse seating index: {exc}")

    rows = result["rows"]
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No seating rows found. Check that the PDF is a readable Class room Index.",
        )

    session.exec(delete(ExamSeating))
    for row in rows:
        session.add(ExamSeating(**row))
    session.commit()

    stats = result["stats"]
    logger.info("Seating index stored: %s rows (%s skipped)", stats["rows_parsed"], stats.get("rows_skipped"))
    return {
        "message": f"Seating index uploaded: {stats['rows_parsed']} rows parsed",
        "rows_inserted": stats["rows_parsed"],
        "rows_skipped": stats.get("rows_skipped", 0),
    }


@router.post("/upload")
async def upload_exam_seating_legacy(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Backwards-compatible alias of :func:`upload_seating_index`."""
    return await upload_seating_index(file=file, session=session, _=_)


# ---------------------------------------------------------------------------
# Mid-sem timetable upload
# ---------------------------------------------------------------------------

@router.post("/timetable/upload")
async def upload_mid_sem_timetable(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Upload the mid-sem exam timetable PDF/CSV into ``MidSemSchedule``."""
    saved_path, is_csv = _upload_meta(file)

    try:
        result = parse_mid_sem_file(saved_path, is_csv=is_csv)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Mid-sem timetable parse failed")
        raise HTTPException(status_code=400, detail=f"Failed to parse exam timetable: {exc}")

    rows = result["rows"]
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No timetable rows found. Check that the PDF is a readable exam timetable.",
        )

    session.exec(delete(MidSemSchedule))
    for row in rows:
        session.add(MidSemSchedule(**row))
    session.commit()

    logger.info("Mid-sem timetable stored: %s rows", result["stats"]["rows_parsed"])
    return {
        "message": f"Exam timetable uploaded: {result['stats']['rows_parsed']} rows parsed",
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


@router.get("/timetable")
def list_exam_timetable(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Mid-sem timetable for the signed-in student, grouped by day.

    Applies rule 1 of the lookup: rows are filtered by the profile branch,
    semester and elective codes.
    """
    profile = get_profile_for_user(session, user)
    profile_filter = profile_to_filter(profile)
    extras = elective_codes(profile)

    stored = session.exec(select(MidSemSchedule)).all()
    rows: List[Dict[str, Any]] = []
    for item in stored:
        row = {
            "id": item.id,
            "schedule_date": item.schedule_date.isoformat() if item.schedule_date else None,
            "day": item.schedule_date.strftime("%A") if item.schedule_date else None,
            "start_time": item.start_time.strftime("%H:%M") if item.start_time else None,
            "end_time": item.end_time.strftime("%H:%M") if item.end_time else None,
            "course_code": item.course_code,
            "room": item.room,
            "branch": item.branch,
            "semester": item.semester,
            "is_extra": bool(item.group and str(item.group).upper().startswith("OE")),
        }
        if exam_row_visible(row, profile_filter, extras):
            rows.append(row)

    # The timetable PDF has no hall column; borrow rooms from the seating index.
    fill_rooms_from_seating(session, rows)

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


@router.get("/seating")
def list_exam_seating(
    limit: int = Query(200, ge=1, le=2000),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Seating-index rows for the signed-in student, grouped by day."""
    profile = get_profile_for_user(session, user)
    profile_filter = profile_to_filter(profile)
    extras = elective_codes(profile)

    stored = session.exec(select(ExamSeating)).all()
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
        if exam_row_visible(row, profile_filter, extras):
            rows.append(row)

    grouped = _group_by_day(rows, "seating_date")
    return {
        "total": len(rows),
        "profile": {"branch": profile_filter["branch"], "semester": profile_filter["semester"]},
        "days": [
            {
                "date": key,
                "day": (key if key == "unscheduled" else _weekday(key)),
                "rooms": exams[:limit],
            }
            for key, exams in grouped.items()
        ],
    }


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

    When the roll matches the signed-in student the three-rule profile filter is
    applied; otherwise every matching range is returned.  Each exam exposes the
    date, room and course code used by the Quick Roll Lookup card.
    """
    roll = roll.strip().upper()

    own_roll = (user.roll_number or "").upper()
    use_profile = bool(own_roll) and own_roll == roll
    profile_filter = None
    if use_profile:
        profile_filter = profile_to_filter(get_profile_for_user(session, user))

    try:
        result = lookup_roll(session, roll, profile_filter)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return result


@router.get("/quick-lookup")
def quick_lookup_exam(
    roll: str = Query(..., description="Roll number (e.g., 23BCS100)"),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """
    Quick Roll Lookup: only date, room and course code, with no profile filter.

    Passes an empty profile so every range in the index is considered.
    """
    result = lookup_roll(session, roll.strip().upper(), profile={})
    exams = [
        {
            "date": exam["date"],
            "day": exam["day"],
            "room": exam["room"],
            "course_code": exam["course_code"],
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

    own_roll = (user.roll_number or "").upper()
    profile_filter = (
        profile_to_filter(get_profile_for_user(session, user)) if own_roll == roll else {}
    )

    try:
        result = lookup_roll(session, roll, profile_filter)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
    _: User = Depends(get_current_user),
):
    """Row counts so the Exam page can show whether uploads are present."""
    timetable_rows = len(session.exec(select(MidSemSchedule)).all())
    seating_rows = len(session.exec(select(ExamSeating)).all())
    return {
        "timetable_rows": timetable_rows,
        "seating_rows": seating_rows,
        "has_timetable": timetable_rows > 0,
        "has_seating": seating_rows > 0,
    }


@router.delete("/timetable", status_code=204)
def clear_exam_timetable(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    session.exec(delete(MidSemSchedule))
    session.commit()
    return None


@router.delete("/seating", status_code=204)
def clear_exam_seating(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    session.exec(delete(ExamSeating))
    session.commit()
    return None


@router.post("/debug/parse-exam")
async def debug_parse_exam(file: UploadFile = File(...)):
    """Return the raw extraction alongside the parse result, for troubleshooting."""
    validate_upload(file, "exam PDF/CSV")
    saved_path = save_upload(file, "debug_exam")
    is_csv = saved_path.suffix.lower() == ".csv"

    if is_csv:
        import csv

        with saved_path.open(newline="", encoding="utf-8") as handle:
            return {
                "file_type": "csv",
                "raw_rows": list(csv.DictReader(handle)),
                "parsed_result": parse_seating_index_file(saved_path, is_csv=True),
            }

    import pdfplumber

    tables, texts = [], []
    with pdfplumber.open(saved_path) as pdf:
        for index, page in enumerate(pdf.pages):
            for table in page.extract_tables():
                cleaned = [[(cell or "").strip() for cell in row] for row in table]
                tables.append({"page": index + 1, "table": cleaned})
            texts.append({"page": index + 1, "text": page.extract_text() or ""})

    return {
        "file_type": "pdf",
        "raw_tables": tables,
        "raw_texts": texts,
        "parsed_result": parse_seating_index_file(saved_path, is_csv=False),
    }