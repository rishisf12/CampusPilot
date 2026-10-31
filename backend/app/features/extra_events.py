from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date
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
    """Return timetable slot data (course code, branch, semester, instructor,
    room, day, time) from the latest timetable upload, plus filter options.

    Everything comes from ``timetable_slot`` - the table the timetable upload
    writes to - so it always reflects the most recent timetable. Faculty can
    select a timetable entry to auto-fill course code, branch, semester,
    instructor and classroom when adding an extra class or quiz.
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

    # Full timetable slot entries matching the filters.
    query = select(TimetableSlot).distinct(TimetableSlot.course_code, TimetableSlot.day, TimetableSlot.start_time)
    if semester is not None:
        query = query.where(TimetableSlot.semester == semester)
    if branch:
        query = query.where(TimetableSlot.branch_or_program == branch)
    if instructor:
        query = query.where(TimetableSlot.instructor == instructor)

    slots = session.exec(query).all()

    # Resolve course names from the Course table.
    course_codes = [s.course_code for s in slots]
    course_map: dict[str, str] = {}
    if course_codes:
        course_objs = session.exec(
            select(Course).where(Course.code.in_(course_codes))
        ).all()
        course_map = {c.code: c.name for c in course_objs}

    timetable_entries = [
        {
            "code": s.course_code,
            "name": course_map.get(s.course_code, s.course_code),
            "instructor": s.instructor,
            "semester": s.semester,
            "branch": s.branch_or_program,
            "room": s.room,
            "day": s.day,
            "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
            "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
        }
        for s in slots
    ]

    return {
        "semesters": sorted(semesters),
        "branches": sorted(branches),
        "instructors": sorted(instructors),
        "courses": [
            {
                "code": e["code"],
                "name": e["name"],
                "instructor": e["instructor"],
                "semester": e["semester"],
                "branch": e["branch"],
            }
            for e in timetable_entries
        ],
        "timetable_entries": timetable_entries,
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
    room: str | None = None,
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
        room=room,
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
