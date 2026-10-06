"""
Which tables are per-user, and which are shared?

Multi-user safety rests on one question per table: does a row belong to a person
or to everybody? A table that *should* be per-user but has no ``user_id`` is a
cross-tenant leak waiting to happen; a table that is *meant* to be shared but
gets filtered per-user makes the app look broken for everyone else.

Prints the schema's own answer rather than an assumed one, so a new table added
later cannot slip past unnoticed.

Usage:  python tools/audit_user_scoping.py
"""
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"

#: What each table is *for*. "shared" is correct for a master document; anything
#: marked per-user must have a user_id column to be safe.
INTENT = {
    # Identity, per user by nature.
    "user": "per-user",
    "user_profile": "per-user",
    "passkey_credential": "per-user",
    "password_reset_code": "per-user",
    "pending_signup": "not-yet-a-user",
    # One student's own marks.
    "attendance_record": "per-user",
    # Master documents: one for the whole college, deliberately shared.
    "timetable_slot": "shared",
    "timetable_upload": "shared",
    "exam_seating": "shared",
    "exam_upload": "shared",
    "mid_sem_schedule": "shared",
    "room": "shared",
    # The catalogue. Shared, but `is_extra` marks a row as one student's
    # opt-in, which is the interesting case - see the report below.
    "course": "shared-with-flag",
}


def main() -> int:
    if not DB.is_file():
        print(f"no database at {DB}")
        return 1

    conn = sqlite3.connect(DB)
    tables = [
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]

    problems = []
    print(f"{'table':<24} {'rows':>6}  {'user_id?':<9} intent")
    print("-" * 72)
    for name in tables:
        if name.startswith("sqlite_"):
            continue
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({name})")]
        count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        intent = INTENT.get(name, "UNKNOWN")
        has_user = "user_id" in columns
        print(f"{name:<24} {count:>6}  {'yes' if has_user else 'NO':<9} {intent}")

        if intent == "per-user" and not has_user:
            problems.append(f"{name}: marked per-user but has no user_id column")
        if intent == "UNKNOWN":
            problems.append(f"{name}: no declared intent - add it to this tool")

    # The subtle one: a shared table with a per-user flag on it.
    if "course" in tables:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(course)")]
        if "is_extra" in columns and "user_id" not in columns:
            problems.append(
                "course.is_extra marks a row as one student's opt-in, but the "
                "table has no user_id - so one student's extra course cannot be "
                "told apart from another's"
            )

    print()
    if problems:
        print("PROBLEMS:")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("every table's intent is satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
