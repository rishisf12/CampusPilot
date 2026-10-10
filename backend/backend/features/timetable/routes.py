"""Timetable API routes: upload, debug, clear, edit slot, options."""
import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from core.database import get_session
from models import TimetableSlot, TimetableUpload, User
from core.deps import get_current_user
from features.attendance.service import sync_courses_from_timetable
from features.exam.parser import normalize_branch
from features.timetable.parser import parse_timetable_file
from core.files import UPLOAD_DIR, save_upload, validate_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Timetable"])


class SlotEdit(BaseModel):
    day: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    room: str | None = None
    course_code: str | None = None
    instructor: str | None = None
    branch_or_program: str | None = None
    semester: int | None = None


class SlotResponse(BaseModel):
    id: int
    day: str
    start_time: str
    end_time: str
    room: str
    course_code: str
    instructor: str | None = None
    branch_or_program: str
    semester: int


@router.post("/upload")
async def upload_timetable(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    Upload master timetable PDF or CSV.
    Parses and stores all slots in TimetableSlot.
    Returns parse report.
    """
    validate_upload(file, "master timetable PDF/CSV")
    saved_path = save_upload(file, "timetable")

    is_csv = saved_path.suffix.lower() == ".csv"
    try:
        result = parse_timetable_file(saved_path, is_csv=is_csv)
    except Exception as e:
        # user-facing 400, and the parser can raise anything.
        logger.error(f"Parse failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse timetable: {e}") from e

    # Refuse before touching stored data. A file that yields no usable rows would
    # otherwise wipe the timetable and still answer "parsed successfully", which
    # is far worse than an error the user can act on.
    if not result["slots"]:
        detail = "No timetable rows could be read from that file, so the existing timetable was left untouched."
        if result["warnings"]:
            detail += f" First problem: {result['warnings'][0]}"
        logger.warning("Timetable upload produced no slots: %s", result["warnings"][:3])
        raise HTTPException(status_code=400, detail=detail)

    # Replace the stored slots now that the new ones are known to be usable.
    session.exec(delete(TimetableSlot))

    # Insert parsed slots
    inserted = 0
    for slot_data in result["slots"]:
        slot = TimetableSlot(**slot_data)
        session.add(slot)
        inserted += 1

    session.commit()

    # Attendance is driven by the timetable, so refresh the course list now.
    new_courses = sync_courses_from_timetable(session)

    # Remember the file so the UI can preview it. Only the newest is referenced.
    session.exec(delete(TimetableUpload))
    session.add(
        TimetableUpload(
            filename=saved_path.name,
            original_name=file.filename,
            size_bytes=saved_path.stat().st_size,
            uploaded_at=datetime.now(),
        )
    )
    session.commit()

    return {
        "message": "Timetable uploaded and parsed successfully",
        "slots_inserted": inserted,
        "slots_found": result["stats"]["slots_found"],
        "courses_synced": new_courses,
        "warnings": result["warnings"],
        "parse_report": result["stats"],
    }


@router.post("/debug/parse-timetable")
async def debug_parse_timetable(
    file: UploadFile = File(...),
):
    """
    DEBUG: Returns RAW extracted tables/text per page AND the parsed result.
    Use this to see exactly where parsing fails.
    """
    validate_upload(file, "master timetable PDF/CSV")
    saved_path = save_upload(file, "debug_timetable")

    is_csv = saved_path.suffix.lower() == ".csv"
    if is_csv:
        import csv
        with saved_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return {
            "file_type": "csv",
            "raw_rows": rows,
            "parsed_result": parse_timetable_file(saved_path, is_csv=True),
        }

    # PDF: return raw tables AND raw text
    import pdfplumber
    tables = []
    texts = []
    with pdfplumber.open(saved_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            if page_tables:
                for t in page_tables:
                    cleaned = [[(cell or "").strip() for cell in row] for row in t]
                    tables.append({"page": i + 1, "table": cleaned})
            texts.append({"page": i + 1, "text": page.extract_text() or ""})

    parsed = parse_timetable_file(saved_path, is_csv=False)

    return {
        "file_type": "pdf",
        "raw_tables": tables,
        "raw_texts": texts,
        "parsed_result": parsed,
    }


@router.get("/options")
def timetable_options(session: Session = Depends(get_session)):
    """
    Branch / semester / course options discovered in the uploaded timetable.

    The profile dropdowns use this so branch choices reflect the real timetable.
    """
    slots = session.exec(select(TimetableSlot)).all()

    branches = OrderedDict()
    for slot in slots:
        branch = normalize_branch(slot.branch_or_program)
        if branch and branch not in branches:
            branches[branch] = 0
        if branch:
            branches[branch] += 1

    semesters = sorted({slot.semester for slot in slots if slot.semester})
    courses = sorted({(slot.course_code or "").upper() for slot in slots if slot.course_code})

    return {
        "branches": list(branches),
        "branch_counts": branches,
        "semesters": semesters,
        "courses": courses,
        "total_slots": len(slots),
    }


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_timetable(session: Session = Depends(get_session)):
    """Clear all timetable slots."""
    session.exec(delete(TimetableSlot))
    session.exec(delete(TimetableUpload))
    session.commit()
    return


def _latest_timetable_upload(session: Session) -> Optional[TimetableUpload]:
    """The newest recorded class-timetable upload, or ``None``."""
    return session.exec(
        select(TimetableUpload).order_by(TimetableUpload.id.desc())
    ).first()


def _resolve_upload_path(filename: str):
    """
    Resolve a stored filename inside ``uploads/``.

    The name comes from the database rather than the request, but it is still
    resolved and checked to be inside the upload directory so a stray ``..``
    can never escape it.
    """
    candidate = (UPLOAD_DIR / Path(filename).name).resolve()
    root = UPLOAD_DIR.resolve()
    if root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid upload path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on the server")
    return candidate


@router.get("/uploads/latest")
def latest_timetable_upload(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """
    Metadata for the newest class-timetable file, for the preview button.

    Returns ``{"available": false}`` rather than 404 when nothing has been
    uploaded, so the UI can simply hide the button.
    """
    record = _latest_timetable_upload(session)
    if record is None:
        return {"available": False}

    try:
        exists = _resolve_upload_path(record.filename).is_file()
    except HTTPException:
        exists = False

    return {
        "available": exists,
        "filename": record.filename,
        "original_name": record.original_name or record.filename,
        "size_bytes": record.size_bytes,
        "uploaded_at": record.uploaded_at.isoformat() if record.uploaded_at else None,
        "preview_url": "/timetable/uploads/preview",
    }


@router.get("/uploads/preview")
def preview_timetable_upload(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Stream the newest uploaded class timetable, inline, for preview."""
    record = _latest_timetable_upload(session)
    if record is None:
        raise HTTPException(status_code=404, detail="No class timetable has been uploaded")

    path = _resolve_upload_path(record.filename)
    media_type = "text/csv" if path.suffix.lower() == ".csv" else "application/pdf"
    return FileResponse(
        path,
        media_type=media_type,
        # `inline` so the browser renders it in a tab instead of downloading it.
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.put("/slot/{slot_id}", response_model=SlotResponse)
def edit_slot(slot_id: int, payload: SlotEdit, session: Session = Depends(get_session)):
    """Edit a weekly timetable slot."""
    slot = session.get(TimetableSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key in ("start_time", "end_time") and value:
            # Parse time string
            from features.timetable.parser import parse_time_str
            parsed = parse_time_str(value)
            if not parsed:
                raise HTTPException(status_code=400, detail=f"Invalid time format: {value}")
            setattr(slot, key, parsed)
        else:
            setattr(slot, key, value)

    session.add(slot)
    session.commit()
    session.refresh(slot)
    return slot


@router.get("/slots", response_model=List[SlotResponse])
def list_slots(session: Session = Depends(get_session)):
    """List all timetable slots (for debugging)."""
    slots = session.exec(select(TimetableSlot)).all()
    # `SlotResponse` declares times as strings, so format them explicitly
    # rather than handing back `datetime.time` objects.
    return [
        SlotResponse(
            id=slot.id,
            day=slot.day,
            start_time=slot.start_time.strftime("%H:%M") if slot.start_time else "",
            end_time=slot.end_time.strftime("%H:%M") if slot.end_time else "",
            room=slot.room,
            course_code=slot.course_code,
            instructor=slot.instructor,
            branch_or_program=slot.branch_or_program,
            semester=slot.semester,
        )
        for slot in slots
    ]