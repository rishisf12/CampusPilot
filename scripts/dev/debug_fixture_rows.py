"""Print what the parser makes of the test fixture table, row by row."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))
sys.path.insert(0, str(REPO / "backend" / "backend" / "tests"))

from features.timetable.parser import parse_day_section_timetable  # noqa: E402
from test_timetable_grid import DAY_SECTION_TABLE  # noqa: E402


def main() -> int:
    slots, warnings = parse_day_section_timetable([DAY_SECTION_TABLE])
    print("warnings:", warnings)
    print("count   :", len(slots))
    for s in slots:
        print(
            f"  {s['day']} {s['start_time']}-{s['end_time']} "
            f"{s['course_code']:<10} {str(s['instructor']):<6} "
            f"{s['room']:<9} {s['branch_or_program']} sem{s['semester']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
