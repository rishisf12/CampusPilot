"""Attendance API routes: mark, summary, subjects, per-course calendar."""
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from database import get_session
from models import AttendanceRecord, AttendanceStatus, Course, User
from routes.deps import get_current_user
from services.attendance_service import (
    delete_attendance,
    get_course_calendar,
    get_course_summary,
    get_overall_summary,
    get_subjects,
    mark_attendance,
    sync_courses_from_timetable,
)
from services.profile_service import get_profile_for_user, profile_to_filter

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

    class Config:
        from_attributes = True


@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(
    payload: AttendanceMark,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Mark a class Present / Absent / Cancelled."""
    course = session.exec(select(Course).where(Course.id == payload.course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        record = mark_attendance(session, payload.course_id, payload.date, payload.status)
        session.commit()
        session.refresh(record)
        return record
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to mark attendance")
        raise HTTPException(status_code=500, detail=f"Could not record attendance: {exc}")


@router.get("/summary")
def attendance_summary(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Overall plus per-course attendance, limited to the student's subjects."""
    profile = profile_to_filter(get_profile_for_user(session, user))
    return get_overall_summary(session, profile)


@router.get("/subjects")
def list_subjects(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Subjects the student can mark, derived from the uploaded timetable.

    Syncs courses first so a freshly uploaded timetable immediately shows up.
    """
    profile = profile_to_filter(get_profile_for_user(session, user))
    sync_courses_from_timetable(session)
    subjects = get_subjects(session, profile)
    return {
        "count": len(subjects),
        "profile": {"branch": profile["branch"], "semester": profile["semester"]},
        "subjects": subjects,
    }


@router.get("/sync")
def sync_subjects(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Re-run the timetable -> course sync on demand."""
    created = sync_courses_from_timetable(session)
    total = len(session.exec(select(Course)).all())
    return {"message": f"Synced {created} new course(s)", "new_courses": created, "total_courses": total}


@router.get("/course/{course_id}")
def course_attendance(
    course_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Single-course summary plus its date-by-date calendar."""
    summary = get_course_summary(session, course_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Course not found")
    summary["calendar"] = get_course_calendar(session, course_id)
    return summary


@router.get("/records")
def list_records(
    course_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Raw attendance records, optionally limited to one course."""
    query = select(AttendanceRecord)
    if course_id is not None:
        query = query.where(AttendanceRecord.course_id == course_id)
    records = session.exec(query).all()
    return [
        {
            "id": r.id,
            "course_id": r.course_id,
            "date": r.date.isoformat(),
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        }
        for r in records
    ]


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_attendance(
    record_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Delete an attendance record."""
    if not delete_attendance(session, record_id):
        raise HTTPException(status_code=404, detail="Record not found")
    session.commit()
    return None