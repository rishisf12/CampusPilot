"""What is in the account tables right now, and what a reset would cost.

Run before any destructive change: this prints every table's row count and the
accounts that exist, so "reset the account database" is not taken on trust. The
timetable, exam seating and uploads live in the same file, and they are the
expensive part - they are listed too so the difference is visible.
"""
import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"

#: Tables that hold student sign-in data, as opposed to academic data.
ACCOUNT_TABLES = ["user", "user_profile", "passkey_credential", "password_reset_code"]

#: Academic data: the timetable and exams. Losing these means re-uploading.
ACADEMIC_TABLES = [
    "timetable_slot",
    "course",
    "attendance_record",
    "exam_seating",
    "mid_sem_schedule",
    "exam_upload",
    "timetable_upload",
    "room",
]


def main() -> int:
    if not DB.is_file():
        print(f"no database at {DB}")
        return 1

    # Refuse to touch anything reached through DATABASE_URL.
    if os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is set - this tool only reads the local file")
        return 1

    print(f"database: {DB.name}  ({DB.stat().st_size / 1024:.0f} KB)\n")

    conn = sqlite3.connect(DB)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    print("ACCOUNT DATA (sign-in)")
    for name in ACCOUNT_TABLES:
        if name not in tables:
            print(f"  {name:<24} -- table not present")
            continue
        print(f"  {name:<24} {conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]:>6} rows")

    print("\nACADEMIC DATA (timetable, exams)")
    for name in ACADEMIC_TABLES:
        if name not in tables:
            continue
        print(f"  {name:<24} {conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]:>6} rows")

    print("\nACCOUNTS")
    if "user" in tables:
        for row in conn.execute(
            "SELECT id, username, email, is_email_verified, password_changed_at "
            "FROM user ORDER BY id"
        ):
            verified = "verified" if row[3] else "UNVERIFIED"
            stamp = "pw reset" if row[4] else "-"
            print(f"  #{row[0]:<4} {row[1]:<20} {row[2]:<34} {verified:<10} {stamp}")

    print("\nPASSKEYS")
    if "passkey_credential" in tables:
        rows = conn.execute(
            "SELECT credential_id, user_id, label, last_used_at FROM passkey_credential"
        ).fetchall()
        if not rows:
            print("  none")
        for row in rows:
            used = row[3] or "never"
            print(f"  {row[0][:22]:<24} user={row[1]:<4} {row[2]:<16} last used {used}")
    else:
        print("  none")

    print("\nPENDING RESET CODES")
    if "password_reset_code" in tables:
        rows = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN used_at IS NULL THEN 1 ELSE 0 END) "
            "FROM password_reset_code"
        ).fetchone()
        print(f"  {rows[0]} total, {rows[1] or 0} unused")
    else:
        print("  none")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
