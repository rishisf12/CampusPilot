"""OCR + LLM extraction API routes."""
import os
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlmodel import Session

from database import get_session
from ocr_engine import (
    process_uploaded_pdf,
    extract_text_from_pdf,
)
from utils.file_prompt import validate_upload, save_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["OCR Extraction"])


@router.post("/extract/timetable")
async def extract_timetable(
    file: UploadFile = File(...),
    hf_token: str = Form(None),
    model: str = Form("microsoft/phi-3-mini-4k-instruct"),
    poppler_path: str = Form(None),
    session: Session = Depends(get_session)
):
    """
    Extract timetable data from PDF using OCR + Hugging Face LLM.
    
    - Upload a timetable PDF
    - OCR extracts text from each page
    - Hugging Face LLM structures the data
    - Returns structured timetable slots
    """
    try:
        validate_upload(file, "timetable PDF")
        saved_path = save_upload(file, "ocr_timetable")
        
        hf_token = hf_token or os.getenv("HF_TOKEN")
        result = process_uploaded_pdf(saved_path, 'timetable', hf_token=hf_token, poppler_path=poppler_path)
        
        # Store in database if needed
        from models import TimetableSlot
        from sqlmodel import select
        
        inserted = 0
        for slot_data in result.get('slots', []):
            # Check if already exists
            existing = session.exec(select(TimetableSlot).where(
                TimetableSlot.day == slot_data['day'],
                TimetableSlot.start_time == slot_data['start_time'],
                TimetableSlot.end_time == slot_data['end_time'],
                TimetableSlot.room == slot_data['room'],
                TimetableSlot.course_code == slot_data['course_code']
            )).first()
            
            if not existing:
                slot = TimetableSlot(**slot_data)
                session.add(slot)
                inserted += 1
        
        session.commit()
        result['slots_inserted'] = inserted
        
        return JSONResponse(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timetable extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract/exam")
async def extract_exam(
    file: UploadFile = File(...),
    hf_token: str = Form(None),
    model: str = Form("microsoft/phi-3-mini-4k-instruct"),
    poppler_path: str = Form(None),
    session: Session = Depends(get_session)
):
    """
    Extract exam seating data from PDF using OCR + Hugging Face LLM.
    
    - Upload an exam seating PDF
    - OCR extracts text from each page
    - Hugging Face LLM structures the data
    - Returns structured exam seating rows
    """
    try:
        validate_upload(file, "exam seating PDF")
        saved_path = save_upload(file, "ocr_exam")
        
        hf_token = hf_token or os.getenv("HF_TOKEN")
        result = process_uploaded_pdf(saved_path, 'exam', hf_token=hf_token, poppler_path=poppler_path)
        
        # Store in database
        from models import ExamSeating
        from sqlmodel import select
        
        inserted = 0
        for row_data in result.get('rows', []):
            # Check if already exists
            existing = session.exec(select(ExamSeating).where(
                ExamSeating.roll_start_prefix == row_data['roll_start_prefix'],
                ExamSeating.roll_start_num == row_data['roll_start_num'],
                ExamSeating.roll_end_num == row_data['roll_end_num'],
                ExamSeating.exam_date == row_data['exam_date']
            )).first()
            
            if not existing:
                row = ExamSeating(**row_data)
                session.add(row)
                inserted += 1
        
        session.commit()
        result['rows_inserted'] = inserted
        
        return JSONResponse(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exam extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/debug/extract-text")
async def debug_extract_text(
    file: UploadFile = File(...),
    poppler_path: str = Form(None),
):
    """
    Debug endpoint: Returns raw OCR text from each page.
    Use this to verify OCR quality before LLM processing.
    """
    try:
        validate_upload(file, "PDF")
        saved_path = save_upload(file, "ocr_debug")
        
        from ocr_engine import extract_text_from_pdf
        ocr_results = extract_text_from_pdf(saved_path, poppler_path=poppler_path)
        
        return {
            'file': file.filename,
            'pages': len(ocr_results),
            'results': ocr_results
        }
        
    except Exception as e:
        logger.error(f"Debug extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Debug extraction failed: {str(e)}")


@router.get("/models")
async def list_recommended_models():
    """List recommended Hugging Face models for extraction."""
    return {
        "recommended_models": [
            {
                "id": "microsoft/phi-3-mini-4k-instruct",
                "name": "Phi-3 Mini 4K",
                "size": "3.8B params",
                "description": "Fast, good for structured extraction, 4K context"
            },
            {
                "id": "microsoft/phi-3-medium-4k-instruct",
                "name": "Phi-3 Medium 4K",
                "size": "14B params",
                "description": "Better accuracy, slower"
            },
            {
                "id": "mistralai/Mistral-7B-Instruct-v0.3",
                "name": "Mistral 7B Instruct v0.3",
                "size": "7B params",
                "description": "Excellent for structured data extraction"
            },
            {
                "id": "google/gemma-2b-it",
                "name": "Gemma 2B IT",
                "size": "2B params",
                "description": "Very fast, good for simple extraction"
            },
            {
                "id": "google/gemma-7b-it",
                "name": "Gemma 7B IT",
                "size": "7B params",
                "description": "Better accuracy than 2B"
            }
        ],
        "note": "Set HF_TOKEN environment variable or pass hf_token parameter for authenticated requests (higher rate limits)"
    }