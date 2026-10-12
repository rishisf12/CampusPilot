"""
Show the raw timetable cells behind each room name.

Rooms are the field most likely to be mis-parsed, because the grid packs a room
into the same cell as a course and an instructor and writes it several ways
("CR-104", "CR: 104", "CC 3F", "C R 202"). A wrong room is invisible in the UI -
it just looks like a room nobody recognises - so this prints the original text
next to what the parser produced, room by room.

Usage:
    python tools/trace_rooms.py            # every distinct room, with an example
    python tools/trace_rooms.py CR-104     # only rooms matching a substring
"""
import re
import sys
from collections import defaultdict
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

#: Room shapes a human would not recognise as a room, so the output is worth
#: reading: "(C-1)" is a group marker, "R-202" came from "C R 202", "MAKE-5" is
#: a fragment of a word.
NOT_A_ROOM = re.compile(r"^\(|\bMAKE\b|^-?\d+F?$", re.IGNORECASE)


def looks_suspicious(room: str) -> bool:
    return bool(NOT_A_ROOM.search(room or "")) or room in ("TBA", "")


def main() -> int:
    wanted = sys.argv[1] if len(sys.argv) > 1 else ""

    tables = extract_tables_from_pdf(Path(PDF))
    slots, _ = parse_day_section_timetable(tables)

    # room -> the raw entries that produced it
    origin: dict = defaultdict(set)
    for table in tables:
        for row in table:
            for cell in row:
                for entry in _split_cell_entries(cell):
                    code, _instructor, room = split_slot_cell(entry)
                    if code and room:
                        origin[room].add(entry)

    counts: dict = defaultdict(int)
    for slot in slots:
        counts[slot["room"]] += 1

    rows = []
    for room, entries in origin.items():
        if wanted and wanted.lower() not in room.lower():
            continue
        # Suspicious ones first, then by how often they occur.
        rows.append((0 if looks_suspicious(room) else 1, -counts.get(room, 0), room, entries))
    rows.sort()

    current = None
    for flag, _neg, room, entries in rows:
        if flag != current:
            current = flag
            print("\n" + ("=" * 70))
            print("NEEDS REVIEW" if flag == 0 else "looks like a real room")
            print("=" * 70)
        sample = sorted(entries)[0]
        print(f"\n  {room:<14} {len(entries):>3} distinct cell(s)")
        for entry in sorted(entries)[:4]:
            code, instructor, got = split_slot_cell(entry)
            print(f"      {entry!r}")
            print(
                f"        -> course={code or '-':<10} instructor={instructor or '-':<6} room={got or 'TBA'}"
            )
        if len(entries) > 4:
            print(f"      ... and {len(entries) - 4} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
