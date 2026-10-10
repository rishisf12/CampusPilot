"""Exam PDF/CSV parsers: seating index, mid-sem timetable, branch inference."""
import logging
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pdfplumber


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
    return re.sub(r"\s+", " ", room).replace(" - ", "-").replace(" -", "-").replace("- ", "-")


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
    return parse_human_date(s)


# ---------------------------------------------------------------------------
# Human-friendly date parsing ("29th Sept 2025", "21.09.2026(Monday)")
# ---------------------------------------------------------------------------

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))

# "21.09.2026(Monday)" / "29th Sept 2025 Monday"
DATE_DOTTED = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})")
DATE_DAYMONTH = re.compile(
    rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_PATTERN})\.?\s*,?\s*(\d{{4}})",
    re.IGNORECASE,
)
WEEKDAY = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)", re.IGNORECASE
)


def _clean_year(year: int) -> int:
    """Expand a 2-digit year, assuming the 2020s (23 -> 2023)."""
    return year + 2000 if year < 100 else year


def parse_human_date(text: str) -> Optional[date]:
    """
    Parse the date formats used in IIITDM exam PDFs.

    Handles ``21.09.2026(Monday)``, ``29th Sept 2025``, ``29-09-2025`` and
    ``September 29, 2025``.
    """
    if not text:
        return None
    text = text.strip()

    # ISO dates must be checked first: the dotted patterns below would happily
    # match the "25-10-06" tail of "2025-10-06".
    iso = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if iso:
        year, month, day = (int(g) for g in iso.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    match = DATE_DAYMONTH.search(text)
    if match:
        day, month_name, year = match.groups()
        return date(_clean_year(int(year)), MONTHS[month_name.lower()], int(day))

    match = DATE_DOTTED.search(text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return date(_clean_year(year), month, day)

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_weekday(text: str) -> Optional[str]:
    """Return the weekday name found in ``text`` (e.g. 'Monday')."""
    match = WEEKDAY.search(text or "")
    return match.group(1).title() if match else None


# ---------------------------------------------------------------------------
# State-machine building blocks (shared by both exam PDF parsers)
# ---------------------------------------------------------------------------

#: "08:00 AM - 10:00 AM", "10.30AM-12.30PM", "3:30PM-5:30PM", "3.30-5.30pm"
TIME_TOKEN = r"(?:\d{1,2})[:.](?:\d{2})\s*(?:AM|PM|am|pm|a\.m\.|p\.m\.)?"
TIME_RANGE_RE = re.compile(rf"({TIME_TOKEN})\s*(?:to|TO|-|–|—)\s*({TIME_TOKEN})")


def parse_meridiem_time(value: str) -> Optional[time]:
    """
    Parse ``08:00 AM`` / ``10.30AM`` / ``3:30pm`` / ``14:00`` into a ``time``.

    The regex trims trailing ``AM``/``PM`` characters one at a time so that the
    meridiem is detected even when it is glued to the minutes (``10.30AM``).
    """
    if not value:
        return None
    raw = value.strip()
    meridiem = None
    lowered = raw.lower()
    for token, marker in (("a.m.", "AM"), ("p.m.", "PM"), ("am", "AM"), ("pm", "PM")):
        if lowered.endswith(token):
            meridiem = marker
            raw = raw[: len(raw) - len(token)].strip()
            break

    match = re.match(r"^(\d{1,2})[:.](\d{2})", raw)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if minute > 59:
        return None
    if meridiem == "PM" and hour < 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    if hour > 23:
        return None
    return time(hour, minute)


def parse_slot_range(value: str) -> tuple[Optional[time], Optional[time]]:
    """
    Parse ``10.30AM-12.30PM`` into ``(start, end)``.

    Handles the common exam-timetable shorthand where only the closing time
    carries a meridiem (``3.30-5.30pm``) - the opening time inherits it.
    """
    if not value:
        return None, None
    match = TIME_RANGE_RE.search(value)
    if match:
        raw_start, raw_end = match.group(1), match.group(2)
        start = parse_meridiem_time(raw_start)
        end = parse_meridiem_time(raw_end)
        # "3.30-5.30pm": start has no meridiem but end says PM.
        if start is not None and not re.search(r"[AaPp]\.?[Mm]\.?", raw_start):
            if re.search(r"[Pp]\.?[Mm]\.?", raw_end) and start.hour < 12:
                start = start.replace(hour=start.hour + 12)
            elif re.search(r"[Aa]\.?[Mm]\.?", raw_end) and start.hour == 12:
                start = start.replace(hour=0)
        if start is not None and end is not None and end <= start:
            # "11.30-1.30am" is shorthand for a 12-hour clock: roll the closing
            # time past noon before giving up on the range.
            rolled_end = (datetime.combine(date.today(), end) + timedelta(hours=12)).time()
            if rolled_end > start:
                return start, rolled_end
            # Garbled overlapping text produced something like "22.30-12.30PM".
            logger.debug("Discarding impossible slot range %r", value.strip())
            return None, None
        return start, end
    single = parse_meridiem_time(value)
    if single is None:
        return None, None
    end_dt = datetime.combine(date.today(), single) + timedelta(hours=2)
    return single, end_dt.time()


# Course codes look like NS1001, CS8037, EC5M03, ME5D03, OE3E33, MT5003, DS5012
#: Course-code shape: 2-3 letters, 1-4 digits, optional letter and digits.
#: Covers NS1001, CS8036, DS1002, MT5003 and the MDes-style EC5M03 / ME5D03.
COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,3}\s?\d{1,4}[A-Z]?\d{0,2})\b")
#: Hall codes that collide with the course-code pattern (``CR103`` is a room).
ROOM_CODE_PREFIXES = {"CR", "LH", "LT", "AB"}
#: A batch/elective annotation such as "(Batch-A)" or "(OE3E33)".
GROUP_SUFFIX_RE = re.compile(r"\(([^)]{1,24})\)")
#: Prefix used for open-elective courses, which belong to no single branch.
OE_PREFIXES = {"OE"}


