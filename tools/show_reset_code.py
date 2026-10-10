"""
Print the pending password-reset code for an account.

There is no mail server in local development, so a reset cannot be finished
through the UI without reading the code out of the database. This recovers it.

The code is stored hashed, which is the point of storing it hashed - so this
brute-forces the six digits. That is acceptable only because this is a local
development database the developer already owns; it would be meaningless against
a real deployment, where the code lives in the student's inbox instead.

Usage:  python tools/show_reset_code.py [username]
"""
import hashlib
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "testuser123"
    if not DB.is_file():
        print(f"no local database at {DB}")
        return 1

    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT id FROM user WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        print(f"no user named {username}")
        return 1
    user_id = row[0]

    rows = conn.execute(
        "SELECT id, code_hash, attempts, created_at FROM password_reset_code "
        "WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    if not rows:
        print(f"no pending reset code for {username}")
        return 1

    newest_id, newest_hash, attempts, created = rows[-1]
    print(f"{username}: {len(rows)} code(s); newest is #{newest_id}")
    print(f"  attempts used : {attempts}")
    print(f"  created at    : {created}")
    print(f"  used          : {'yes' if conn.execute('SELECT used_at FROM password_reset_code WHERE id=?', (newest_id,)).fetchone()[0] else 'no'}")

    for number in range(1000000):
        candidate = f"{number:06d}"
        if hashlib.sha256(f"{user_id}:{candidate}".encode()).hexdigest() == newest_hash:
            print(f"\n  code: {candidate}")
            return 0

    print("\n  no code matches the stored hash - it has expired")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
