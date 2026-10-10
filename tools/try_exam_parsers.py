"""Run the exam parsers against the real downloaded PDFs."""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "backend"))

from features.exam.parser import parse_seating_index_file, parse_mid_sem_file  # noqa: E402

DOWNLOADS = Path.home() / "Downloads"

for label, filename, parser in (
    ("SEATING INDEX", "MID SEM Indexing 2026-27 (Odd Sem)-print.PDF", parse_seating_index_file),
    ("MID SEM TIMETABLE", "Mid Sem Examination Time Table _23rd Sept, 2025 - Table 1.pdf", parse_mid_sem_file),
):
    path = DOWNLOADS / filename
    if not path.exists():
        print(f"!! missing {path}")
        continue

    result = parser(path, is_csv=False)
    rows = result["rows"]
    print(f"\n===== {label}: {result['stats']} =====")
    if not rows:
        print("  NO ROWS PARSED")
        continue

    date_key = "seating_date" if "seating_date" in rows[0] else "schedule_date"
    print("  dates:", collections.Counter(str(r[date_key]) for r in rows).most_common(8))
    print("  slots:", collections.Counter(f"{r['start_time']}-{r['end_time']}" for r in rows).most_common(6))
    print("  courses:", len({r["course_code"] for r in rows}), sorted({r["course_code"] for r in rows})[:18])
    print("  branches:", collections.Counter(str(r["branch"]) for r in rows).most_common())
    print("  UNKNOWN courses:", sum(1 for r in rows if r["course_code"] == "UNKNOWN"))
    print("  rooms:", len({r["room"] for r in rows}), sorted({r["room"] for r in rows})[:10])
    print("  sample rows:")
    for row in rows[:6]:
        print("   ", {k: str(v) for k, v in row.items()})