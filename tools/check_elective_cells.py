"""
How many cells mention a course code, versus how many slots came out?

An elective sits in a column shared by every branch of its semester, so the
parser has to read rows whose leading cell names no branch the student cares
about. This counts the raw cells that mention a code and compares that with the
slots produced, which is the only way to tell "not scheduled that day" from
"scheduled but not read".

Usage:  python tools/check_elective_cells.py OE2C12 [more codes...]
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from features.timetable.parser import (  # noqa: E402
    _split_cell_entries,
    extract_tables_from_pdf,
    parse_day_section_timetable,
    split_slot_cell,
)

PDF = r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF"
WANTED = [c.upper() for c in (sys.argv[1:] or ["OE2C12"])]


def main() -> int:
    tables = extract_tables_from_pdf(Path(PDF))
    slots, _ = parse_day_section_timetable(tables)

    for code in WANTED:
        mentions = []
        for page_index, table in enumerate(tables, 1):
            for row_index, row in enumerate(table):
                for col_index, cell in enumerate(row):
                    if code in (cell or "").upper():
                        mentions.append((page_index, row_index, col_index, cell))

        produced = [s for s in slots if s["course_code"].upper() == code]

        print(f"\n{'=' * 66}")
        print(f"{code}: mentioned in {len(mentions)} cell(s), "
              f"{len(produced)} slot(s) produced")
        print("=" * 66)

        for page, row_i, col_i, cell in mentions:
            entries = _split_cell_entries(cell)
            parsed = [split_slot_cell(e) for e in entries]
            codes = [p[0] for p in parsed if p[0]]
            produced_here = code in [c.upper() for c in codes]
            print(f"\n  page {page} row {row_i} col {col_i}: {cell[:80]!r}")
            print(f"    -> entries={entries}")
            print(f"    -> parsed codes={codes}")
            if not produced_here:
                print("    ** this cell mentions the code but produced no slot **")

        print(f"\n  resulting slots:")
        for slot in produced:
            print(f"    {slot['day']} {slot['start_time']} "
                  f"branch={slot['branch_or_program']} sem={slot['semester']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
