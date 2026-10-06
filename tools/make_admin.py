"""
Promote an account to admin (developer use only).

The admin login is the same username + password sign-in; the role is what opens
the admin panel. Student signup can never set a role, so this script is the
only way an admin comes to exist.

Usage:
    python tools/make_admin.py <username-or-email>

Run from the CampusPilot directory. The script finds the account in the local
SQLite database and stamps role="admin".
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from sqlmodel import select  # noqa: E402

from core.database import session_scope  # noqa: E402
from models import User  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("Usage: python tools/make_admin.py <username-or-email>")
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
        user.role = "admin"
        session.add(user)
        print(f"{user.username} ({user.email}) is now an admin. Sign in via the Admin role.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
