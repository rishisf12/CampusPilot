"""Admin routes: user list, role change, stats, teams moderation."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from core.audit import log_audit
from models import User, UserProfile
from features.admin import service

router = APIRouter(tags=["Admin"])


def user_role_before(session: Session, user_id: int) -> Optional[str]:
    """The role a user held before this change, for the audit trail.

    Read before the mutation so the log can say what changed rather than only
    what it became. Returns None when the user does not exist, which the caller
    already treats as a 404.
    """
    from sqlmodel import select

    user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        return None
    return getattr(user.role, "value", str(user.role))


class RoleBody(BaseModel):
    role: str


class SettingBody(BaseModel):
    value: object = None


@router.get("/users")
def admin_list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    category: Optional[str] = None,
    group: Optional[str] = None,
    programme: Optional[str] = None,
    batch_year: Optional[int] = None,
    branch: Optional[str] = None,
    semester: Optional[int] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    The user list, filtered.

    Every filter is optional and an unset one filters nothing. The
    categories are the ones an administrator thinks in: admins, faculty,
    students (undergraduate or postgraduate), class representatives.
    """
    page = max(1, page)
    size = max(1, min(size, 100))
    if category == "clubs":
        # There are no clubs to filter yet, and a list that quietly
        # answered with everything would be worse than one that says so.
        raise HTTPException(
            status_code=400,
            detail="Clubs are not available yet.",
        )
    if category and category not in service.USER_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category '{category}'. Use one of {list(service.USER_CATEGORIES)}.",
        )
    rows, total = service.list_users(
        session,
        search,
        role,
        page,
        size,
        category=category,
        group=group,
        programme=programme,
        batch_year=batch_year,
        branch=branch,
        semester=semester,
    )
    profiles = service.profiles_for(session, rows)
    return {
        "total": total,
        "page": page,
        "size": size,
        "users": [
            service.to_public(user, profiles.get(user.id)) for user in rows
        ],
    }


@router.get("/users/filters")
def admin_user_filters(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    The values the list can be filtered by.

    The branches and the semesters are the timetable's own lists, so the
    filter speaks the college's vocabulary. The batch years are the ones the
    accounts actually carry: a year nobody has recorded is a year that would
    match nobody.
    """
    from sqlmodel import select

    from features.exam.parser import BRANCH_OPTIONS, PROGRAMME_SEMESTERS

    profiles = session.exec(select(UserProfile)).all()
    batch_years = sorted(
        {p.batch_year for p in profiles if p.batch_year is not None}, reverse=True
    )
    semesters = sorted(
        {
            semester
            for programme_semesters in PROGRAMME_SEMESTERS.values()
            for semester in programme_semesters
        }
    )
    return {
        "batch_years": batch_years,
        "branches": list(BRANCH_OPTIONS),
        "semesters": semesters,
    }


class UserDetailsBody(BaseModel):
    """What the admin may correct about who a person is."""

    programme: Optional[str] = None
    semester: Optional[int] = None
    branch: Optional[str] = None
    section: Optional[str] = None
    batch_year: Optional[int] = None
    is_faculty: Optional[bool] = None
    is_class_representative: Optional[bool] = None


@router.patch("/users/{user_id}")
def admin_update_user(
    user_id: int,
    body: UserDetailsBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Correct who a person is: their programme, batch, class, and whether they
    are faculty or a class representative.

    A student may set their own branch and electives, but who represents a
    class and who teaches here is the college's call, so it is the admin's.
    """
    user = service.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    before = service.to_public(
        user, service.profiles_for(session, [user]).get(user.id)
    )

    if body.batch_year is not None and not 2000 <= body.batch_year <= 2100:
        raise HTTPException(status_code=400, detail="Batch year looks wrong.")

    updated_user = service.update_user_details(
        session,
        user_id,
        programme=body.programme,
        semester=body.semester,
        branch=body.branch,
        section=body.section,
        batch_year=body.batch_year,
        is_faculty=body.is_faculty,
        is_class_representative=body.is_class_representative,
    )
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    after = service.to_public(
        updated_user, service.profiles_for(session, [updated_user]).get(updated_user.id)
    )
    log_audit(
        session, actor=admin, action="user.details.change",
        target_type="user", target_id=str(user_id),
        before=before,
        after=after,
    )
    return after


@router.patch("/users/{user_id}/role")
def admin_set_role(
    user_id: int,
    body: RoleBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    if body.role not in ("admin", "student"):
        raise HTTPException(status_code=400, detail="role must be admin or student")
    if admin.id == user_id and body.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote yourself")
    before_role = user_role_before(session, user_id)
    user = service.set_role(session, user_id, body.role)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(
        session, actor=admin, action="user.role.change",
        target_type="user", target_id=str(user_id),
        before={"role": before_role},
        after={"role": body.role},
    )
    return service.to_public(user)


@router.get("/stats")
def admin_stats(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    return service.stats(session)


@router.get("/settings")
def admin_get_settings(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """All system settings as one flat object. Missing keys are simply
    absent - the Settings tab falls back to its own defaults, so a fresh
    install renders correctly with zero rows stored."""
    return service.get_settings_all(session)


@router.patch("/settings/{key}")
def admin_update_setting(
    key: str,
    body: SettingBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    return service.set_setting(session, key, body.value, updated_by=admin.id)


@router.get("/teams")
def admin_list_teams(
    search: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    teams, total = service.list_teams(session, search, page, size)
    return {"total": total, "page": page, "size": size, "teams": teams}


@router.delete("/teams/{team_id}", status_code=204)
def admin_delete_team(
    team_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    if not service.delete_team_any(session, team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    return
