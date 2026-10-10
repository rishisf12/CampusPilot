"""Inspect the day-section layout of the real class timetable.

The published grid is organised as one *section* per weekday rather than one
column per weekday, which is why the existing parser reports "Could not find day
header row". This prints the section skeleton - the day marker, the time header
and the leading columns of each row - so the parser can be written against the
real shape instead of a guess.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

import pdfplumber  # noqa: E402

from core.config import DAYS_ORDER  # noqa: E402

SEMESTER_RE = re.compile(r"^\s*([IVX]+)\s*Sem\s*$", re.IGNORECASE)
TIME_RE = re.compile(r"\d{1,2}[:.]\d{2}")


def clean(value):
    return " ".join((value or "").split())


def roman_to_int(text):
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    previous = 0
    for char in reversed(text.upper()):
        value = values.get(char, 0)
        total = total - value if value < previous else total + value
        previous = max(previous, value)
    return total


def main() -> int:
    path = Path(sys.argv[1])
    with pdfplumber.open(path) as pdf:
        for p_index, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                continue
            table = [[clean(c) for c in row] for row in tables[0]]

            print(f"\n########## page {p_index} ##########")
            day = None
            times = []
            for r_index, row in enumerate(table):
                first = row[0] if row else ""
                rest = row[1] if len(row) > 1 else ""

                # A day section marker: one cell holding a weekday.
                if first in DAYS_ORDER and not rest.strip():
                    day = first
                    print(f"\n--- {day} (row {r_index}) ---")
                    continue

                # The time header: "Time/Day | Group | 8:00-8:55 | ..."
                if "Time" in first and sum(1 for c in row if TIME_RE.search(c)) >= 3:
                    times = [(i, c) for i, c in enumerate(row) if TIME_RE.search(c)]
                    print("    time cols:", [(i, c) for i, c in times])
                    continue

                if SEMESTER_RE.match(first):
                    print(f"    SEMESTER {first} -> {roman_to_int(SEMESTER_RE.match(first).group(1))}")
                    continue

                if not any(cells for cells in row):
                    continue

                # A data row: show the leading columns plus a count of entries.
                filled = sum(1 for c in row[2:] if c)
                print(
                    f"    row {r_index:<3} col0={first[:22]!r:<24} col1={rest[:6]!r:<8} "
                    f"cells={filled}"
                )
                for idx, col in [(2 + i, c) for i, c in enumerate(row[2:]) if c][:2]:
                    print(f"           [{idx}] {row[idx][:100]!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
