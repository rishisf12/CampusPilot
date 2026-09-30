"""Attendance API routes."""
import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from pydantic import BaseModel, Field

from database import get_session
from models import AttendanceStatus
from services.attendance_service import (
    get_overall_summary,
    get_course_summary,
    mark_attendance,
    delete_attendance,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Attendance"])


class AttendanceMark(BaseModel):
    course_id: int = Field(..., gt=0)
    date: date
    status: AttendanceStatus


class AttendanceResponse(BaseModel):
    id: int
    course_id: int
    date: date
    status: AttendanceStatus


@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(payload: AttendanceMark, session: Session = Depends(get_session)):
    """Mark a class Present / Absent / Cancelled."""
    try:
        record = mark_attendance(session, payload.course_id, payload.date, payload.status)
        session.commit()
        session.refresh(record)
        return record
    except Exception as e:
        logger.error(f"Failed to mark attendance: {e}")
        raise HTTPException(status_code=500, detail="Could not record attendance")


@router.get("/summary")
def attendance_summary(session: Session = Depends(get_session)):
    """Overall + per-course attendance percentages."""
    try:
        return get_overall_summary(session)
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        raise HTTPException(status_code=500, detail="Could not compute summary")


@router.get("/course/{course_id}")
def course_attendance(course_id: int, session: Session = Depends(get_session)):
    """Single course attendance detail."""
    summary = get_course_summary(session, course_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Course not found")
    return summary


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_attendance(record_id: int, session: Session = Depends(get_session)):
    """Delete an attendance record."""
    if not delete_attendance(session, record_id):
        raise HTTPException(status_code=404, detail="Record not found")
    session.commit()
    return None