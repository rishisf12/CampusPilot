from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date, timedelta
from core.database import get_session
from core.deps import get_current_user
from models import User, ExtraEvent, TimetableSlot, Course, UserProfile

router = APIRouter(tags=["Extra Events"])


@router.get("/extra-events/options")
async def extra_event_options(
    semester: int | None = None,
    branch: str | None = None,
    instructor: str | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Return filter options (semesters, branches, instructors) and matching
    courses from the latest timetable upload. Used by the faculty Manage
    screen to auto-select the course code when semester+branch+instructor
    are chosen.

    All figures come from ``timetable_slot`` - the table the timetable upload
    writes to - so they always reflect the most recent timetable, whatever
    semester/branch/instructor combination is currently published.
    """
    # Current user's profile (for default values)
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).first()

    # Distinct values from the timetable - always the latest upload.
    semesters = [
        s
        for s in session.exec(
            select(TimetableSlot.semester).distinct().where(
                TimetableSlot.semester.is_not(None)
            )
        ).all()
        if s
    ]
    branches = [
        b
        for b in session.exec(
            select(TimetableSlot.branch_or_program).distinct().where(
                TimetableSlot.branch_or_program.is_not(None)
            )
        ).all()
        if b
    ]
    instructors = [
        i
        for i in session.exec(
            select(TimetableSlot.instructor).distinct().where(
                TimetableSlot.instructor.is_not(None)
            )
        ).all()
        if i
    ]

    # Matching courses for the selected semester/branch/instructor.
    course_query = select(
        TimetableSlot.course_code,
        TimetableSlot.instructor,
        TimetableSlot.semester,
        TimetableSlot.branch_or_program,
    ).distinct()
    if semester is not None:
        course_query = course_query.where(TimetableSlot.semester == semester)
    if branch:
        course_query = course_query.where(
            TimetableSlot.branch_or_program == branch
        )
    if instructor:
        course_query = course_query.where(TimetableSlot.instructor == instructor)

    course_rows = session.exec(course_query).all()

    # Resolve course names from the Course table.
    course_codes = [r[0] for r in course_rows]
    course_map: dict[str, str] = {}
    if course_codes:
        course_objs = session.exec(
            select(Course).where(Course.code.in_(course_codes))
        ).all()
        course_map = {c.code: c.name for c in course_objs}

    courses = [
        {
            "code": code,
            "name": course_map.get(code, code),
            "instructor": instr,
            "semester": sem,
            "branch": br,
        }
        for code, instr, sem, br in course_rows
    ]

    return {
        "semesters": sorted(semesters),
        "branches": sorted(branches),
        "instructors": sorted(instructors),
        "courses": courses,
        "profile": {
            "first_name": profile.first_name if profile else None,
            "last_name": profile.last_name if profile else None,
            "branch": profile.branch if profile else None,
            "semester": profile.semester if profile else None,
            "designation": profile.designation if profile else None,
            "timetable_notation": profile.timetable_notation if profile else None,
            "full_name": (
                f"{profile.first_name or ''} {profile.last_name or ''}".strip()
                if profile
                else None
            ),
        } if profile else None,
    }


@router.post("/extra-events")
async def create_extra(
    course_code: str,
    label: str,
    event_date: date,
    time_slot: str = None,
    semester: int | None = None,
    branch: str | None = None,
    instructor: str | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    event = ExtraEvent(
        course_code=course_code,
        label=label,
        event_date=event_date,
        time_slot=time_slot,
        instructor_id=user.id,
        semester=semester,
        branch=branch,
        instructor_name=instructor,
        expires_at=event_date,
    )
    session.add(event)
    session.commit()
    return {"id": event.id, "message": "Extra event created"}


@router.delete("/extra-events/{event_id}")
async def delete_extra(
    event_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    event = session.get(ExtraEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Not found")
    event.cancelled = True
    session.commit()
    return {"message": "Extra event cancelled"}
