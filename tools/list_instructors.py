"""List the instructor values the parser produced, so they can be eyeballed.

Instructor quality is easy to damage without noticing: a stricter name check
removes junk, but it can also silently remove real names. Printing the distinct
values is the only way to tell those apart - a count cannot.

Usage:  python tools/list_instructors.py [--missing]
"""
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"


def main() -> int:
    if not DB.is_file():
        print(f"no database at {DB}")
        return 1

    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT instructor, COUNT(*) FROM timetable_slot "
        "GROUP BY instructor ORDER BY COUNT(*) DESC, instructor"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM timetable_slot").fetchone()[0]
    conn.close()

    named = [(name, count) for name, count in rows if name]
    named_count = sum(count for _, count in named)

    print(f"{len(named)} distinct instructors across {named_count}/{total} slots\n")
    width = max((len(name) for name, _ in named), default=4)
    for name, count in named:
        print(f"  {name:<{width}}  {count}")

    if "--missing" in sys.argv:
        print("\nslots with no instructor, by course:")
        missing = Counter(
            code
            for (code,) in conn.execute(
                "SELECT course_code FROM timetable_slot "
                "WHERE instructor IS NULL OR instructor = ''"
            )
        )
        for code, count in missing.most_common(15):
            print(f"  {code:<12} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
