"""Exam seating PDF/CSV parser with debug support."""
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import date, time
import pdfplumber
import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

# Roll number pattern: prefix + number (e.g., 23BCS003) - prefix must end with a letter
ROLL_PATTERN = re.compile(r"^(.*[A-Za-z])(\d+)$")

# Range patterns: "23BCS003 to 23BCS291" or "23BCS003-23BCS291"
RANGE_PATTERN = re.compile(
    r"([A-Za-z0-9]+?\d+)\s*(?:to|-|–)\s*([A-Za-z0-9]+?\d+)",
    re.IGNORECASE
)

# Room normalization: "L 201" -> "L-201"
ROOM_PATTERN = re.compile(r"([A-Z]+)\s*(\d+)")


def parse_roll(roll: str) -> tuple[str, int]:
    """Split roll like '23BCS003' -> ('23BCS', 3)."""
    roll = roll.strip().upper()
    match = ROLL_PATTERN.match(roll)
    if not match:
        raise ValueError(f"Invalid roll format: {roll}")
    prefix = match.group(1)
    num = int(match.group(2))
    return prefix, num


def roll_in_range(roll: str, start_prefix: str, start_num: int, end_num: int) -> bool:
    """Check if roll falls in [start_num, end_num] with same prefix."""
    prefix, num = parse_roll(roll)
    if prefix != start_prefix.upper():
        return False
    return start_num <= num <= end_num


def parse_roll_range(range_str: str) -> tuple[str, int, int]:
    """Parse '23BCS003 to 23BCS291' or '23BCS003-23BCS291'."""
    normalized = range_str.replace(" to ", "-").replace(" TO ", "-").replace(" To ", "-").replace("–", "-")
    parts = normalized.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid range format: {range_str}")

    start_prefix, start_num = parse_roll(parts[0].strip())
    end_prefix, end_num = parse_roll(parts[1].strip())

    if start_prefix != end_prefix:
        raise ValueError(f"Prefix mismatch in range: {range_str}")

    if start_num > end_num:
        raise ValueError(f"Start > end in range: {range_str}")

    return start_prefix, start_num, end_num


def normalize_room(room: str) -> str:
    """Normalize room strings: 'L 201' -> 'L-201', 'CR 103' -> 'CR-103'."""
    if not room:
        return ""
    room = room.strip().upper()
    room = re.sub(r"([A-Z]+)\s*(\d+)", r"\1-\2", room)
    room = re.sub(r"\s+", " ", room).replace(" - ", "-").replace(" -", "-").replace("- ", "-")
    return room


