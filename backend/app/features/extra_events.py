from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from datetime import date, timedelta
from core.database import get_session
from core.deps import get_current_user
from models import User, ExtraEvent

router = APIRouter(tags=["Extra Events"])

@router.post("/extra-events")
async def create_extra(
    course_code: str,
    label: str,
    event_date: date,
    time_slot: str = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    event = ExtraEvent(
        course_code=course_code,
        label=label,
        event_date=event_date,
        time_slot=time_slot,
        instructor_id=user.id,
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
