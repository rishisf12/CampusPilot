"""
Check what a password reset actually left behind.

Confirms the three consequences that matter, by looking at the API and the
database rather than at the UI that reported them:

- the new password works and the old one does not
- every passkey on the account is gone
- the password-change stamp is set, which is what invalidates old sessions
"""
import sqlite3
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"
BASE = "http://127.0.0.1:8001"
USERNAME = "testuser123"
NEW_PASSWORD = sys.argv[1] if len(sys.argv) > 1 else "Brand@New456"
OLD_PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "Test@12345"


def main() -> int:
    old = requests.post(
        BASE + "/auth/login", data={"username": USERNAME, "password": OLD_PASSWORD}
    )
    print(f"old password rejected : {old.status_code} (want 401)")

    new = requests.post(
        BASE + "/auth/login", data={"username": USERNAME, "password": NEW_PASSWORD}
    )
    print(f"new password accepted : {new.status_code} (want 200)")
    if new.status_code != 200:
        return 1

    headers = {"Authorization": "Bearer " + new.json()["access_token"]}
    keys = requests.get(BASE + "/auth/passkeys", headers=headers).json()
    print(f"passkeys remaining    : {keys['count']} (want 0)")

    conn = sqlite3.connect(DB)
    user_id = conn.execute(
        "SELECT id FROM user WHERE username = ?", (USERNAME,)
    ).fetchone()[0]
    stamped = conn.execute(
        "SELECT password_changed_at FROM user WHERE id = ?", (user_id,)
    ).fetchone()[0]
    print(f"password stamped      : {'yes' if stamped else 'NO'} ({stamped})")

    total, used = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN used_at IS NOT NULL THEN 1 ELSE 0 END) "
        "FROM password_reset_code WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    print(f"reset codes           : {total} total, {used} spent")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
