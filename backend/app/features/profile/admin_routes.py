"""The administrator's own profile: an operator's, not a student's.

The student profile is a roll number, a branch and a set of electives. None
of that describes an administrator, and none of it belongs on their screen.

This module adds the admin's own surface:

- `GET /profile/admin` - their profile, their console preferences, their
  notification routing and their account state. **Only their own**: no
  student data, no other operator's data.
- `PUT /profile/admin` - update it.
- `GET /profile/admin/activity` - their own recent actions, from the audit
  trail, scoped to their user id.

The admin's view of *other* people is a different screen on purpose (User
360): an operator looking at a student is doing a task, not reading their
own profile.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from core.database import get_session
from core.deps import get_current_admin
from models import AdminProfile, AuditLog, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Profile"])

#: The console's own vocabulary. A value outside these is a typo, not a
# preference, and is refused rather than stored.
THEMES = ("system", "light", "dark")
DENSITIES = ("comfortable", "compact")
NOTIFY_CHANNELS = ("email", "telegram", "webhook")
SUBSECTIONS = (
    "A_W_HEALTH",
    "B_W_ACTIVITY",
    "C_W_SECURITY",
    "D_W_FEEDBACK",
    "A_A_HEALTH",
    "B_A_ACTIVITY",
    "C_A_SECURITY",
    "D_A_FEEDBACK",
)


class AdminProfileUpdate(BaseModel):
    """The parts of an administrator's profile they may change."""

    display_name: Optional[str] = Field(default=None, max_length=120)
    job_title: Optional[str] = Field(default=None, max_length=120)
    team: Optional[str] = Field(default=None, max_length=120)
    timezone: Optional[str] = Field(default=None, max_length=64)
    locale: Optional[str] = Field(default=None, max_length=16)
    theme: Optional[str] = Field(default=None, max_length=16)
    density: Optional[str] = Field(default=None, max_length=16)
    default_subsection: Optional[str] = Field(default=None, max_length=32)
    default_window_days: Optional[int] = Field(default=None, ge=1, le=90)
    pinned_panels: Optional[List[str]] = None
    notify_email: Optional[str] = Field(default=None, max_length=255)
    notify_channels: Optional[List[str]] = None
    quiet_hours: Optional[dict] = None
    notes: Optional[str] = None


class AdminActivityItem(BaseModel):
    """One of the administrator's own actions."""

    id: int
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    at: Optional[datetime] = None


class AdminProfileResponse(BaseModel):
    """The administrator's own profile, and nothing of anybody else's."""

    id: int
    user_id: Optional[int] = None
    email: str
    role: str
    display_name: Optional[str] = None
    job_title: Optional[str] = None
    team: Optional[str] = None
    timezone: str
    locale: str
    theme: str
    density: str
    default_subsection: Optional[str] = None
    default_window_days: int
    pinned_panels: List[str] = []
    notify_email: Optional[str] = None
    notify_channels: List[str] = []
    quiet_hours: dict = {}
    notes: Optional[str] = None
    #: Their account's own state: when it was created, whether a passkey is on
    #: the account, and how many of their own actions are in the trail.
    account_created_at: Optional[datetime] = None
    passkey_registered: bool = False
    own_action_count: int = 0
    recent_actions: List[AdminActivityItem] = []


def _get_admin_profile(session: Session, user: User) -> AdminProfile:
    """Their profile row, created on first sight."""
    profile = session.exec(
        select(AdminProfile).where(AdminProfile.user_id == user.id)
    ).first()
    if profile is None:
        profile = AdminProfile(
            user_id=user.id,
            display_name=user.full_name or user.email,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def _own_actions(
    session: Session, user: User, limit: int = 25
) -> List[AuditLog]:
    """The administrator's own actions, newest first."""
    return list(
        session.exec(
            select(AuditLog)
            .where(AuditLog.actor_id == user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        ).all()
    )


def _has_passkey(session: Session, user: User) -> bool:
    try:
        from models import PasskeyCredential

        return (
            session.exec(
                select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
            ).first()
            is not None
        )
    except Exception:  # noqa: BLE001 - the table may not be there yet
        return False


@router.get("/admin", response_model=AdminProfileResponse)
def get_admin_profile(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """The administrator's own profile, console setup and recent activity."""
    profile = _get_admin_profile(session, admin)
    actions = _own_actions(session, admin)
    own_count = session.exec(
        select(AuditLog).where(AuditLog.actor_id == admin.id)
    ).all()
    return AdminProfileResponse(
        id=profile.id or 0,
        user_id=profile.user_id,
        email=admin.email,
        role=admin.role or "admin",
        display_name=profile.display_name,
        job_title=profile.job_title,
        team=profile.team,
        timezone=profile.timezone,
        locale=profile.locale,
        theme=profile.theme,
        density=profile.density,
        default_subsection=profile.default_subsection,
        default_window_days=profile.default_window_days,
        pinned_panels=list(profile.pinned_panels or []),
        notify_email=profile.notify_email,
        notify_channels=list(profile.notify_channels or []),
        quiet_hours=dict(profile.quiet_hours or {}),
        notes=profile.notes,
        account_created_at=getattr(admin, "created_at", None),
        passkey_registered=_has_passkey(session, admin),
        own_action_count=len(own_count),
        recent_actions=[
            AdminActivityItem(
                id=row.id,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                at=row.created_at,
            )
            for row in actions
        ],
    )


@router.put("/admin", response_model=AdminProfileResponse)
def update_admin_profile(
    payload: AdminProfileUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Update the administrator's own profile."""
    profile = _get_admin_profile(session, admin)
    data = payload.model_dump(exclude_unset=True)

    if "theme" in data and data["theme"] is not None:
        if data["theme"] not in THEMES:
            raise HTTPException(
                status_code=422,
                detail=f"theme must be one of {list(THEMES)}",
            )
    if "density" in data and data["density"] is not None:
        if data["density"] not in DENSITIES:
            raise HTTPException(
                status_code=422,
                detail=f"density must be one of {list(DENSITIES)}",
            )
    if "default_subsection" in data and data["default_subsection"] is not None:
        if data["default_subsection"] not in SUBSECTIONS:
            raise HTTPException(
                status_code=422,
                detail=f"default_subsection must be one of {list(SUBSECTIONS)}",
            )
    if "default_window_days" in data and data["default_window_days"] is not None:
        if not 1 <= int(data["default_window_days"]) <= 90:
            raise HTTPException(
                status_code=422, detail="default_window_days must be 1..90"
            )
    if "notify_channels" in data and data["notify_channels"] is not None:
        unknown = [c for c in data["notify_channels"] if c not in NOTIFY_CHANNELS]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"unknown notify channel(s) {unknown}; allowed: {list(NOTIFY_CHANNELS)}",
            )

    for field, value in data.items():
        setattr(profile, field, value)
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return get_admin_profile(session=session, admin=admin)


@router.get("/admin/activity", response_model=List[AdminActivityItem])
def get_admin_activity(
    limit: int = 25,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """The administrator's own recent actions - and only their own."""
    limit = max(1, min(int(limit), 200))
    return [
        AdminActivityItem(
            id=row.id,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            at=row.created_at,
        )
        for row in _own_actions(session, admin, limit=limit)
    ]
