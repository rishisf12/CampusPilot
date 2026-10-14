"""Promote an account to admin (developer use only).

Usage:
    python scripts/admin/make_admin.py <username-or-email>

Run from the CampusPilot directory.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend" / "app"))

from sqlmodel import select  # noqa: E402

from core.database import session_scope  # noqa: E402
from models import User, UserRole  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("Usage: python scripts/admin/make_admin.py <username-or-email>")
        return 2
    identity = sys.argv[1].strip()

    with session_scope() as session:
        user = session.exec(select(User).where(User.username == identity)).first()
        if user is None:
            user = session.exec(
                select(User).where(User.email == identity.lower())
            ).first()
        if user is None:
            print(f"No account found for {identity!r}.")
            return 1
        user.role = UserRole.ADMIN
        session.add(user)
        print(f"{user.username} ({user.email}) is now an admin. Sign in via the Admin role.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