def split_course_codes(value: str) -> List[str]:
    """
    Extract course codes, splitting slash-joined cells such as ``CS8031/CS8032``.

    Batch suffixes are stripped: ``NS1001 (Batch-A)`` -> ``['NS1001']``.
    """
    if not value:
        return []

    # Drop "(Batch-A)" style suffixes, keeping anything that looks like a code.
    working = value
    for suffix in GROUP_SUFFIX_RE.findall(value):
        if COURSE_CODE_RE.search(suffix.replace(" ", "")):
            working = working.replace(f"({suffix})", " ")
    working = working.replace("(", " ").replace(")", " ").replace("/", " / ")

    codes: List[str] = []
    for token in re.split(r"[,\s]+", working):
        token = token.strip().strip("/").upper()
        if not token or token == "/":
            continue
        if not re.fullmatch(r"[A-Z]{2,3}\s?\d{1,4}[A-Z]?\d{0,2}", token):
            continue
        if token[:2] in ROOM_CODE_PREFIXES:
            continue  # hall code, not a course
        if token not in codes:
            codes.append(token.replace(" ", ""))
    return codes


def extract_roll_tokens(value: str) -> List[str]:
    """
    Pull every roll number out of a cell, whether it is a range or a list.

    ``26BCS042 to 26BCS113`` -> ``['26BCS042', '26BCS113']``
    ``23BCS125, 23BCS197``   -> ``['23BCS125', '23BCS197']``
    """
    if not value:
        return []
    tokens: List[str] = []
    for match in ROLL_TOKEN_RE.finditer(value):
        token = match.group(0).upper().strip()
        if token not in tokens:
            tokens.append(token)
    return tokens


