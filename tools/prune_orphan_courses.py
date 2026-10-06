"""Report attendance courses that no longer exist in the timetable.

`sync_courses_from_timetable` only ever adds courses, so a code that a previous
parse produced wrongly stays in the database forever and keeps showing up in the
subject list. This lists the orphans so they can be reviewed before removal.
"""
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from features.exam.parser import is_open_elective  # noqa: E402

DB = REPO / "database" / "classpilot.db"

#: Extra courses are declared by the user, not derived from the timetable, so
#: they are never orphans.
EXTRA_LIKE = {"HS1001"}


def main() -> int:
    remove = "--remove" in sys.argv
    conn = sqlite3.connect(DB)

    orphans = conn.execute(
        """
        SELECT c.id, c.code, c.branch, c.semester, c.is_elective
        FROM course c
        LEFT JOIN timetable_slot t ON t.course_code = c.code
        WHERE t.course_code IS NULL
          AND c.is_extra = 0
        ORDER BY c.code
        """
    ).fetchall()

    print(f"courses with no timetable slot: {len(orphans)}\n")
    for row in orphans:
        code = row[1]
        # An elective nobody sits is still a real paper; flag rather than judge.
        kind = "elective" if row[4] or is_open_elective(code) else "core"
        print(f"  id={row[0]:<4} {code:<10} branch={str(row[2]):<12} sem={row[3]} ({kind})")

    if remove:
        print()
        removable = [row[0] for row in orphans if row[1] not in EXTRA_LIKE]
        for course_id in removable:
            conn.execute("DELETE FROM course WHERE id = ?", (course_id,))
        # Records for a deleted course would dangle, so clear them too.
        conn.execute(
            "DELETE FROM attendance_record WHERE course_id NOT IN (SELECT id FROM course)"
        )
        conn.commit()
        print(f"removed {len(removable)} orphan course(s) and any dangling records")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
