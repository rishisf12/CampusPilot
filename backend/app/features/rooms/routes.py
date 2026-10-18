"""Rooms API routes: vacant room finder (live + manual)."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_user
from models import User
from features.rooms.service import (
    get_vacant_rooms_live,
    get_vacant_rooms_manual,
    get_all_rooms,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Rooms"])


@router.get("/vacant")
def vacant_rooms(
    mode: str = Query("live", pattern="^(live|manual)$"),
    day: str = Query(None),
    hour: str = Query(None),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Get vacant rooms.
    
    - mode=live: uses server system clock (default)
    - mode=manual: requires day (Mon-Sun) and hour (HH:MM)
    """
    try:
        if mode == "live":
            result = get_vacant_rooms_live(session, user_id=user.id)
        else:
            if not day or not hour:
                raise HTTPException(
                    status_code=400,
                    detail="Manual mode requires 'day' and 'hour' query parameters"
                )
            result = get_vacant_rooms_manual(session, day, hour, user_id=user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # into a 500; the detail is logged, never returned.
        logger.error(f"Failed to get vacant rooms: {e}")
        raise HTTPException(status_code=500, detail="Could not compute vacant rooms") from e


@router.get("/all")
def list_all_rooms(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """List all rooms found in timetable."""
    rooms = get_all_rooms(session, user_id=user.id)
    return {"rooms": rooms, "count": len(rooms)}