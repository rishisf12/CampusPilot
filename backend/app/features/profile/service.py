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


def _default_branch_id(session: Session) -> Optional[int]:
    """Branch id used for a profile created without an explicit branch.

    The schema stores ``branch_id`` (a FK), not a free-text branch, so a new
    profile has to resolve a real row rather than pass a string.
    """
    from models import Branch

    branch = session.exec(select(Branch).where(Branch.code == "CSE")).first()
    return branch.id if branch else None


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
                branch_id=_default_branch_id(session),
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

    profile = session.exec(select(UserProfile).where(UserProfile.id == 1)).first()
    if profile:
        return profile

    profile = UserProfile(id=1, semester=1, branch="CSE A", branch_id=_default_branch_id(session))
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def profile_to_filter(profile: Optional[UserProfile], session: Optional[Session] = None) -> Dict[str, Any]:
    """Reduce a profile row to the fields the exam/timetable filters need."""
    if profile is None:
        return dict(DEFAULT_PROFILE)
    
    # Prefer the free-text branch (the field the profile API reads and writes)
    # and fall back to the FK for rows that carry only a branch_id.
    branch_code = profile.branch
    if not branch_code and profile.branch_id and session:
        from models import Branch
        branch_obj = session.get(Branch, profile.branch_id)
        if branch_obj:
            branch_code = branch_obj.code
    
    # Resolve original_branch code
    original_branch_code = profile.original_branch
    if not original_branch_code and profile.original_branch_id and session:
        from models import Branch
        branch_obj = session.get(Branch, profile.original_branch_id)
        if branch_obj:
            original_branch_code = branch_obj.code
    
    # Resolve requested_branch code
    requested_branch_code = profile.requested_branch
    if not requested_branch_code and profile.requested_branch_id and session:
        from models import Branch
        branch_obj = session.get(Branch, profile.requested_branch_id)
        if branch_obj:
            requested_branch_code = branch_obj.code
    
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "programme": profile.programme,
        "semester": profile.semester,
        "branch": normalize_branch(branch_code) or branch_code,
        "elective_codes": list(profile.elective_codes or []),
        "attendance_target": profile.attendance_target,
        "original_branch": normalize_branch(original_branch_code) or original_branch_code,
        "branch_change_requested": bool(profile.branch_change_requested),
        "requested_branch": normalize_branch(requested_branch_code) or requested_branch_code,
    }


def elective_codes(profile: Optional[UserProfile]) -> List[str]:
    """Normalised list of the student's opted-in elective course codes."""
    if profile is None:
        return []
    return [code.strip().upper() for code in (profile.elective_codes or []) if code and code.strip()]