"""Reset the demo account's password so the local demo login keeps working.

Only for a local SQLite development database. Refuses to run against anything
that is not a local file, and refuses if the account does not exist.
"""
import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"

sys.path.insert(0, str(REPO / "backend" / "backend"))
from features.auth.routes import hash_password  # noqa: E402


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "testuser123"
    password = sys.argv[2] if len(sys.argv) > 2 else "Test@12345"

    if not DB.is_file():
        print(f"no local database at {DB}")
        return 1
    # Local development only: a real deployment uses a different DATABASE_URL.
    if os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is set - refusing to edit the file database")
        return 1
    if DB.suffix != ".db":
        print(f"refusing to touch {DB.name}, which is not a SQLite database")
        return 1

    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT id FROM user WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        print(f"no user named {username}")
        return 1

    conn.execute(
        "UPDATE user SET password_hash = ?, is_email_verified = 1 WHERE username = ?",
        (hash_password(password), username),
    )
    conn.commit()
    print(f"password reset for {username}; email marked verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
