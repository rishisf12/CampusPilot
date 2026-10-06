"""
Compare the slots produced for a weekday against the raw cells that mention a course.

The parser reads one weekday section at a time, so a day can go quietly missing
without any error - the upload still succeeds with fewer slots. This counts the
raw cells naming each course and flags the ones that produced nothing, which is
the only way to tell "not scheduled that day" from "scheduled but not read".

Usage:  python tools/check_day_completeness.py [Mon|Tue|Wed|Thu|Fri|Sat|Sun]
        python tools/check_day_completeness.py --codes OE2C12 ME3011L
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from features.timetable.parser import (  # noqa: E402
    extract_tables_from_pdf,
    parse_day_section_timetable,
    split_slot_cell,
    _split_cell_entries,
)

PDF = r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF"

#: A course code as it appears in the grid: 2-4 letters, then digits, optionally
#: with a single trailing letter for a lab. Used to notice a damaged code that
#: slipped through as "E2N12" instead of "OE2N12".
CODE_IN_CELL = re.compile(
    r"\b((?:OE|OI)\d[A-Z]\d{2}|[A-Z]{2,4}\d{3,4}[A-Z]?)\b",
)


def main() -> int:
    args = sys.argv[1:]
    tables = extract_tables_from_pdf(Path(PDF))
    slots, _ = parse_day_section_timetable(tables)

    wanted_days = [a for a in args if not a.startswith("--")]
    codes_only = "--codes" in args
    if codes_only:
        wanted_codes = {c.upper() for c in args[args.index("--codes") + 1:]}
        wanted_days = []

    # Every distinct code the parser produced, with the days it landed on.
    produced = defaultdict(set)
    for slot in slots:
        produced[slot["course_code"].upper()].add(slot["day"])

    # Every code the raw cells name, with the day section each cell sits in.
    # A day section is identified by the slot day the parser assigned to the
    # table row, so instead we key on the produced slots for that table row and
    # fall back to reporting the cell text.
    mentions = defaultdict(list)
    for page_index, table in enumerate(tables, 1):
        for row_index, row in enumerate(table):
            for col_index, cell in enumerate(row):
                for match in CODE_IN_CELL.finditer((cell or "").upper()):
                    mentions[match.group(1)].append((page_index, row_index, col_index))

    report = []
    for code, where in sorted(mentions.items()):
        missing = [w for w in where if not produced.get(code)]
        if missing:
            report.append((code, len(where), missing))

    print(f"parsed {len(slots)} slots over "
          f"{sorted({s['day'] for s in slots})}")
    print(f"{len(produced)} distinct codes produced, "
          f"{len(mentions)} named in the raw cells")

    if wanted_days:
        print(f"\n--- slots per day, requested {wanted_days} ---")
        for day in wanted_days:
            day_slots = [s for s in slots if s["day"] == day]
            sems = sorted({s["semester"] for s in day_slots})
            print(f"  {day}: {len(day_slots)} slots, semesters {sems}")
            for sem in sems:
                rows = [s for s in day_slots if s["semester"] == sem]
                print(f"      sem {sem}: {len(rows)} slots, "
                      f"courses {sorted({r['course_code'] for r in rows})}")

    print(f"\n--- codes named in the grid but never produced "
          f"({len(report)}) ---")
    for code, total, missing in report:
        print(f"  {code}: named in {total} cell(s), 0 slots produced")
        for page, row, col in missing[:4]:
            print(f"      page {page} row {row} col {col}")

    if wanted_codes:
        print(f"\n--- requested codes {sorted(wanted_codes)} ---")
        for code in sorted(wanted_codes):
            days = sorted(produced.get(code, set()))
            print(f"  {code}: {len(days)} day(s) -> {days or 'NOT PRODUCED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
