"""Remove a single account and everything hanging off it.

Useful after testing the signup flow, which leaves an unverified account behind.
Only the named account is touched; timetable, exams and other students are not.

Usage:  python tools/delete_account.py <username>
"""
import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"

#: Removed with the account: anything referencing user_id, then the user itself.
OWNED_TABLES = [
    "password_reset_code",
    "passkey_credential",
    "user_profile",
]


def main() -> int:
    if not DB.is_file():
        print(f"no database at {DB}")
        return 1
    if os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is set - refusing to edit the file database")
        return 1
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    username = sys.argv[1].strip()
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT id, email FROM user WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        print(f"no account named {username}")
        return 1
    user_id, email = row

    conn.execute("DELETE FROM user_profile WHERE user_id = ?", (user_id,))
    for table in ("password_reset_code", "passkey_credential"):
        if table in {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }:
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM user WHERE id = ?", (user_id,))
    conn.commit()

    remaining = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
    print(f"removed {username} <{email}>")
    print(f"accounts remaining: {remaining}")

    # Academic data is untouched; confirm rather than assume.
    slots = conn.execute("SELECT COUNT(*) FROM timetable_slot").fetchone()[0]
    print(f"timetable slots still present: {slots}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
