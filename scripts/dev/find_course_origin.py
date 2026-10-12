"""Find where a suspicious course code came from in the stored timetable."""
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"

CODE = sys.argv[1] if len(sys.argv) > 1 else "OE3M"


def main() -> int:
    conn = sqlite3.connect(DB)

    in_slots = conn.execute(
        "SELECT COUNT(*) FROM timetable_slot WHERE course_code = ?", (CODE,)
    ).fetchone()[0]
    in_courses = conn.execute(
        "SELECT COUNT(*) FROM course WHERE code = ?", (CODE,)
    ).fetchone()[0]
    print(f"{CODE}: timetable_slot={in_slots} course={in_courses}")

    for row in conn.execute(
        "SELECT id, day, start_time, room, instructor, branch_or_program, semester "
        "FROM timetable_slot WHERE course_code = ? LIMIT 5",
        (CODE,),
    ):
        print("  slot:", row)

    for row in conn.execute(
        "SELECT id, code, name, branch, semester, is_elective, is_extra FROM course "
        "WHERE code = ? LIMIT 5",
        (CODE,),
    ):
        print("  course:", row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
