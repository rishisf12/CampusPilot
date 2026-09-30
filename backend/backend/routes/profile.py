"""Profile API routes: get/update user profile (semester, branch, electives)."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Optional

from database import get_session
from models import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Profile"])


class ProfileBase(BaseModel):
    semester: int
    branch: str
    elective_codes: List[str] = []


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(BaseModel):
    semester: Optional[int] = None
    branch: Optional[str] = None
    elective_codes: Optional[List[str]] = None


class ProfileResponse(ProfileBase):
    id: int

    class Config:
        from_attributes = True


@router.get("/", response_model=ProfileResponse)
def get_profile(session: Session = Depends(get_session)):
    """Get the user profile (single profile, id=1)."""
    profile = session.get(UserProfile, 1)
    if not profile:
        # Return default if not set
        return ProfileResponse(id=1, semester=1, branch="CSE", elective_codes=[])
    return profile


@router.put("/", response_model=ProfileResponse)
def update_profile(payload: ProfileUpdate, session: Session = Depends(get_session)):
    """Update semester, branch, and/or elective course codes."""
    profile = session.get(UserProfile, 1)
    if not profile:
        profile = UserProfile(id=1, semester=1, branch="CSE", elective_codes=[])
        session.add(profile)

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(profile, key, value)

    session.add(profile)
    session.commit()
    session.refresh(profile)
    logger.info(f"Profile updated: {profile}")
    return profile