"""What the timetable filter should show for a profile, and what it actually shows.

The Timetable tab claims "116 slots" for CSE A semester 5, but a direct read of
the grid says fewer. This compares the two so the gap is visible: which
semesters, branches and course codes are leaking through, and in what number.

Usage:
    python tools/check_timetable_filter.py [branch] [semester]
"""
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend" / "src"))

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"


def main() -> int:
    branch = sys.argv[1] if len(sys.argv) > 1 else "CSE A"
    semester = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    if not DB.is_file():
        print(f"no database at {DB}")
        return 1
    conn = sqlite3.connect(DB)
    total = conn.execute("SELECT COUNT(*) FROM timetable_slot").fetchone()[0]
    print(f"timetable_slot rows in total: {total}\n")

    print(f"profile: {branch}, semester {semester}\n")

    print("rows by semester:")
    for sem, count in sorted(Counter(r[0] for r in conn.execute(
            "SELECT semester FROM timetable_slot")).items()):
        print(f"  sem {sem}: {count}")

    print(f"\nrows in semester {semester}, by branch label:")
    rows = conn.execute(
        "SELECT branch_or_program, COUNT(*) FROM timetable_slot WHERE semester = ? "
        "GROUP BY branch_or_program ORDER BY COUNT(*) DESC",
        (semester,),
    ).fetchall()
    for label, count in rows:
        mark = ""
        if branch.split()[0].lower() == (label.split() or [""])[0].lower():
            mark = "  <- contains the profile branch"
        print(f"  {label:<24} {count:>4}{mark}")

    # The strict reading: the semester matches and the branch label is exactly the
    # profile's branch, or lists it among several that share the class.
    want = branch.split()[0].lower()
    exact = conn.execute(
        "SELECT COUNT(*) FROM timetable_slot WHERE semester = ? AND branch_or_program = ?",
        (semester, branch),
    ).fetchone()[0]
    shared = conn.execute(
        "SELECT COUNT(*) FROM timetable_slot WHERE semester = ? "
        "AND (',' || replace(branch_or_program, ' ', ',') || ',') LIKE ?",
        (semester, f"%,{want},%"),
    ).fetchone()[0]

    print(f"\nexact branch match        : {exact}")
    print(f"branch listed in label    : {shared}")
    print(f"semester-only (any branch): {conn.execute('SELECT COUNT(*) FROM timetable_slot WHERE semester = ?', (semester,)).fetchone()[0]}")

    print(f"\ncourse codes in semester {semester}, by branch label:")
    for label, count in Counter(
        (r[0], r[1]) for r in conn.execute(
            "SELECT branch_or_program, course_code FROM timetable_slot WHERE semester = ?",
            (semester,),
        )
    ).most_common(24):
        print(f"  {label[0]:<20} {label[1]:<12} {count}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
