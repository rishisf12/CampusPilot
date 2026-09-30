"""Timetable PDF/CSV parser with debug support."""
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import time
import pdfplumber
import pandas as pd

from config import DAYS_ORDER, DAY_TO_INT, COLLEGE_START_HOUR, COLLEGE_END_HOUR

logger = logging.getLogger(__name__)

# Time slot regex: matches "9:00-10:00", "09:00 - 10:00", "9.00-10.00", etc.
TIME_RANGE_RE = re.compile(r"(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})")
TIME_SINGLE_RE = re.compile(r"(\d{1,2})[:.](\d{2})")


def parse_time_str(s: str) -> Optional[time]:
    """Parse time string like '9:00', '09:00', '9.00' -> time(9, 0)."""
    s = s.strip().replace(".", ":")
    m = TIME_SINGLE_RE.match(s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return time(h, mi)
    return None


def parse_time_range(s: str) -> tuple[Optional[time], Optional[time]]:
    """Parse '9:00-10:00' -> (time(9,0), time(10,0))."""
    s = s.strip().replace(".", ":")
    m = TIME_RANGE_RE.match(s)
    if m:
        h1, mi1, h2, mi2 = map(int, m.groups())
        return time(h1, mi1), time(h2, mi2)
    # Fallback: single time means 1-hour slot
    t = parse_time_str(s)
    if t:
        from datetime import timedelta
        end = (time(t.hour, t.minute) + timedelta(hours=1)).replace(tzinfo=None)
        return t, end
    return None, None


def normalize_room(room: str) -> str:
    """Normalize room strings: 'L 201' -> 'L-201', 'CR 103' -> 'CR-103'."""
    if not room:
        return ""
    room = room.strip().upper()
    # Insert dash between letters and digits if missing
    room = re.sub(r"([A-Z]+)\s*(\d+)", r"\1-\2", room)
    # Collapse multiple spaces/dashes
    room = re.sub(r"\s+", " ", room).replace(" - ", "-").replace(" -", "-").replace("- ", "-")
    return room


def extract_tables_from_pdf(pdf_path: Path) -> List[List[List[str]]]:
    """Extract tables from all pages using pdfplumber."""
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                for t_idx, table in enumerate(tables):
                    # Clean cell values
                    cleaned = [[(cell or "").strip() for cell in row] for row in table]
                    all_tables.append(cleaned)
                    logger.info(f"Page {i+1}, table {t_idx+1}: {len(cleaned)} rows x {len(cleaned[0]) if cleaned else 0} cols")
            else:
                # Fallback: extract text
                text = page.extract_text()
                if text:
                    logger.info(f"Page {i+1}: no tables, extracted text ({len(text)} chars)")
    return all_tables


def parse_grid_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
    """
    Parse grid-style timetable where:
    - Rows represent branches/programs (e.g., "M.Tech (AI)", "CSE Sem 5")
    - Columns represent days (Mon-Sun) with time slots
    - Cells contain course codes or course names
    """
    slots = []
    warnings = []

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Find header row (contains day names)
        header_row_idx = -1
        day_cols = {}  # day -> column index
        for i, row in enumerate(table):
            day_count = sum(1 for cell in row if cell.strip() in DAYS_ORDER)
            if day_count >= 3:  # At least 3 days found
                header_row_idx = i
                for j, cell in enumerate(row):
                    cell_clean = cell.strip()
                    if cell_clean in DAYS_ORDER:
                        day_cols[cell_clean] = j
                break

        if header_row_idx == -1:
            warnings.append("Could not find day header row in table")
            continue

        # Determine time slots from first column (or a time column)
        time_col_idx = 0
        # Look for time patterns in first column
        time_slots = []
        for row in table[header_row_idx + 1:]:
            if row and row[0]:
                t = parse_time_str(row[0])
                if t:
                    time_slots.append(t)
        if not time_slots:
            warnings.append("Could not parse time slots from first column")
            continue

        # Parse data rows: each row = branch/program
        for row in table[header_row_idx + 1:]:
            if not row or len(row) <= max(day_cols.values()):
                continue

            branch = row[0].strip() if row[0] else "Unknown"
            # Skip if branch looks like a time
            if parse_time_str(branch):
                continue

            for day, col_idx in day_cols.items():
                if col_idx >= len(row):
                    continue
                cell = row[col_idx].strip()
                if not cell or cell.lower() in ("", "-", "na", "n/a", "none"):
                    continue

                # Cell might contain multiple lines (multiple courses)
                # For simplicity, take first line as course code
                course_code = cell.split("\n")[0].strip()
                if not course_code:
                    continue

                # Try to find time slot for this row
                slot_start = time_slots[0] if time_slots else time(COLLEGE_START_HOUR, 0)
                slot_end = time(COLLEGE_START_HOUR + 1, 0)

                # Try to extract room if present (e.g., "CS301 L-101")
                room = "TBA"
                parts = cell.split()
                if len(parts) > 1 and re.match(r"^[A-Z]+-\d+$", parts[-1].upper()):
                    room = normalize_room(parts[-1])
                    course_code = " ".join(parts[:-1])

                slots.append({
                    "day": day,
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "room": room,
                    "course_code": course_code,
                    "branch_or_program": branch,
                    "semester": 1,  # Default, will be updated if detectable
                })

    return slots, warnings


def parse_csv_timetable(csv_path: Path) -> tuple[List[Dict], List[str]]:
    """Parse CSV fallback with columns: day,start_time,end_time,room,course_code,branch_or_program,semester."""
    import csv
    slots = []
    warnings = []

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"day", "start_time", "end_time", "room", "course_code", "branch_or_program", "semester"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(f"CSV missing columns: {missing}")

        for i, row in enumerate(reader, 1):
            try:
                day = row["day"].strip()[:3].capitalize()
                if day not in DAYS_ORDER:
                    warnings.append(f"Row {i}: invalid day '{row['day']}'")
                    continue

                start = parse_time_str(row["start_time"])
                end = parse_time_str(row["end_time"])
                if not start or not end:
                    warnings.append(f"Row {i}: invalid time format")
                    continue

                slots.append({
                    "day": day,
                    "start_time": start,
                    "end_time": end,
                    "room": normalize_room(row["room"]),
                    "course_code": row["course_code"].strip(),
                    "branch_or_program": row["branch_or_program"].strip(),
                    "semester": int(row["semester"]),
                })
            except Exception as e:
                warnings.append(f"Row {i}: {e}")

    return slots, warnings


def parse_timetable_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
    """
    Main entry: parse PDF or CSV timetable.
    Returns dict with slots, raw_extraction, warnings, stats.
    """
    if is_csv:
        slots, warnings = parse_csv_timetable(file_path)
        raw = {"csv_rows": len(slots)}
    else:
        tables = extract_tables_from_pdf(file_path)
        slots, warnings = parse_grid_timetable(tables)
        raw = {"tables": tables}

    return {
        "slots": slots,
        "raw_extraction": raw,
        "warnings": warnings,
        "stats": {
            "slots_found": len(slots),
            "warnings_count": len(warnings),
        }
    }


# For debug endpoint: return raw text too
def extract_raw_text(pdf_path: Path) -> List[str]:
    """Extract raw text from each page for debugging."""
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return texts