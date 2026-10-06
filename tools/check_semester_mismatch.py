"""Compare a slot's semester/branch with the course row synced from it.

`sync_courses_from_timetable` infers a course's semester and branch from the
course *code* when creating it, which can disagree with the semester the grid
puts the class in. `get_subjects` then filters on the course's values, so a class
the student genuinely sits can be hidden. This shows the disagreements.
"""
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"


def main() -> int:
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """
        SELECT t.course_code,
               t.semester       AS slot_sem,
               t.branch_or_program,
               co.semester      AS course_sem,
               co.branch        AS course_branch
        FROM timetable_slot t
        LEFT JOIN course co ON co.code = t.course_code
        WHERE co.id IS NOT NULL
        GROUP BY t.course_code
        HAVING slot_sem IS NOT course_sem
        ORDER BY t.course_code
        """
    ).fetchall()

    print(f"courses whose inferred semester differs from the grid's: {len(rows)}\n")
    for code, slot_sem, slot_branch, course_sem, course_branch in rows[:20]:
        print(
            f"  {code:<10} grid={slot_sem} sem / {str(slot_branch):<14} "
            f"course row={course_sem} sem / {course_branch}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
