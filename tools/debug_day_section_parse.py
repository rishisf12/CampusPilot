"""Trace why the day-section parser finds nothing in the real timetable."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from features.timetable.parser import (  # noqa: E402
    _is_branch_label,
    _parse_header_range,
    extract_tables_from_pdf,
)
from core.config import DAYS_ORDER  # noqa: E402

PDF = r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF"


def main() -> int:
    tables = extract_tables_from_pdf(Path(PDF))
    print("tables:", len(tables), "rows in table 0:", len(tables[0]))

    table = tables[0]
    print("DAYS_ORDER:", DAYS_ORDER)
    print("'Monday' in DAYS_ORDER:", "Monday" in DAYS_ORDER)
    print()

    for index in range(0, 7):
        row = table[index]
        second = row[1] if len(row) > 1 else ""
        print(f"row {index}: first={row[0]!r}")
        print(f"         second={second!r}")
        parsed = [(i, _parse_header_range(c)) for i, c in enumerate(row) if c]
        header_hits = [
            (i, c, _parse_header_range(c)) for i, c in enumerate(row)
            if _parse_header_range(c)
        ]
        print(f"         header-range hits: {[(i, c) for i, c, _ in header_hits]}")
        print(f"         is_branch_label(first): {_is_branch_label(row[0])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
