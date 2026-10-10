"""Check the exact cells that produced each disputed room, before and after.

Each pair is the raw text from the timetable and what it should mean. These are
the cases where the parser was confidently wrong, so they are asserted one by one
rather than checked in bulk - a room is only obvious as wrong when you know what
the grid actually said.

Run:  python tools/check_room_fixes.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from features.timetable.parser import split_slot_cell  # noqa: E402

#: (raw cell, expected course, expected instructor, expected room, what was wrong)
CASES = [
    # A group marker in parentheses is not a room.
    ("IT2E01-SKT-CC-FF (C1)", "IT2E01", "SKT", "CC-FF", "'(C-1)' was taken as the room"),
    (
        "EC2002L-TK-(C2) /IT2002-VF-CC-GF (C1)",
        "EC2002L",
        None,
        None,
        "two papers in one cell, both markers stripped",
    ),
    # A garbled cell must not invent a building or an instructor.
    ("EC5M03-MAKE-5", "EC5M03", "", "", "'MAKE-5' was read as a room"),
    # Lab groups are not rooms.
    ("ES1002L-PKP-A1", "ES1002L", "PKP", "", "'A-1' is a lab group"),
    ("ES1002L-PR-B1", "ES1002L", "PR", "", "'B-1' is a lab group"),
    ("IT3E01-KD-G1", "IT3E01", "KD", "", "'G-1' is a lab group"),
    # The building written with a space between its letters.
    ("OE4L73-JAMF- C R 202", "OE4L73", "JAMF", "CR-202", "'R-202' had lost its C"),
    # Instructor followed by a bare room number.
    ("OE4E21-SKJ- 101", "OE4E21", "SKJ", "", "'SKJ-101' had swallowed the instructor"),
    # A floor written before its building.
    ("IT1002L-AV-2F-CC", "IT1002L", "AV", "CC-2F", "'AV-2F' used the instructor as a building"),
    # A trailing floor belongs to the room before it.
    # A trailing floor belongs to the room before it. The room keeps the house
    # style: "CC2" normalises to "CC-2", so "CC2-GF" reads as "CC-2-GF".
    ("SM3010L-ARR-Batch A -CC2- GF", "SM3010L", None, "CC-2-GF", "'GF' was dropped as an instructor"),
    # Already-correct shapes that must not regress.
    ("CS8028-NA-CC 2F", "CS8028", "NA", "CC-2F", "floor + building"),
    ("NS1002-MKR-L102", "NS1002", "MKR", "L-102", "the plain case"),
    ("HS 1001 -MA- L106", "HS1001", "MA", "L-106", "spaced course code"),
    ("IT2001-SKM-CC-3F", "IT2001", "SKM", "CC-3F", "hyphenated floor"),
    ("CS8007-AnS (VF)-L107", "CS8007", "AnS", "L-107", "role marker after the instructor"),
    ("OE3: CS8016-BiG (VF)-L107", "CS8016", "BiG", "L-107", "group label and marker"),
    ("ME3001-SKC-CR-208", "ME3001", "SKC", "CR-208", "hyphenated classroom"),
    ("ES1003:LAB: AUDITORIUM", "ES1003", "LAB", "AUDITORIUM", "named venue"),
    ("EC5C01-SKC-L102", "EC5C01", "SKC", "L-102", "letter inside the code"),
    ("OE3E33-SKC-L202", "OE3E33", "SKC", "L-202", "open elective"),
]


def main() -> int:
    failures = 0
    for cell, want_course, want_instructor, want_room, note in CASES:
        course, instructor, room = split_slot_cell(cell)

        problems = []
        if want_course is not None and course != want_course:
            problems.append(f"course {course!r} != {want_course!r}")
        if want_instructor is not None and instructor != want_instructor:
            problems.append(f"instructor {instructor!r} != {want_instructor!r}")
        # None means "do not care"; "" means "must be empty".
        if want_room is not None and room != want_room:
            problems.append(f"room {room!r} != {want_room!r}")

        if problems:
            failures += 1
            print(f"FAIL  {cell!r}")
            print(f"      {'; '.join(problems)}")
            print(f"      ({note})")
        else:
            shown = f"{course or '-'} / {instructor or '-'} / {room or 'TBA'}"
            print(f"ok    {cell!r}")
            print(f"      -> {shown}")

    print()
    if failures:
        print(f"{failures} of {len(CASES)} still wrong")
        return 1
    print(f"all {len(CASES)} cases correct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
