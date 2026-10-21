"""Profile API routes: profile CRUD, branch options, and branch-change tracking."""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.database import get_session
from models import User, UserProfile, normalize_tags
from core.deps import get_current_user
from features.exam.parser import (
    BRANCH_OPTIONS,
    PROGRAMME_BRANCHES,
    PROGRAMME_GROUPS,
    PROGRAMME_SEMESTERS,
    normalize_branch,
    programme_group,
    programmes_in_group,
)
from features.profile.service import get_profile_for_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Profile"])

#: Roman-numeral semester labels used by the profile dropdown.
SEMESTER_LABELS = {
    1: "I Sem", 2: "II Sem", 3: "III Sem", 4: "IV Sem",
    5: "V Sem", 6: "VI Sem", 7: "VII Sem", 8: "VIII Sem",
}


class ProfileBase(BaseModel):
    semester: int
    branch: str
    elective_codes: List[str] = []


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    programme: Optional[str] = None
    semester: Optional[int] = None
    #: The year the student joined, e.g. 2024. The roll number carries it
    #: ("24BCS125" -> 2024), but it is asked for and stored on its own so a
    #: typo in the roll can be corrected without changing the roll.
    batch_year: Optional[int] = None
    branch: Optional[str] = None
    section: Optional[str] = None
    elective_codes: Optional[List[str]] = None
    attendance_target: Optional[float] = None
    #: Skill tags for team-finding, free-form. Normalised on write.
    skills: Optional[List[str]] = None
    bio: Optional[str] = None
    contact: Optional[str] = None


class ProfileResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    programme: Optional[str] = None
    semester: int
    batch_year: Optional[int] = None
    branch: str
    section: Optional[str] = None
    elective_codes: List[str] = []
    attendance_target: float = 75.0
    skills: List[str] = []
    bio: Optional[str] = None
    contact: Optional[str] = None
    original_branch: Optional[str] = None
    branch_changed_at: Optional[datetime] = None
    branch_change_requested: bool = False
    requested_branch: Optional[str] = None
    branch_change_reason: Optional[str] = None
    branch_change_requested_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BranchChangeRequest(BaseModel):
    """A branch-change request: the branch being left and the one requested."""

    from_branch: Optional[str] = None
    to_branch: str = Field(..., description="Target branch (e.g. 'CSE B')")
    reason: Optional[str] = None


class BranchChangeResponse(BaseModel):
    message: str
    original_branch: Optional[str] = None
    previous_branch: Optional[str] = None
    requested_branch: Optional[str] = None
    branch_change_requested: bool = False
    branch_changed_at: Optional[datetime] = None
    branch_change_requested_at: Optional[datetime] = None


def _to_response(profile: UserProfile) -> ProfileResponse:
    # `branch` is nullable in the database (a student may not have picked one
    # yet) but the response model declares it as a required string. Passing the
    # raw NULL through made Pydantic raise a ValidationError, and the endpoint
    # answered 500 for the whole profile screen. Coerce it here so the
    # response keeps its "always a string" contract without failing.
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        phone=profile.phone,
        programme=profile.programme,
        semester=profile.semester,
        batch_year=profile.batch_year,
        branch=profile.branch or "",
        section=profile.section,
        elective_codes=list(profile.elective_codes or []),
        attendance_target=profile.attendance_target,
        skills=list(profile.skills or []),
        bio=profile.bio,
        contact=profile.contact,
        original_branch=profile.original_branch,
        branch_changed_at=profile.branch_changed_at,
        branch_change_requested=bool(profile.branch_change_requested),
        requested_branch=profile.requested_branch,
        branch_change_reason=profile.branch_change_reason,
        branch_change_requested_at=profile.branch_change_requested_at,
    )


@router.get("/options")
def profile_options():
    """Programme, branch and semester choices that populate the profile dropdowns."""
    return {
        "branches": BRANCH_OPTIONS,
        "programmes": [p for programmes in PROGRAMME_GROUPS.values() for p in programmes],
        "programme_groups": {group: list(ps) for group, ps in PROGRAMME_GROUPS.items()},
        "programme_branches": {p: list(b) for p, b in PROGRAMME_BRANCHES.items()},
        "programme_semesters": {p: list(s) for p, s in PROGRAMME_SEMESTERS.items()},
        "semesters": [
            {"value": number, "label": label} for number, label in SEMESTER_LABELS.items()
        ],
    }