ROLL_TOKEN_RE = re.compile(r"\b([0-9]{2,4}[A-Z]{2,4}\d{1,4})\b")


def roll_tokens_to_ranges(tokens: List[str]) -> List[tuple[str, int, int]]:
    """Convert roll tokens into ``(prefix, start, end)`` tuples, pairing them up."""
    ranges: List[tuple[str, int, int]] = []
    for index in range(0, len(tokens), 2):
        chunk = tokens[index : index + 2]
        try:
            start_prefix, start_num = parse_roll(chunk[0])
        except ValueError:
            continue
        if len(chunk) == 2:
            try:
                end_prefix, end_num = parse_roll(chunk[1])
            except ValueError:
                end_prefix, end_num = start_prefix, start_num
            # The PDF sometimes lists the bounds the wrong way round; swap them
            # rather than dropping the row.
            if end_prefix == start_prefix and end_num < start_num:
                start_num, end_num = end_num, start_num
            elif end_prefix != start_prefix:
                end_prefix, end_num = start_prefix, start_num
        else:
            end_prefix, end_num = start_prefix, start_num
        ranges.append((start_prefix, start_num, end_num))
    return ranges


def is_open_elective(course_code: str) -> bool:
    """True for OE-prefixed courses (open electives, shared across branches)."""
    return bool(course_code) and course_code[:2].upper() in OE_PREFIXES


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
        except Exception as e:  # noqa: BLE001 - one malformed row must not abort the whole file
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
            except Exception as e:  # noqa: BLE001 - one malformed row must not abort the whole file
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


# ---------------------------------------------------------------------------
# Seating index parser  (Class room Index: roll range -> room)
# ---------------------------------------------------------------------------

#: Column layout of the seating index, used when the header row is present.
SEATING_HEADER_MAP = {
    "S. No.": "sno",
    "Lecture Hall": "room",
    "Course Code": "course",
    "Roll Numbers": "rolls",
    "No. of Students": "count",
    "Total Students in Room": "room_total",
    "Invigilator": "invigilator",
}


def map_seating_columns(table: List[List[str]]) -> Dict[str, int]:
    """Map header labels to column indices; falls back to the standard order."""
    for row in table[:5]:
        labels = [(cell or "").strip().lower() for cell in row]
        if not any("roll" in label for label in labels):
            continue
        mapping: Dict[str, int] = {}
        for index, label in enumerate(labels):
            for header, key in SEATING_HEADER_MAP.items():
                if label.startswith(header.lower()):
                    mapping.setdefault(key, index)
        if "rolls" in mapping:
            mapping.setdefault("room", 1)
            mapping.setdefault("course", 2)
            return mapping
    # Standard positional fallback: S.No | Lecture Hall | Course | Rolls | ...
    return {"sno": 0, "room": 1, "course": 2, "rolls": 3, "count": 4}


def drop_outlier_dates(rows: List[Dict[str, Any]], key: str, tolerance: int = 1) -> List[Dict[str, Any]]:
    """
    Discard rows whose parsed date sits far outside the document's main year.

    Overlapping PDF text sometimes yields nonsense such as ``30-05-30``, which
    would otherwise show up as an exam scheduled in 2030.  The modal year of the
    remaining rows defines the document year.
    """
    dated = [row for row in rows if row.get(key) is not None]
    if not dated:
        return rows
    years = [row[key].year for row in dated]
    modal_year = max(set(years), key=years.count)
    kept = [row for row in rows if row.get(key) is None or abs(row[key].year - modal_year) <= tolerance]
    if len(kept) != len(rows):
        logger.warning(
            "Dropped %d row(s) with outlier dates outside %d +/- %d",
            len(rows) - len(kept),
            modal_year,
            tolerance,
        )
    return kept


