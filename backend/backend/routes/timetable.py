"""Timetable API routes: upload, debug, clear, edit slot."""
import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlmodel import Session, select
from pydantic import BaseModel

from database import get_session
from models import TimetableSlot
from services.timetable_parser import parse_timetable_file, extract_raw_text
from utils.file_prompt import validate_upload, save_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Timetable"])


class SlotEdit(BaseModel):
    day: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    room: str | None = None
    course_code: str | None = None
    branch_or_program: str | None = None
    semester: int | None = None


class SlotResponse(BaseModel):
    id: int
    day: str
    start_time: str
    end_time: str
    room: str
    course_code: str
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
        logger.error(f"Parse failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse timetable: {e}")

    # Clear existing slots (optional: could be separate endpoint)
    session.exec(select(TimetableSlot)).delete(synchronize_session=False)

    # Insert parsed slots
    inserted = 0
    for slot_data in result["slots"]:
        slot = TimetableSlot(**slot_data)
        session.add(slot)
        inserted += 1

    session.commit()

    return {
        "message": f"Timetable uploaded and parsed successfully",
        "slots_inserted": inserted,
        "slots_found": result["stats"]["slots_found"],
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


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_timetable(session: Session = Depends(get_session)):
    """Clear all timetable slots."""
    session.exec(select(TimetableSlot)).delete(synchronize_session=False)
    session.commit()
    return None


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
            from services.timetable_parser import parse_time_str
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
    return slots