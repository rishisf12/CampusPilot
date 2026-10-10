"""Parse the real class timetable PDF and summarise what was read.

Confirms the day-section parser against the published document: how many slots,
which days, semesters, branches, and whether course / instructor / room came out
of the packed cells.
"""
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from features.timetable.parser import parse_timetable_file  # noqa: E402

DEFAULT_PDF = r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF"


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF)
    result = parse_timetable_file(path)
    slots = result["slots"]

    print(f"file      : {path.name}")
    print(f"slots     : {len(slots)}")
    print(f"warnings  : {result['warnings'][:4]}")

    print("\nby day")
    for day, count in Counter(s["day"] for s in slots).items():
        print(f"  {day}: {count}")

    print("\nby semester")
    for sem, count in sorted(Counter(s["semester"] for s in slots).items()):
        print(f"  sem {sem}: {count}")

    print("\nby branch")
    for branch, count in Counter(s["branch_or_program"] for s in slots).most_common(14):
        print(f"  {branch:<22} {count}")

    print("\nfield quality")
    with_instructor = sum(1 for s in slots if s["instructor"])
    with_real_room = sum(1 for s in slots if s["room"] not in ("TBA", ""))
    print(f"  instructor parsed : {with_instructor}/{len(slots)}")
    print(f"  room parsed      : {with_real_room}/{len(slots)}")

    print("\nfirst 15 slots")
    for s in slots[:15]:
        print(
            f"  {s['day']} {s['start_time']}-{s['end_time']} "
            f"{s['course_code']:<10} {str(s['instructor']):<8} "
            f"{s['room']:<10} {s['branch_or_program']} sem{s['semester']}"
        )

    # A CSE A sem 5 student is the demo profile: show only what they would sit.
    # A combined label like "CSE ECE" counts, because those rows are shared.
    print("\nCSE A sem 5 (demo profile), per weekday")
    mine = [
        s for s in slots
        if "CSE" in s["branch_or_program"].split() and s["semester"] == 5
    ]
    for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat"):
        todays = [s for s in mine if s["day"] == day]
        if not todays:
            continue
        print(f"  {day}")
        for s in sorted(todays, key=lambda x: x["start_time"]):
            print(
                f"    {s['start_time']}-{s['end_time']} {s['course_code']:<10} "
                f"{str(s['instructor']):<8} {s['room']:<10} [{s['branch_or_program']}]"
            )
    print(f"  -> {len(mine)} slot(s)")

    return 0 if slots else 1


if __name__ == "__main__":
    raise SystemExit(main())
