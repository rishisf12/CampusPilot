"""Admin user-management service: queries + role changes."""
from typing import Optional
from sqlmodel import Session, delete, or_, select

from models import User, UserRole


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
