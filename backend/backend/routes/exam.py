"""Exam API routes: upload, debug, lookup, PDF generation."""
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from io import BytesIO

from database import get_session
from models import ExamSeating
from services.exam_parser import (
    parse_exam_file,
    parse_roll,
    roll_in_range,
    extract_raw_text,
)
from services.exam_pdf import generate_exam_pdf
from utils.file_prompt import validate_upload, save_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Exam"])


@router.post("/upload")
async def upload_exam_seating(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    Upload exam seating PDF or CSV.
    Parses and stores all rows in ExamSeating.
    """
    validate_upload(file, "exam seating PDF/CSV")
    saved_path = save_upload(file, "exam")

    is_csv = saved_path.suffix.lower() == ".csv"
    try:
        result = parse_exam_file(saved_path, is_csv=is_csv)
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse exam seating: {e}")

    # Clear existing
    session.exec(select(ExamSeating)).delete(synchronize_session=False)

    # Insert parsed rows
    inserted = 0
    for row_data in result["rows"]:
        row = ExamSeating(**row_data)
        session.add(row)
        inserted += 1

    session.commit()

    return {
        "message": f"Exam seating uploaded and parsed successfully",
        "rows_inserted": inserted,
        "rows_parsed": result["stats"]["rows_parsed"],
    }


@router.post("/debug/parse-exam")
async def debug_parse_exam(file: UploadFile = File(...)):
    """
    DEBUG: Returns RAW extracted tables/text AND parsed result.
    """
    validate_upload(file, "exam seating PDF/CSV")
    saved_path = save_upload(file, "debug_exam")

    is_csv = saved_path.suffix.lower() == ".csv"
    if is_csv:
        import csv
        with saved_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return {
            "file_type": "csv",
            "raw_rows": rows,
            "parsed_result": parse_exam_file(saved_path, is_csv=True),
        }

    # PDF
    tables = []
    texts = []
    import pdfplumber
    with pdfplumber.open(saved_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            if page_tables:
                for t in page_tables:
                    cleaned = [[(cell or "").strip() for cell in row] for row in t]
                    tables.append({"page": i + 1, "table": cleaned})
            texts.append({"page": i + 1, "text": page.extract_text() or ""})

    parsed = parse_exam_file(saved_path, is_csv=False)

    return {
        "file_type": "pdf",
        "raw_tables": tables,
        "raw_texts": texts,
        "parsed_result": parsed,
    }


@router.get("/lookup")
def lookup_exam(roll: str = Query(..., description="Roll number (e.g., 23BCS100)"), session: Session = Depends(get_session)):
    """
    Lookup exam details for a roll number.
    Returns exam date, time slot, room(s), course.
    """
    try:
        prefix, num = parse_roll(roll)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Find all seatings with matching prefix
    seatings = session.exec(
        select(ExamSeating).where(ExamSeating.roll_start_prefix == prefix.upper())
    ).all()

    matches = []
    for seating in seatings:
        if seating.roll_start_num <= num <= seating.roll_end_num:
            matches.append(seating)

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"Roll {roll} not found in any exam seating range"
        )

    # Sort by date, then time
    matches.sort(key=lambda s: (s.exam_date, s.start_time))

    return {
        "roll": roll,
        "exams": [
            {
                "course_code": m.course_code,
                "exam_date": m.exam_date.isoformat(),
                "day": m.exam_date.strftime("%A"),
                "start_time": m.start_time.strftime("%H:%M"),
                "end_time": m.end_time.strftime("%H:%M"),
                "room": m.room,
            }
            for m in matches
        ],
    }


@router.get("/pdf")
def download_exam_pdf(roll: str = Query(..., description="Roll number (e.g., 23BCS100)"), session: Session = Depends(get_session)):
    """
    Generate and download personalized exam timetable PDF.
    """
    try:
        prefix, num = parse_roll(roll)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    seatings = session.exec(
        select(ExamSeating).where(ExamSeating.roll_start_prefix == prefix.upper())
    ).all()

    matches = []
    for seating in seatings:
        if seating.roll_start_num <= num <= seating.roll_end_num:
            matches.append({
                "course_code": seating.course_code,
                "exam_date": seating.exam_date,
                "start_time": seating.start_time.strftime("%H:%M"),
                "end_time": seating.end_time.strftime("%H:%M"),
                "room": seating.room,
            })

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"Roll {roll} not found in any exam seating range"
        )

    matches.sort(key=lambda m: (m["exam_date"], m["start_time"]))

    pdf_bytes = generate_exam_pdf(roll, matches)

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=exam_timetable_{roll}.pdf"}
    )