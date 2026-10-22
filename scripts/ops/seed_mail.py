"""
Seed the mail app: sections, demo clusters and a sample user per role.

Run from the repository root:

    python scripts/ops/seed_mail.py

Safe to run again: everything is looked up first.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend" / "app"
sys.path.insert(0, str(BACKEND))

from sqlmodel import Session, select  # noqa: E402

from core.database import create_db_and_tables, engine  # noqa: E402
from models import User, UserProfile, UserRole  # noqa: E402
from features.mail import seed as mail_seed  # noqa: E402
from features.auth.routes import create_access_token  # noqa: E402

SAMPLE_USERS = (
    {
        "username": "mailadmin",
        "email": "mailadmin@iiitdmj.ac.in",
        "full_name": "Mail Admin",
        "role": UserRole.ADMIN,
        "programme": "BTech",
        "sections": ("academics", "placement", "cultural", "technical", "sports"),
        "can_manage": True,
    },
    {
        "username": "mailsection",
        "email": "mailsection@iiitdmj.ac.in",
        "full_name": "Placement Moderator",
        "role": UserRole.STUDENT,
        "programme": "BTech",
        "sections": ("placement",),
        "can_manage": True,
    },
    {
        "username": "mailstudent",
        "email": "mailstudent@iiitdmj.ac.in",
        "full_name": "Mail Student",
        "role": UserRole.STUDENT,
        "programme": "BTech",
        "sections": (),
        "can_manage": False,
    },
)


def ensure_user(session: Session, spec: dict) -> User:
    """One account, created if it is not there yet."""
    user = session.exec(select(User).where(User.username == spec["username"])).first()
    if user is None:
        user = User(
            email=spec["email"],
            password_hash="not-a-real-password",
            full_name=spec["full_name"],
            username=spec["username"],
            roll_number=None,
            is_email_verified=True,
            role=spec["role"],
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).first()
    if profile is None and spec.get("programme"):
        session.add(
            UserProfile(
                user_id=user.id,
                programme=spec["programme"],
                semester=1,
                branch="CSE A",
            )
        )
        session.commit()
    return user


def main() -> int:
    os.environ.setdefault("DATABASE_URL", "sqlite:///classpilot.db")
    create_db_and_tables()
    with Session(engine) as session:
        summary = mail_seed.seed_all(session)
        print("sections:", summary["sections"])
        print("demo clusters created:", summary["clusters"])
        for spec in SAMPLE_USERS:
            user = ensure_user(session, spec)
            if spec["sections"]:
                granted = mail_seed.grant_section_access(
                    session,
                    user.id,
                    list(spec["sections"]),
                    can_manage=spec["can_manage"],
                )
                print(f"{spec['username']}: {granted} section(s) granted")
            else:
                print(f"{spec['username']}: ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
