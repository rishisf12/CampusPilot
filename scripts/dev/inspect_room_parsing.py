"""Show the cells the parser found hard, so the rules can be checked against them.

Room parsing is the weak spot: the grid writes "CR: 104", "CR 104", "CC-GF",
"CC 3F" and "CPPS Lab", and a value like "AUDITORIUM" is a room too. This prints
the entries whose room came out as TBA, with the original text beside them.
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
)

PDF = r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF"


def main() -> int:
    tables = extract_tables_from_pdf(Path(PDF))
    slots, _ = parse_day_section_timetable(tables)

    missing_room = [s for s in slots if s["room"] == "TBA"]
    print(f"slots with room=TBA: {len(missing_room)} / {len(slots)}\n")

    print("raw entries behind those (deduplicated):")
    seen = set()
    shown = 0
    for table in tables:
        for row in table:
            for cell in row:
                for entry in _split_cell_entries(cell):
                    if entry in seen:
                        continue
                    seen.add(entry)
                    # Reproduce the failure: a slot that lost its room.
                    from features.timetable.parser import split_slot_cell
                    code, _instructor, room = split_slot_cell(entry)
                    if code and not room:
                        print(f"  {entry!r}")
                        shown += 1
            if shown > 40:
                break

    print("\ncell fragments that look like rooms but were split apart:")
    for entry in sorted(seen):
        if re.search(r"\bCR\b|\bCC\b|GF|\dF\b|Lab|AUDITORIUM", entry, re.IGNORECASE):
            if len(entry) < 46:
                print(f"  {entry!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
