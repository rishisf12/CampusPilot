"""Admin user-management service: queries + role changes."""
from datetime import datetime, timezone
from typing import Any, Optional
from sqlmodel import Session, or_, select

from models import JoinRequest, SystemSetting, Team, TeamMember, User, UserProfile, UserRole

#: The categories the admin's user list filters by.
#:
#: Students split the way an administrator thinks of them - undergraduate and
#: postgraduate - and PhD sits with the postgraduates here, even though
#: signup asks for Doctoral as a group of its own: this is a filter over who
#: is who, not a question about which groups the app bundles features by.
USER_FILTER_GROUPS: dict[str, tuple[str, ...]] = {
    "UG": ("BTech", "BDes"),
    "PG": ("MTech", "MDes", "PhD"),
}

#: Programmes with no batch year: a doctoral student joins no batch.
BATCHLESS_PROGRAMMES: tuple[str, ...] = ("PhD",)

#: The categories the list can be filtered by. "clubs" is not among them yet
#: - there are no clubs to filter - but the admin's screen says so rather
#: than hiding the option.
USER_CATEGORIES: tuple[str, ...] = (
    "admin",
    "faculty",
    "students",
    "cr",
)


def get_settings_all(session: Session) -> dict[str, Any]:
    """Every stored setting as a flat key/value object, exactly what the
    Settings tab renders. Unknown keys are returned too - the UI owns the
    key list, not the backend."""
    rows = session.exec(select(SystemSetting)).all()
    return {row.key: row.value for row in rows}


def set_setting(
    session: Session, key: str, value: Any, updated_by: Optional[int] = None
) -> dict[str, Any]:
    """Upsert one setting. Creates the key on first write so the UI never has
    to distinguish "new" from "changed"."""
    row = session.get(SystemSetting, key)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by=updated_by, updated_at=now)
    else:
        row.value = value
        row.updated_by = updated_by
        row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"key": row.key, "value": row.value}


def list_users(
    session: Session,
    search: Optional[str],
    role: Optional[str],
    page: int,
    size: int,
    category: Optional[str] = None,
    group: Optional[str] = None,
    programme: Optional[str] = None,
    batch_year: Optional[int] = None,
    branch: Optional[str] = None,
    semester: Optional[int] = None,
) -> tuple[list[User], int]:
    """
    The user list, filtered the way an administrator asks for it.

    The role column is the coarse cut ("admin" or "student"); the profile
    carries the rest - the programme, the batch year, the branch, the
    semester - and the two flags that say faculty and class representative.
    Every filter is optional, and an unset one filters nothing: the list
    starts as every account, not as the administrator's own batch.
    """
    stmt = select(User).outerjoin(UserProfile, UserProfile.user_id == User.id)
    if role in ("admin", "student"):
        want = UserRole.ADMIN if role == "admin" else UserRole.STUDENT
        stmt = stmt.where(User.role == want)
    if category == "admin":
        stmt = stmt.where(User.role == UserRole.ADMIN)
    elif category == "faculty":
        stmt = stmt.where(UserProfile.is_faculty.is_(True))
    elif category == "students":
        # The students: not the teaching staff. A class representative is a
        # student, so they are in here too.
        stmt = stmt.where(
            User.role == UserRole.STUDENT,
            UserProfile.is_faculty.is_(False),
        )
    elif category == "cr":
        stmt = stmt.where(UserProfile.is_class_representative.is_(True))

    programmes: Optional[tuple[str, ...]] = None
    if programme:
        programmes = (programme,)
    elif group:
        programmes = USER_FILTER_GROUPS.get(group.upper())
    if programmes is not None:
        stmt = stmt.where(UserProfile.programme.in_(programmes))
    if batch_year is not None:
        stmt = stmt.where(UserProfile.batch_year == batch_year)
    if branch:
        stmt = stmt.where(UserProfile.branch == branch)
    if semester is not None:
        stmt = stmt.where(UserProfile.semester == semester)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(like),
                User.username.ilike(like),
                User.full_name.ilike(like),
                User.roll_number.ilike(like),
            )
        )
    total = len(session.exec(stmt).all())
    rows = session.exec(stmt.order_by(User.id.desc()).offset((page - 1) * size).limit(size)).all()
    return rows, total


