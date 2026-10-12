"""
Re-upload the class timetable PDF and report what changed.

The room and instructor rules have been corrected, so the stored timetable still
holds the old mis-parsed values until the file is uploaded again. This uploads it
and prints the before/after so the effect of a parser change is visible rather
than assumed.

Upload is unauthenticated in this backend (a separate, already-reported issue),
so this needs no account.

Usage:  python tools/reupload_timetable.py [path-to-pdf]
"""
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

DB = REPO / "database" / "classpilot.db"
BASE = "http://127.0.0.1:8001"
PDF = Path(
    sys.argv[1] if len(sys.argv) > 1
    else r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF"
)

#: Values that are not rooms, and should not survive a parse.
NOT_ROOMS = {
    "(C-1)", "(C-2)", "A-1", "B-1", "B-2", "G-1", "G-2",
    "MAKE-5", "R-202", "SKJ-101", "AV-2F", "CC-2",
}


def snapshot():
    if not DB.is_file():
        return {}
    conn = sqlite3.connect(DB)
    rows = dict(conn.execute("SELECT room, COUNT(*) FROM timetable_slot GROUP BY room"))
    conn.close()
    return rows


def main() -> int:
    if not PDF.is_file():
        print(f"no file at {PDF}")
        return 1

    before = snapshot()
    print(f"before: {sum(before.values())} slots, {len(before)} distinct rooms")

    with PDF.open("rb") as handle:
        upload = requests.post(
            BASE + "/timetable/upload",
            files={"file": (PDF.name, handle, "application/pdf")},
        )
    if upload.status_code != 200:
        print(f"upload failed: {upload.status_code} {upload.text[:300]}")
        return 1
    print(f"upload: {upload.status_code}, {upload.json().get('slots_inserted')} slots inserted\n")

    after = snapshot()

    print("rooms that disappeared (the bad ones):")
    for room in sorted(set(before) - set(after)):
        print(f"  - {room:<14} {before[room]:>4} slots")

    print("\nrooms that appeared:")
    for room in sorted(set(after) - set(before)):
        print(f"  + {room:<14} {after[room]:>4} slots")

    print(f"\nbefore: {sum(before.values())} slots, {len(before)} distinct rooms")
    print(f"after : {sum(after.values())} slots, {len(after)} distinct rooms")

    survivors = sorted(set(after) & NOT_ROOMS)
    if survivors:
        print(f"\nWARNING: still present: {survivors}")

    print(f"\nall rooms now ({len(after)}):")
    for room, count in sorted(after.items(), key=lambda kv: -kv[1]):
        flag = "  <- not a room" if room in NOT_ROOMS else ""
        print(f"  {room:<14} {count:>4}{flag}")

    # Instructors matter as much as rooms: a rule change can cost them too.
    conn = sqlite3.connect(DB)
    total, named = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN instructor IS NOT NULL AND instructor != '' THEN 1 ELSE 0 END) "
        "FROM timetable_slot"
    ).fetchone()
    rooms = conn.execute(
        "SELECT COUNT(*) FROM timetable_slot WHERE room IS NOT NULL AND room NOT IN ('TBA', '')"
    ).fetchone()[0]
    conn.close()
    print(f"\ninstructor recorded : {named}/{total}")
    print(f"room recorded        : {rooms}/{total}  (was {sum(v for k, v in before.items() if k not in ('TBA', ''))}/{sum(before.values())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