def parse_time_str(s: str) -> Optional[time]:
    """Parse time string like '9:00', '09:00', '9.00' -> time(9, 0)."""
    s = s.strip().replace(".", ":")
    match = re.match(r"(\d{1,2}):(\d{2})", s)
    if not match:
        return None
    h, mi = int(match.group(1)), int(match.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return time(h, mi)
    return None


def parse_date_str(s: str) -> Optional[date]:
    """Parse date string like '2026-12-15', '15/12/2026', '15-12-2026'."""
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def extract_tables_from_pdf(pdf_path: Path) -> List[List[List[str]]]:
    """Extract tables from all pages using pdfplumber."""
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                for t_idx, table in enumerate(tables):
                    cleaned = [[(cell or "").strip() for cell in row] for row in table]
                    all_tables.append(cleaned)
                    logger.info(f"Page {i+1}, table {t_idx+1}: {len(cleaned)} rows x {len(cleaned[0]) if cleaned else 0} cols")
            else:
                text = page.extract_text()
                if text:
                    logger.info(f"Page {i+1}: no tables, extracted text ({len(text)} chars)")
    return all_tables


def extract_raw_text(pdf_path: Path) -> List[str]:
    """Extract raw text from each page for debugging."""
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return texts


def parse_exam_table(table: List[List[str]]) -> List[Dict[str, Any]]:
    """
    Parse a table containing exam seating data.
    Expected columns (flexible): roll range, room, date, time, course
    """
    rows = []
    if not table or len(table) < 2:
        return rows

    # Try to find header row
    header_idx = 0
    for i, row in enumerate(table):
        row_str = " ".join(row).lower()
        if any(kw in row_str for kw in ["roll", "range", "room", "date", "time", "course"]):
            header_idx = i
            break

    # Map column indices by header content
    headers = [h.lower() for h in table[header_idx]] if header_idx < len(table) else []
    col_map = {}
    for idx, h in enumerate(headers):
        if "roll" in h or "range" in h:
            col_map["roll_range"] = idx
        elif "room" in h:
            col_map["room"] = idx
        elif "date" in h:
            col_map["date"] = idx
        elif "time" in h or "slot" in h:
            col_map["time"] = idx
        elif "course" in h or "subject" in h or "paper" in h:
            col_map["course"] = idx

    # If no headers found, assume standard order
    if not col_map:
        col_map = {
            "roll_range": 0,
            "room": 1,
            "date": 2,
            "time": 3,
            "course": 4,
        }

    for row in table[header_idx + 1:]:
        if not row or all(not cell for cell in row):
            continue

        try:
            roll_range = row[col_map.get("roll_range", 0)] if col_map.get("roll_range", 0) < len(row) else ""
            room = row[col_map.get("room", 1)] if col_map.get("room", 1) < len(row) else ""
            date_str = row[col_map.get("date", 2)] if col_map.get("date", 2) < len(row) else ""
            time_str = row[col_map.get("time", 3)] if col_map.get("time", 3) < len(row) else ""
            course = row[col_map.get("course", 4)] if col_map.get("course", 4) < len(row) else ""

            if not roll_range or not room:
                continue

            start_prefix, start_num, end_num = parse_roll_range(roll_range)
            exam_date = parse_date_str(date_str) or date.today()
            
            # Parse time range
            start_time = time(9, 0)
            end_time = time(12, 0)
            if time_str:
                if "-" in time_str or "–" in time_str:
                    parts = time_str.replace("–", "-").split("-")
                    if len(parts) == 2:
                        start_time = parse_time_str(parts[0]) or time(9, 0)
                        end_time = parse_time_str(parts[1]) or time(12, 0)
                else:
                    start_time = parse_time_str(time_str) or time(9, 0)
                    end_time = time(start_time.hour + 3, start_time.minute)

            rows.append({
                "roll_start_prefix": start_prefix,
                "roll_start_num": start_num,
                "roll_end_num": end_num,
                "room": normalize_room(room),
                "exam_date": exam_date,
                "start_time": start_time,
                "end_time": end_time,
                "course_code": course.strip() if course else "UNKNOWN",
            })
        except Exception as e:
            logger.warning(f"Failed to parse row {row}: {e}")

    return rows


def parse_csv_exam(csv_path: Path) -> List[Dict[str, Any]]:
    """Parse CSV fallback with columns: roll_range,room,date,time,course_code."""
    import csv
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            try:
                roll_range = row.get("roll_range", "").strip()
                room = row.get("room", "").strip()
                date_str = row.get("date", "").strip()
                time_str = row.get("time", "").strip()
                course = row.get("course_code", "").strip()

                if not roll_range or not room:
                    continue

                start_prefix, start_num, end_num = parse_roll_range(roll_range)
                exam_date = parse_date_str(date_str) or date.today()
                
                start_time = time(9, 0)
                end_time = time(12, 0)
                if time_str:
                    if "-" in time_str:
                        parts = time_str.split("-")
                        if len(parts) == 2:
                            start_time = parse_time_str(parts[0]) or time(9, 0)
                            end_time = parse_time_str(parts[1]) or time(12, 0)
                    else:
                        start_time = parse_time_str(time_str) or time(9, 0)
                        end_time = time(start_time.hour + 3, start_time.minute)

                rows.append({
                    "roll_start_prefix": start_prefix,
                    "roll_start_num": start_num,
                    "roll_end_num": end_num,
                    "room": normalize_room(room),
                    "exam_date": exam_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "course_code": course if course else "UNKNOWN",
                })
            except Exception as e:
                logger.warning(f"CSV row {i} parse error: {e}")

    return rows


def parse_exam_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
    """Main entry: parse PDF or CSV exam seating."""
    if is_csv:
        rows = parse_csv_exam(file_path)
        raw = {"csv_rows": len(rows)}
    else:
        tables = extract_tables_from_pdf(file_path)
        rows = []
        for table in tables:
            rows.extend(parse_exam_table(table))
        raw = {"tables": tables}

    return {
        "rows": rows,
        "raw_extraction": raw,
        "stats": {
            "rows_parsed": len(rows),
        }
    }