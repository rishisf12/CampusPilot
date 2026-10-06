"""Schedule API routes: live schedule (/schedule/now), extra courses."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Optional

from core.database import get_session
from models import Course
from features.schedule.service import get_current_and_next_class

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Schedule"])


class ExtraCourseCreate(BaseModel):
    code: str
    name: str
    semester: int
    branch: str


class ExtraCourseResponse(BaseModel):
    id: int
    code: str
    name: str
    semester: int
    branch: str
    is_elective: bool
    is_extra: bool

    class Config:
        from_attributes = True


@router.get("/now")
def live_schedule(session: Session = Depends(get_session)):
    """
    Get current and next class based on system clock (Asia/Kolkata).
    Uses user profile (semester, branch, electives) + extra courses.
    """
    try:
        return get_current_and_next_class(session)
    except Exception as e:
        logger.error(f"Failed to get live schedule: {e}")
        raise HTTPException(status_code=500, detail="Could not compute schedule")


@router.post("/courses/extra", response_model=ExtraCourseResponse, status_code=status.HTTP_201_CREATED)
def add_extra_course(payload: ExtraCourseCreate, session: Session = Depends(get_session)):
    """
    Add a cross-semester extra course that appears in the user's schedule.
    """
    # Check if course already exists
    existing = session.exec(select(Course).where(Course.code == payload.code)).first()
    if existing:
        # Update to be extra
        existing.is_extra = True
        existing.is_elective = False
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    course = Course(
        code=payload.code,
        name=payload.name,
        semester=payload.semester,
        branch=payload.branch,
        is_elective=False,
        is_extra=True,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    logger.info(f"Added extra course: {course.code}")
    return course


@router.get("/courses/extra", response_model=List[ExtraCourseResponse])
def list_extra_courses(session: Session = Depends(get_session)):
    """List all extra courses."""
    courses = session.exec(select(Course).where(Course.is_extra == True)).all()
    return courses


@router.delete("/courses/extra/{course_code}", status_code=status.HTTP_204_NO_CONTENT)
def remove_extra_course(course_code: str, session: Session = Depends(get_session)):
    """Remove extra course flag (keeps course but removes from schedule)."""
    course = session.exec(select(Course).where(Course.code == course_code)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    course.is_extra = False
    session.add(course)
    session.commit()
    return None