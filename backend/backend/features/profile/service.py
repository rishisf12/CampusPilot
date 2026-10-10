"""Profile helpers shared by the exam, timetable and attendance routes."""
import logging
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from models import User, UserProfile
from features.exam.parser import normalize_branch

logger = logging.getLogger(__name__)

DEFAULT_PROFILE: Dict[str, Any] = {
    "id": 1,
    "user_id": None,
    "first_name": None,
    "last_name": None,
    "programme": "BTech",
    "semester": 1,
    "branch": "CSE A",
    "elective_codes": [],
    "attendance_target": 75.0,
    "original_branch": None,
    "branch_change_requested": False,
    "requested_branch": None,
}


def get_profile_for_user(session: Session, user: Optional[User]) -> UserProfile:
    """
    Return the profile row for ``user``, creating a default one when missing.

    The legacy schema used a single shared profile (``id=1``); this keeps that
    working while preferring the authenticated user's own profile.
    """
    if user is not None:
        profile = session.exec(
            select(UserProfile).where(UserProfile.user_id == user.id)
        ).first()
        if profile:
            return profile
        if not profile:
            profile = UserProfile(
                user_id=user.id,
                first_name=(user.full_name or "").split(" ")[0] if user.full_name else None,
                last_name=" ".join((user.full_name or "").split(" ")[1:]) or None,
                semester=1,
                branch="CSE A",
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

    profile = session.exec(select(UserProfile).where(UserProfile.id == 1)).first()
    if profile:
        return profile

    profile = UserProfile(id=1, semester=1, branch="CSE A")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def profile_to_filter(profile: Optional[UserProfile]) -> Dict[str, Any]:
    """Reduce a profile row to the fields the exam/timetable filters need."""
    if profile is None:
        return dict(DEFAULT_PROFILE)
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "programme": profile.programme,
        "semester": profile.semester,
        "branch": normalize_branch(profile.branch) or profile.branch,
        "elective_codes": list(profile.elective_codes or []),
        "attendance_target": profile.attendance_target,
        "original_branch": profile.original_branch,
        "branch_change_requested": bool(profile.branch_change_requested),
        "requested_branch": profile.requested_branch,
    }


def elective_codes(profile: Optional[UserProfile]) -> List[str]:
    """Normalised list of the student's opted-in elective course codes."""
    if profile is None:
        return []
    return [code.strip().upper() for code in (profile.elective_codes or []) if code and code.strip()]