@router.get("/", response_model=ProfileResponse)
def get_profile(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile."""
    profile = get_profile_for_user(session, user)
    return _to_response(profile)


@router.put("/", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Update programme, semester, branch, section, electives, skills or target."""
    profile = get_profile_for_user(session, user)

    data = payload.model_dump(exclude_unset=True)

    # The group chosen at signup is fixed: a BTech student may switch to BDes
    # (an MTech student to MDes) but never across groups. A profile with no
    # programme yet may set one freely; afterwards the group is locked, so the
    # dropdowns keep offering only that group's branches and semesters.
    current_group = programme_group(profile.programme) if profile.programme else None

    if data.get("programme") is not None:
        new_programme = data["programme"]
        if current_group and new_programme not in programmes_in_group(current_group):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Programme '{new_programme}' is not available for your "
                    f"{current_group} registration. Choose one of "
                    f"{list(programmes_in_group(current_group))}."
                ),
            )

    effective_programme = data.get("programme") or profile.programme
    allowed_branches = PROGRAMME_BRANCHES.get(effective_programme or "", tuple(BRANCH_OPTIONS))

    if data.get("branch"):
        normalized = normalize_branch(data["branch"])
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown branch '{data['branch']}'. Choose one of {BRANCH_OPTIONS}.",
            )
        if normalized not in allowed_branches:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Branch '{normalized}' is not available for "
                    f"{effective_programme or 'your programme'}. "
                    f"Choose one of {list(allowed_branches)}."
                ),
            )
        data["branch"] = normalized

    if data.get("semester") is not None:
        allowed_semesters = PROGRAMME_SEMESTERS.get(effective_programme or "")
        if allowed_semesters and data["semester"] not in allowed_semesters:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Semester {data['semester']} is not valid for "
                    f"{effective_programme or 'your programme'}. "
                    f"Choose one of {list(allowed_semesters)}."
                ),
            )

    if data.get("batch_year") is not None:
        # The same bound signup applies: a batch year is a calendar year the
        # student joined in, and a year outside the range is a typo.
        latest = datetime.now(timezone.utc).year + 1
        if not 2000 <= data["batch_year"] <= latest:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch year must be between 2000 and {latest}.",
            )

    if "elective_codes" in data and data["elective_codes"] is not None:
        # Store normalised, de-duplicated, upper-case codes.
        seen: List[str] = []
        for code in data["elective_codes"]:
            cleaned = (code or "").strip().upper()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        data["elective_codes"] = seen
    if "skills" in data and data["skills"] is not None:
        # Skill tags are lower-cased on write, so "React " matches "react".
        data["skills"] = normalize_tags(data["skills"])

    for key, value in data.items():
        setattr(profile, key, value)

    session.add(profile)
    session.commit()
    session.refresh(profile)
    logger.info("Profile updated for user %s: %s", user.username, data)
    return _to_response(profile)


@router.post("/branch-change", response_model=BranchChangeResponse)
def request_branch_change(
    payload: BranchChangeRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Record a branch-change request.

    ``original_branch`` is set once, on the first request, so the student's
    admitted branch is preserved even after several changes.
    """
    profile = get_profile_for_user(session, user)

    target = normalize_branch(payload.to_branch)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown branch '{payload.to_branch}'. Choose one of {BRANCH_OPTIONS}.",
        )

    # A branch change stays inside the student's programme, so an MTech student
    # cannot request an undergraduate branch (and vice versa).
    allowed_branches = PROGRAMME_BRANCHES.get(profile.programme or "", tuple(BRANCH_OPTIONS))
    if target not in allowed_branches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Branch '{target}' is not available for "
                f"{profile.programme or 'your programme'}. "
                f"Choose one of {list(allowed_branches)}."
            ),
        )

    previous_branch = profile.branch
    source = payload.from_branch or previous_branch
    if source and normalize_branch(source) == target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target branch must differ.",
        )

    if not profile.original_branch:
        profile.original_branch = previous_branch

    now = datetime.utcnow()
    profile.branch_change_requested = True
    profile.requested_branch = target
    profile.branch_change_reason = payload.reason
    profile.branch_change_requested_at = now

    session.add(profile)
    session.commit()
    session.refresh(profile)

    logger.info(
        "Branch change requested by %s: %s -> %s", user.username, previous_branch, target
    )
    return BranchChangeResponse(
        message=f"Branch change requested: {previous_branch} -> {target}",
        original_branch=profile.original_branch,
        previous_branch=previous_branch,
        requested_branch=profile.requested_branch,
        branch_change_requested=profile.branch_change_requested,
        branch_changed_at=profile.branch_changed_at,
        branch_change_requested_at=profile.branch_change_requested_at,
    )


@router.delete("/branch-change", response_model=BranchChangeResponse)
def clear_branch_change(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Clear any pending branch-change request ("No branch change").

    The admitted ``original_branch`` and ``branch_changed_at`` history are kept.
    """
    profile = get_profile_for_user(session, user)

    previous_request = profile.requested_branch
    profile.branch_change_requested = False
    profile.requested_branch = None
    profile.branch_change_reason = None
    profile.branch_change_requested_at = None

    session.add(profile)
    session.commit()
    session.refresh(profile)

    logger.info("Branch change request cleared for %s", user.username)
    return BranchChangeResponse(
        message="No branch change recorded"
        + (f" (cleared pending request for {previous_request})" if previous_request else ""),
        original_branch=profile.original_branch,
        previous_branch=profile.branch,
        requested_branch=None,
        branch_change_requested=False,
        branch_changed_at=profile.branch_changed_at,
        branch_change_requested_at=None,
    )