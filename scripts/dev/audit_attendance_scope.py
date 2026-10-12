"""
Does an attendance record belong to a student, or to a course?

`attendance_record` is the one table where a missing user reference would leak
one student's marks to another: if rows are keyed by course alone, then whoever
reads a subject's history sees everyone who ever marked it.

Prints the real columns and the queries that touch it, so the answer is read off
the code rather than assumed from the schema.

Usage:  python tools/audit_attendance_scope.py
"""
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"
BACKEND = REPO / "backend" / "backend"


def main() -> int:
    conn = sqlite3.connect(DB)

    print("attendance_record columns")
    for row in conn.execute("PRAGMA table_info(attendance_record)"):
        print(f"  {row[1]:<20} {row[2]}")

    cols = {row[1] for row in conn.execute("PRAGMA table_info(attendance_record)")}
    print(f"\nhas user_id: {'user_id' in cols}")
    print(f"has course_id: {'course_id' in cols}")

    print("\nAny rows sharing a course would be indistinguishable between students.")
    dupes = conn.execute(
        "SELECT course_id, COUNT(*) c FROM attendance_record "
        "GROUP BY course_id HAVING c > 1 LIMIT 5"
    ).fetchall()
    print(f"  courses with more than one record: {len(dupes)}")
    for course_id, count in dupes:
        print(f"    course_id={course_id} rows={count}")

    # Now the important part: does the read path filter by the signed-in user?
    print("\nqueries touching attendance_record")
    for path in sorted(BACKEND.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "AttendanceRecord" not in text:
            continue
        relative = path.relative_to(REPO)
        print(f"\n  {relative}")
        for match in re.finditer(
            r"(?:select\(AttendanceRecord\)|delete\(AttendanceRecord\))[^\n]*", text
        ):
            print(f"    {match.group(0).strip()[:150]}")
        for number, line in enumerate(text.splitlines(), 1):
            if "AttendanceRecord" in line and (
                "where" in line.lower() or "user" in line.lower()
            ):
                print(f"    L{number}: {line.strip()[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
