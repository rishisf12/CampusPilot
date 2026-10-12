"""Dump the raw tables of a timetable PDF so the grid parser can be matched to it.

The "Could not find day header row" warning means the parser did not recognise
the layout. This prints every table it can see - shape first, then cell text -
so the real structure is visible instead of guessed at.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

import pdfplumber  # noqa: E402

from core.config import DAYS_ORDER  # noqa: E402

MAX_CELLS = 14


def cell_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split())


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: dump_timetable_tables.py <file.pdf>")
        return 1

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"not a file: {path}")
        return 1
    if path.stat().st_size == 0:
        print(f"{path.name} is 0 bytes - the download failed, nothing to parse")
        return 1

    print(f"file  : {path.name}")
    print(f"bytes : {path.stat().st_size}")

    with pdfplumber.open(path) as pdf:
        print(f"pages : {len(pdf.pages)}")
        for index, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            print(f"\n=== page {index}: {len(tables)} table(s), "
                  f"{page.width:.0f}x{page.height:.0f} ===")
            for t_index, table in enumerate(tables, 1):
                print(f"\n-- table {t_index}: {len(table)} rows --")
                for r_index, row in enumerate(table):
                    cells = [cell_text(c) for c in row]
                    shown = cells[:MAX_CELLS]
                    marker = " *" if any(
                        c.strip() in DAYS_ORDER for c in cells
                    ) else ""
                    print(f"  r{r_index:<3}{marker} | " + " | ".join(shown))

            if not tables:
                text = page.extract_text() or ""
                print("  (no tables; first 600 chars of page text)")
                print("  " + text[:600].replace("\n", " | "))

    print(f"\nDAYS_ORDER the parser looks for: {DAYS_ORDER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