def parse_indexing_table(table: List[List[str]], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parse one seating-index table into ``ExamSeating`` rows.

    The document is a state machine: a day/date line opens a block, a time line
    sets the slot, and data rows then carry ``S. No. | Lecture Hall | Course |
    Roll Numbers``.  Room and serial number are inherited by continuation rows
    (a room keeps the same hall for several courses).
    """
    context = context or {}
    columns = map_seating_columns(table)

    rows: List[Dict[str, Any]] = []
    current_date: Optional[date] = context.get("date")
    current_start: Optional[time] = context.get("start")
    current_end: Optional[time] = context.get("end")
    current_room = ""
    current_sno: Optional[int] = None

    for raw_row in table:
        cells = [(cell or "").strip() for cell in raw_row]
        joined = " ".join(cell for cell in cells if cell).strip()
        if not joined:
            continue

        # --- state transitions -------------------------------------------------
        day_name = parse_weekday(joined)
        parsed_date = parse_human_date(joined)
        if parsed_date and (day_name or DATE_DAYMONTH.search(joined)):
            current_date = parsed_date
            continue

        start, end = parse_slot_range(joined)
        if start and end:
            current_start, current_end = start, end
            continue

        # A row that is only a header carries no rolls.
        lowered = joined.lower()
        if "roll number" in lowered and "course" in lowered:
            continue
        if lowered.startswith("class room index"):
            continue

        # --- data row ----------------------------------------------------------
        def cell_for(key: str, cells=cells) -> str:
            index = columns.get(key)
            if index is None or index >= len(cells):
                return ""
            return cells[index]

        roll_tokens = extract_roll_tokens(cell_for("rolls"))
        if not roll_tokens:
            continue

        # The hall number only appears on the first row of a room group.
        room_cell = normalize_room(cell_for("room"))
        if room_cell:
            current_room = room_cell
        sno_cell = cell_for("sno")
        if sno_cell.isdigit():
            current_sno = int(sno_cell)

        course_codes = split_course_codes(cell_for("course"))
        if not course_codes:
            # Fall back to the whole row: garbled PDFs still yield the code.
            course_codes = split_course_codes(joined)
        if not course_codes:
            # Overlapping text destroyed both the course and its roll range.
            # Storing a fabricated row would corrupt lookups, so skip it.
            context["skipped"] = context.get("skipped", 0) + 1
            continue

        for course_code in course_codes:
            for prefix, start_num, end_num in roll_tokens_to_ranges(roll_tokens):
                rows.append({
                    "roll_start_prefix": prefix,
                    "roll_start_num": start_num,
                    "roll_end_num": end_num,
                    "room": current_room,
                    "seating_date": current_date,
                    "start_time": current_start or time(9, 0),
                    "end_time": current_end or time(12, 0),
                    "course_code": course_code,
                    "branch": None,  # filled by attach_branch_metadata()
                    "semester": None,
                    "is_extra": is_open_elective(course_code),
                    "s_no": current_sno,
                })

    return rows


def attach_branch_metadata(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fill the ``branch``/``semester`` columns that the PDF does not provide."""
    for row in rows:
        if not row.get("branch"):
            row["branch"] = infer_branch_from_row(row)
        if row.get("semester") is None:
            row["semester"] = infer_semester_from_course(row.get("course_code", ""))
        row.pop("s_no", None)
    return rows


def parse_indexing_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
    """
    Parse every extracted table of a seating-index PDF.

    The date and time band are threaded between tables: a new page's table
    usually continues the previous block, so rows would otherwise lose their
    date whenever the day/time lines do not repeat.
    """
    rows: List[Dict[str, Any]] = []
    context: Dict[str, Any] = {}
    skipped = 0
    for table in tables:
        rows.extend(parse_indexing_table(table, context))
        skipped = context.get("skipped", 0)
        last = rows[-1] if rows else None
        if last:
            context = {
                "date": last.get("seating_date"),
                "start": last.get("start_time"),
                "end": last.get("end_time"),
                "skipped": skipped,
            }
    if skipped:
        logger.warning("Seating index: skipped %d unreadable row(s)", skipped)
    rows = attach_branch_metadata(drop_outlier_dates(rows, "seating_date"))
    return rows, skipped


# ---------------------------------------------------------------------------
# Mid-sem timetable parser  (Date | Time | Course Code | Semester)
# ---------------------------------------------------------------------------

#: Column layout of the mid-sem timetable.
TIMETABLE_HEADER_MAP = {
    "date": "date",
    "time": "time",
    "course code": "course",
    "semester": "semester",
}
#: "DAY 1", "Day-2", "DAY 3" section headers.
DAY_MARKER_RE = re.compile(r"\bDAY\s*[-_]?\s*(\d+)\b", re.IGNORECASE)


def parse_mid_sem_table(table: List[List[str]], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parse one mid-sem timetable table into ``MidSemSchedule`` rows.

    Columns are ``Date | Time | Course Code | Semester``.  The date cell carries
    the full date ("29th Sept\\n2025 Monday") and a ``DAY n`` marker may appear as
    a standalone row; course cells continue onto following rows with a blank time.
    """
    context = context or {}
    rows: List[Dict[str, Any]] = []

    columns = {"date": 0, "time": 1, "course": 2, "semester": 3}
    for raw_row in table[:5]:
        labels = [(cell or "").strip().lower() for cell in raw_row]
        if any(label.startswith("time") for label in labels):
            for index, label in enumerate(labels):
                for header, key in TIMETABLE_HEADER_MAP.items():
                    if label.startswith(header):
                        columns[key] = index
            break

    current_date: Optional[date] = context.get("date")
    current_start: Optional[time] = context.get("start")
    current_end: Optional[time] = context.get("end")
    current_semester: Optional[int] = context.get("semester")

    def cell_for(key: str) -> str:
        index = columns.get(key, 0)
        if index >= len(raw_row):
            return ""
        return (raw_row[index] or "").strip()

    for raw_row in table:
        cells = [(cell or "").strip() for cell in raw_row]
        joined = " ".join(cell for cell in cells if cell).strip()
        if not joined:
            continue

        lowered = joined.lower()
        if lowered.startswith(("pdpm", "date time course")):
            continue

        # DAY markers advance the block but carry no date themselves.
        if DAY_MARKER_RE.search(joined) and not extract_roll_tokens(joined):
            continue

        parsed_date = parse_human_date(joined)
        if parsed_date and not extract_roll_tokens(joined):
            current_date = parsed_date

        start, end = parse_slot_range(joined)
        if start and end and not extract_roll_tokens(joined):
            current_start, current_end = start, end

        semester = parse_semester_label(cell_for("semester") or joined)
        course_cell = cell_for("course")
        course_codes = split_course_codes(course_cell or joined)
        if not course_codes:
            continue

        # Only treat the semester column as authoritative when it has a value.
        if cell_for("semester"):
            current_semester = semester

        for course_code in course_codes:
            rows.append({
                "schedule_date": current_date,
                "start_time": current_start or time(10, 30),
                "end_time": current_end or time(12, 30),
                "course_code": course_code,
                "room": "",
                "branch": None,
                "semester": current_semester,
                "is_extra": is_open_elective(course_code),
            })

    for row in rows:
        if not row.get("branch"):
            row["branch"] = infer_branch_from_course(row.get("course_code", ""))
        if not row.get("semester"):
            row["semester"] = infer_semester_from_course(row.get("course_code", ""))
    return rows


def parse_mid_sem_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
    """
    Parse every extracted table of a mid-sem timetable PDF.

    As with the seating index, the current date band is carried across table
    boundaries so continuation tables inherit their day.
    """
    rows: List[Dict[str, Any]] = []
    context: Dict[str, Any] = {}
    for table in tables:
        rows.extend(parse_mid_sem_table(table, context))
        last = rows[-1] if rows else None
        if last:
            context = {
                "date": last.get("schedule_date"),
                "start": last.get("start_time"),
                "end": last.get("end_time"),
                "semester": last.get("semester"),
            }
    return drop_outlier_dates(rows, "schedule_date")


# ---------------------------------------------------------------------------
# Branch / semester inference (drives rule 1 and rule 3 of the roll lookup)
# ---------------------------------------------------------------------------

#: The eight branches offered in the profile dropdown.
BRANCH_OPTIONS = ["CSE A", "CSE B", "DS", "ECE", "ME", "SM", "PG", "MDes"]

#: Roll-number infix -> branch. ``23BCS125`` carries the infix ``BCS``.
ROLL_INFIX_BRANCH = {
    "BCS": "CSE", "BCE": "ECE", "BEC": "ECE",
    "BDS": "DS", "BDE": "DS",
    "BME": "ME", "BMC": "ECE",
    "BSM": "SM", "BES": "SM",
    "BPG": "PG", "BMT": "PG", "BMD": "MDes", "BMDS": "MDes",
    "MDS": "MDes", "MCS": "CSE", "MEC": "ECE", "MME": "ME", "MSM": "SM",
}

#: Course-code infix -> branch, used when a PDF row carries no explicit branch.
COURSE_INFIX_BRANCH = {
    "CS": "CSE", "EC": "ECE", "ME": "ME", "SM": "SM",
    "DS": "DS", "MT": "PG", "MDS": "MDes", "MD": "MDes",
}

#: The first two characters of a course code, used for the map above.
BRANCHES_WITH_SECTIONS = {"CSE", "DS"}


def normalize_branch(value: Optional[str]) -> Optional[str]:
    """
    Normalise a free-text branch to one of :data:`BRANCH_OPTIONS`.

    ``"BTech CSE"`` -> ``"CSE A"`` (default section), ``"cse b"`` -> ``"CSE B"``,
    ``"BDS"`` -> ``"DS"``.  Returns ``None`` for empty/unknown input.
    """
    if not value:
        return None
    text = str(value).strip().upper()
    if not text:
        return None

    # Already canonical.
    for option in BRANCH_OPTIONS:
        if text == option.upper():
            return option

    # Sections must be checked before the family match ("CSE B" vs "CSE").
    section = ""
    if re.search(r"\bB\b", text):
        section = "B"
    elif re.search(r"\bA\b", text):
        section = "A"

    if "CSE" in text or "CSE" in text.replace(" ", "") or "BCS" in text or text[:2] == "CS":
        return f"CSE {section}" if section else "CSE A"
    if "MDS" in text or "MDES" in text or "M-DES" in text or "DESIGN" in text:
        return "MDes"
    if "DS" in text:
        return f"DS {section}".strip() if section else "DS"
    if "ECE" in text or "EC" in text[:3]:
        return "ECE"
    if re.search(r"\bME\b", text) or "MECH" in text:
        return "ME"
    if re.search(r"\bSM\b", text) or "SCIENCE" in text:
        return "SM"
    if "PG" in text or "MTECH" in text or "M-TECH" in text:
        return "PG"
    return None


def normalize_exam_branch(value: Optional[str]) -> Optional[str]:
    """Alias of :func:`normalize_branch` kept for exam-specific call sites."""
    return normalize_branch(value)


def branch_family(branch: Optional[str]) -> Optional[str]:
    """``"CSE A"`` -> ``"CSE"``; ``None`` stays ``None``."""
    normalized = normalize_branch(branch)
    if not normalized:
        return None
    if normalized in ("PG", "MDes"):
        return normalized
    return normalized.split(" ")[0]


def infer_branch_from_roll(roll: str) -> Optional[str]:
    """
    Derive the branch from a roll number.

    ``23BCS125`` -> ``"CSE A"`` (odd roll = section A), ``23BCS126`` -> ``"CSE B"``.
    Returns ``None`` when the infix is not recognised.
    """
    try:
        prefix, num = parse_roll(roll)
    except ValueError:
        return None

    infix = prefix[2:] if prefix[:2].isdigit() else prefix
    family = ROLL_INFIX_BRANCH.get(infix.upper())
    if not family:
        return None
    if family in BRANCHES_WITH_SECTIONS:
        return f"{family} {'A' if num % 2 == 1 else 'B'}"
    return family


def infer_branch_from_course(course_code: str) -> Optional[str]:
    """
    Derive the branch family from a course code.

    ``CS8036`` -> ``"CSE"``, ``EC5M03`` -> ``"ECE"``, ``OE3E33`` -> ``None``
    (open electives are not branch-specific).
    """
    if not course_code or is_open_elective(course_code):
        return None
    code = course_code.strip().upper()
    family = COURSE_INFIX_BRANCH.get(code[:2])
    if family:
        return family
    # "MDS501" / "MT5003" style codes where the letters lead.
    for infix, branch in COURSE_INFIX_BRANCH.items():
        if code.startswith(infix) and len(code) > len(infix):
            return branch
    return None


def infer_semester_from_course(course_code: str) -> Optional[int]:
    """
    Derive the semester from a course code's first digit.

    ``CS8036`` -> 8, ``DS1002`` -> 1, ``EC5M03`` -> 5, ``OE3E33`` -> 3.
    """
    if not course_code:
        return None
    match = re.search(r"\d", course_code)
    return int(match.group(0)) if match else None


def parse_semester_label(value: Optional[str]) -> Optional[int]:
    """
    Parse a semester cell such as ``"Sem 5"``, ``"Sem-7"`` or ``"3rd Sem"``.

    PG/PhD rows return ``9`` so they never collide with a real semester.
    """
    if not value:
        return None
    text = str(value).strip().lower()
    if "pg" in text or "phd" in text:
        return 9
    match = re.search(r"(\d)", text)
    return int(match.group(1)) if match else None


def infer_branch_from_row(
    row: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Best-effort branch for a row that carries no explicit branch column.

    Tries the roll range first, then the course code, and finally falls back to
    the profile's branch so open-elective rows inherit the student's branch.
    """
    prefix = row.get("roll_start_prefix")
    if prefix:
        with_num = f"{prefix}{row.get('roll_start_num', 1)}"
        inferred = infer_branch_from_roll(with_num)
        if inferred:
            return inferred
    inferred = infer_branch_from_course(row.get("course_code", ""))
    if inferred:
        return inferred
    if profile:
        return normalize_branch(profile.get("branch"))
    return None


def branch_matches(row_branch: Optional[str], profile_branch: Optional[str]) -> bool:
    """
    Compare a row branch against the profile branch.

    Matches on family so ``"CSE"`` (a timetable-wide course) is visible to both
    ``"CSE A"`` and ``"CSE B"`` students.
    """
    if not row_branch or not profile_branch:
        return True  # Unknown branch on either side -> do not hide the row.
    row_family = branch_family(row_branch)
    profile_family = branch_family(profile_branch)
    return row_family is None or profile_family is None or row_family == profile_family


def exam_row_visible(
    row: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
    extra_course_codes: Optional[Iterable[str]] = None,
) -> bool:
    """
    Rule 1: keep the filter in sync with the student's profile.

    A row is visible when its branch matches the profile branch family, its
    semester matches, or it belongs to an elective the student opted into.
    (Open electives are NOT automatically visible; they must be in the profile.)
    """
    if not profile:
        return True

    course_code = (row.get("course_code") or "").upper()

    # Electives the student explicitly opted into are visible regardless of branch/semester.
    # Check both the explicit extra_course_codes parameter and the profile's elective_codes.
    elected = set()
    if extra_course_codes:
        elected.update(c.upper() for c in extra_course_codes)
    if profile.get("elective_codes"):
        elected.update(c.strip().upper() for c in profile["elective_codes"] if c and c.strip())
    if course_code in elected:
        return True

    # Branch filter
    if not branch_matches(row.get("branch"), profile.get("branch")):
        return False

    # Semester filter (skip if either side is unknown)
    row_semester = row.get("semester")
    profile_semester = profile.get("semester")
    if (  # noqa: SIM103 - explicit if/return is clearer than negated condition
        row_semester is not None
        and profile_semester is not None
        and row_semester != 9
        and row_semester != profile_semester
    ):
        return False
    return True


# ---------------------------------------------------------------------------
# File-level entry points
# ---------------------------------------------------------------------------

SEATING_CSV_COLUMNS = ("roll_range", "room", "date", "time", "course_code", "branch", "semester")
TIMETABLE_CSV_COLUMNS = ("date", "time", "course_code", "semester", "branch")


def _parse_csv_rows(csv_path: Path, columns: Iterable[str]) -> List[Dict[str, str]]:
    import csv

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(handle)
        ]


def parse_seating_index_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
    """
    Parse a seating-index PDF/CSV into ``ExamSeating``-ready row dicts.

    Each emitted row uses the ``seating_date`` field name to match the model.
    """
    if is_csv:
        rows: List[Dict[str, Any]] = []
        for _index, raw in enumerate(_parse_csv_rows(file_path, SEATING_CSV_COLUMNS), 1):
            roll_tokens = extract_roll_tokens(raw.get("roll_range", ""))
            if not roll_tokens:
                continue
            start_time, end_time = parse_slot_range(raw.get("time", ""))
            course_codes = split_course_codes(raw.get("course_code", "")) or ["UNKNOWN"]
            for course_code in course_codes:
                for prefix, start_num, end_num in roll_tokens_to_ranges(roll_tokens):
                    rows.append({
                        "roll_start_prefix": prefix,
                        "roll_start_num": start_num,
                        "roll_end_num": end_num,
                        "room": normalize_room(raw.get("room", "")),
                        "seating_date": parse_human_date(raw.get("date", "")),
                        "start_time": start_time or time(9, 0),
                        "end_time": end_time or time(12, 0),
                        "course_code": course_code,
                        "branch": normalize_branch(raw.get("branch", "")),
                        "semester": int(raw["semester"]) if raw.get("semester", "").isdigit() else None,
                        "is_extra": is_open_elective(course_code),
                    })
        return {"rows": attach_branch_metadata(rows), "stats": {"rows_parsed": len(rows)}}

    tables = extract_tables_from_pdf(file_path)
    rows, skipped = parse_indexing_tables(tables)
    return {"rows": rows, "stats": {"rows_parsed": len(rows), "tables": len(tables), "rows_skipped": skipped}}


def parse_mid_sem_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
    """Parse a mid-sem timetable PDF/CSV into ``MidSemSchedule``-ready row dicts."""
    if is_csv:
        rows: List[Dict[str, Any]] = []
        for raw in _parse_csv_rows(file_path, TIMETABLE_CSV_COLUMNS):
            course_codes = split_course_codes(raw.get("course_code", "")) or ["UNKNOWN"]
            start_time, end_time = parse_slot_range(raw.get("time", ""))
            for course_code in course_codes:
                rows.append({
                    "schedule_date": parse_human_date(raw.get("date", "")),
                    "start_time": start_time or time(10, 30),
                    "end_time": end_time or time(12, 30),
                    "course_code": course_code,
                    "room": normalize_room(raw.get("room", "")),
                    "branch": normalize_branch(raw.get("branch", "")) or infer_branch_from_course(course_code),
                    "semester": parse_semester_label(raw.get("semester", "")),
                    "is_extra": is_open_elective(course_code),
                })
        return {"rows": rows, "stats": {"rows_parsed": len(rows)}}

    tables = extract_tables_from_pdf(file_path)
    rows = parse_mid_sem_tables(tables)
    return {"rows": rows, "stats": {"rows_parsed": len(rows), "tables": len(tables)}}