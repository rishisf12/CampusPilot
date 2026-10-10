"""
How well are instructors parsed, and where does it fail?

Reports two different problems that look identical on screen:

  **missing** - no instructor at all
  **wrong**   - something that is not a person: "LAB", "VF" (visiting faculty),
               a room, a leftover of the course code

A document is internally consistent - the same course code is taught by the same
person all term - so a code whose instructor was read cleanly somewhere can fill
in the cells where the layout defeated the parser. That is the fix, and this tool
measures how much it would recover.

Usage:  python tools/audit_instructors.py [path-to-pdf]
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from features.timetable.parser import (  # noqa: E402
    _split_cell_entries,
    extract_tables_from_pdf,
    parse_day_section_timetable,
    split_slot_cell,
)

PDF = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF"

#: Not people. "LAB" is a room-ish label, "VF" is visiting faculty, "T MA" is a
#: mangled teaching-assistant entry, "STAFF" is a placeholder.
NOT_A_PERSON = {
    "LAB", "VF", "T MA", "STAFF", "TBA", "NONE", "NIL", "-", "TBD",
    "AO", "AV", "AP", "AS", "AB", "AG", "AC", "AM", "AR",
}


def main() -> int:
    tables = extract_tables_from_pdf(Path(PDF))
    slots, _ = parse_day_section_timetable(tables)

    total = len(slots)
    named = [s for s in slots if s["instructor"]]
    missing = [s for s in slots if not s["instructor"]]

    # Which raw cells fail, so the layout can be looked at rather than guessed at.
    failures = Counter()
    for table in tables:
        for row in table:
            for cell in row:
                for entry in _split_cell_entries(cell):
                    code, instructor, _room = split_slot_cell(entry)
                    if code and not instructor:
                        failures[entry] += 1

    # Instructor per course code: the document is consistent about this.
    by_code = defaultdict(Counter)
    for slot in named:
        by_code[slot["course_code"].upper()][slot["instructor"]] += 1

    consistent = {
        code: counter.most_common(1)[0][0]
        for code, counter in by_code.items()
        if len(counter) == 1
    }
    contested = {code: dict(c) for code, c in by_code.items() if len(c) > 1}

    print(f"slots                 : {total}")
    print(f"with an instructor    : {len(named)}  ({len(named) * 100 // max(total, 1)}%)")
    print(f"missing               : {len(missing)}  ({len(missing) * 100 // max(total, 1)}%)")
    print(f"distinct codes seen   : {len(by_code)}")
    print(f"codes with one name   : {len(consistent)}")
    print(f"codes with several    : {len(contested)}")

    print(f"\nvalues that are not people ({len(NOT_A_PERSON)} known):")
    junk = Counter()
    for slot in named:
        if slot["instructor"] in NOT_A_PERSON:
            junk[slot["instructor"]] += 1
    for name, count in junk.most_common():
        print(f"  {name:<8} {count:>4} slots")

    # How many of the missing ones could a code->instructor map recover?
    recoverable = 0
    unrecoverable = Counter()
    for slot in missing:
        code = slot["course_code"].upper()
        if code in consistent:
            recoverable += 1
        else:
            unrecoverable[code] += 1

    print(f"\nmissing, recoverable from the same code elsewhere: {recoverable}")
    print(f"missing, code never named anywhere            : {sum(unrecoverable.values())}")
    if unrecoverable:
        print("  " + ", ".join(f"{c} x{n}" for c, n in unrecoverable.most_common(12)))

    print(f"\nraw cells that yield no instructor ({len(failures)} distinct):")
    for entry, count in failures.most_common(18):
        code, _i, room = split_slot_cell(entry)
        print(f"  x{count}  {entry!r}  -> course={code or '-'} room={room or '-'}")

    if contested:
        print(f"\ncodes taught by more than one name ({len(contested)}):")
        for code, names in list(contested.items())[:10]:
            print(f"  {code:<10} {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
