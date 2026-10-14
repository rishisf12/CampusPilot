"""Admin user-management service: queries + role changes."""
from typing import Optional
from sqlmodel import Session, delete, or_, select

from models import JoinRequest, Team, TeamMember, User, UserRole


def list_users(
    session: Session, search: Optional[str], role: Optional[str], page: int, size: int
) -> tuple[list[User], int]:
    stmt = select(User)
    if role in ("admin", "student"):
        want = UserRole.ADMIN if role == "admin" else UserRole.STUDENT
        stmt = stmt.where(User.role == want)
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
    return {
        "total": total,
        "admins": admins,
        "students": total - admins,
        "verified": verified,
    }


def to_public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "roll_number": user.roll_number,
        "role": user.role.value if isinstance(user.role, UserRole) else user.role,
        "is_email_verified": user.is_email_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def list_teams(
    session: Session, search: Optional[str], page: int, size: int
) -> tuple[list[dict], int]:
    stmt = select(Team)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Team.name.ilike(like), Team.description.ilike(like)))
    all_rows = session.exec(stmt).all()
    total = len(all_rows)
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
    for model in (TeamMember, JoinRequest):
        for row in session.exec(select(model).where(model.team_id == team_id)).all():
            session.delete(row)
    session.delete(team)
    session.commit()
    return True