def get_user(session: Session, user_id: int) -> Optional[User]:
    """One user by id, or None."""
    return session.exec(select(User).where(User.id == user_id)).first()


def profiles_for(session: Session, users: list[User]) -> dict[int, UserProfile]:
    """The profiles of the given users, in one query."""
    if not users:
        return {}
    ids = [user.id for user in users]
    rows = session.exec(select(UserProfile).where(UserProfile.user_id.in_(ids))).all()
    return {row.user_id: row for row in rows}


def set_role(session: Session, user_id: int, role: str) -> Optional[User]:
    if role not in ("admin", "student"):
        return None
    user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        return None
    user.role = UserRole.ADMIN if role == "admin" else UserRole.STUDENT
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def stats(session: Session) -> dict:
    all_users = session.exec(select(User)).all()
    total = len(all_users)
    admins = sum(1 for u in all_users if (u.role.value if isinstance(u.role, UserRole) else u.role) == "admin")
    verified = sum(1 for u in all_users if u.is_email_verified)
    profiles = profiles_for(session, all_users)
    faculty = sum(1 for p in profiles.values() if p.is_faculty)
    representatives = sum(
        1 for p in profiles.values() if p.is_class_representative
    )
    return {
        "total": total,
        "admins": admins,
        "students": total - admins,
        "verified": verified,
        "faculty": faculty,
        "class_representatives": representatives,
    }


def to_public(user: User, profile: Optional[UserProfile] = None) -> dict:
    """
    A user as the admin's screens see them.

    The profile's own fields come with them: the admin's list filters on
    the programme, the batch, the branch and the semester, and a list that
    filters on fields it does not show is a list the admin cannot read.
    """
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "roll_number": user.roll_number,
        "role": user.role.value if isinstance(user.role, UserRole) else user.role,
        "is_email_verified": user.is_email_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "programme": profile.programme if profile else None,
        "semester": profile.semester if profile else None,
        "branch": profile.branch if profile else None,
        "section": profile.section if profile else None,
        "batch_year": profile.batch_year if profile else None,
        "is_faculty": bool(profile.is_faculty) if profile else False,
        "is_class_representative": (
            bool(profile.is_class_representative) if profile else False
        ),
    }


def update_user_details(
    session: Session,
    user_id: int,
    programme: Optional[str] = None,
    semester: Optional[int] = None,
    branch: Optional[str] = None,
    section: Optional[str] = None,
    batch_year: Optional[int] = None,
    is_faculty: Optional[bool] = None,
    is_class_representative: Optional[bool] = None,
) -> Optional[User]:
    """
    Set the fields that say who a person is.

    The admin is the one who can correct these: a student may set their own
    branch and electives, but who represents a class and who teaches here
    is the college's call. The profile is created if it is missing, so an
    account made outside signup can still be described.
    """
    user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        return None
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
    if programme is not None:
        profile.programme = programme
    if semester is not None:
        profile.semester = semester
    if branch is not None:
        profile.branch = branch
    if section is not None:
        profile.section = section
    if batch_year is not None:
        profile.batch_year = batch_year
    if is_faculty is not None:
        profile.is_faculty = is_faculty
    if is_class_representative is not None:
        profile.is_class_representative = is_class_representative
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return user


def list_teams(
    session: Session, search: Optional[str], page: int, size: int
) -> tuple[list[dict], int]:
    stmt = select(Team)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Team.name.ilike(like),
                Team.description.ilike(like),
            )
        )
    total = len(session.exec(stmt).all())
    rows = session.exec(stmt.order_by(Team.id.desc()).offset((page - 1) * size).limit(size)).all()
    out = []
    for t in rows:
        members = len(session.exec(select(TeamMember).where(TeamMember.team_id == t.id)).all())
        out.append(
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "owner_id": t.owner_id,
                "members": members,
                "max_members": t.max_members,
                "is_open": t.is_open,
                "hackathon_id": t.hackathon_id,
            }
        )
    return out, total


def delete_team_any(session: Session, team_id: int) -> bool:
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if team is None:
        return False
    for model in (JoinRequest, TeamMember):
        for row in session.exec(select(model).where(model.team_id == team_id)).all():
            session.delete(row)
    session.delete(team)
    session.commit()
    return True
