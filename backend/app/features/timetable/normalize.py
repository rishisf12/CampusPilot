"""Phase 1: Normalize parser output to match Claude's Excel format.

This module post-processes raw parser slots into the final normalized form:
- Semester: 1 -> I, 3 -> III, 5 -> V, 7 -> VII, 9+ -> PG
- Branch: split CSE into CSE-A/CSE-B, DS into DS-E1/DS-E2, etc.
- Day: Mon -> Monday
- Time: 10:00:00-10:55:00 -> 10:00-10:55
- Room: L-102 -> L102, CR-104 -> CR104
- Course codes: keep lab suffix (NS1002L), strip batch (NS1002L-A -> NS1002L)
"""
import re
from typing import Dict, List, Any, Optional

# Semester number -> Roman numeral (matching Claude's Excel)
SEMESTER_ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII",
}

# Day abbreviation -> full name
DAY_FULL = {
    "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
    "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday",
}

# Branch family -> list of (group_code, full_branch_name)
# The PDF's second column shows group codes; these map to full branch names
BRANCH_GROUPS = {
    "CSE": [("A", "CSE-A"), ("B", "CSE-B")],
    "DS": [("E1", "DS-E1"), ("E2", "DS-E2")],
    # ECE, ME, SM have single groups
}

# PG programmes - the PDF lists these under "VII Sem" block but they're PG
PG_PROGRAMMES = [
    "M.Tech (AI)", "M.Tech (DS)", "Ph.D. (CSE)", "M.Tech (P&C)",
    "M.Tech (Nano)", "M.Tech (Design)", "M.Tech (Mechtronics)",
    "Ph.D. (ME)", "MDes (Sem I)", "MDes (Sem III)", "Ph.D. (NS)",
]


def semester_to_roman(semester: int) -> str:
    """Convert semester number to Roman numeral for display."""
    return SEMESTER_ROMAN.get(semester, str(semester))


def is_pg(semester: int, branch: str) -> bool:
    """Is this a PG/PhD/MDes programme?"""
    if semester >= 9:
        return True
    return any(p in branch for p in ["M.Tech", "Ph.D.", "MDes"])


def normalize_day(day: str) -> str:
    """Mon -> Monday."""
    return DAY_FULL.get(day[:3], day)


def normalize_time(start_time, end_time) -> str:
    """time(10,0) -> '10:00-10:55'."""
    if not start_time or not end_time:
        return ""
    return f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}"


def normalize_room(room: str) -> Optional[str]:
    """L-102 -> L102, CR-104 -> CR104. Returns None for TBA/empty."""
    if not room or room.upper() in ("TBA", "TBC", "N/A", "NONE"):
        return None
    # Remove dash between letters and digits
    room = room.strip()
    room = re.sub(r"^([A-Z]+)-(\d+)$", r"\1\2", room)
    return room


def normalize_course_code(course_code: str) -> str:
    """Keep lab suffix, strip batch letter: NS1002L-A -> NS1002L."""
    if not course_code:
        return ""
    # Strip trailing batch letter like -A, -B (but keep lab L)
    # e.g., ME3010L-A -> ME3010L
    match = re.match(r"^([A-Z]{2,4}\d{3,4}L)-[A-Z]$", course_code, re.IGNORECASE)
    if match:
        return match.group(1)
    return course_code


def split_branch_into_codes(branch: str, group_hint: str = "") -> List[tuple[str, str]]:
    """
    Split a branch family into (group_code, full_branch_name) tuples.
    
    CSE -> [("A", "CSE-A"), ("B", "CSE-B")] (or just the one matching group_hint)
    DS -> [("E1", "DS-E1"), ("E2", "DS-E2")]
    ECE/ME/SM -> [("C", "ECE")]/[("D1", "ME")]/[("D2", "SM")]
    PG programmes -> []
    """
    family = branch.strip()
    
    # PG programmes - check if branch contains PG keywords
    pg_keywords = ["M.Tech", "Ph.D.", "MDes"]
    is_pg_branch = any(p in family for p in pg_keywords)
    if is_pg_branch:
        return []
    
    # Known families with groups
    if family in BRANCH_GROUPS:
        groups = BRANCH_GROUPS[family]
        if group_hint:
            # Return only the matching group
            for code, name in groups:
                if code == group_hint:
                    return [(code, name)]
            return []  # hint not found
        # Return all groups
        return groups
    
    # Single-branch families (ECE, ME, SM) - return with default code ""
    if family in ("ECE", "ME", "SM"):
        return [(family[0].upper(), family)]
    
    # Fallback
    return [(family, family)]


def expand_branch_slots(normalized_slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Expand slots that have a branch family into individual branch rows.
    
    Key transformation: CSE with all entries -> CSE-A + CSE-B (two rows per original).
    DS -> DS-E1 + DS-E2.
    ECE -> single row, etc.
    """
    result = []
    
    for slot in normalized_slots:
        branch = slot["Branch"]
        code = slot["Course Code"]
        instructor = slot["Instructor"]
        room = slot["Room"]
        time_str = slot["Time"]
        semester = slot["Semester"]
        day = slot["Day"]
        semester_orig = int(semester) if semester and str(semester).isdigit() else None
        
        # Split this branch into specific branches
        branches = split_branch_into_codes(branch)
        
        for group_code, full_branch in branches:
            new_slot = dict(slot)
            new_slot["Branch"] = full_branch
            # If there's a group code, also set it as a hint in the course code parsing
            # We don't modify the course code itself - that's handled elsewhere
            
            # Adjust instructor if needed for combined branches
            # (in the PDF, some OE cells span multiple branches)
            
            result.append(new_slot)
    
    return result


def normalize_slot(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalize one raw parser slot into zero or more normalized slots.
    
    Returns a list because a CSE row may expand into CSE-A and CSE-B.
    """
    semester = raw.get("semester", 1)
    branch = raw.get("branch_or_program", "")
    day = raw.get("day", "")
    course_code = raw.get("course_code", "")
    instructor = raw.get("instructor")
    room = raw.get("room", "")
    remarks = raw.get("remarks")
    start_time = raw.get("start_time")
    end_time = raw.get("end_time")
    
    # Normalize fields
    sem_display = semester_to_roman(semester) if not is_pg(semester, branch) else "PG"
    day_full = normalize_day(day)
    time_str = normalize_time(start_time, end_time)
    room_clean = normalize_room(room)
    course_clean = normalize_course_code(course_code)
    
    # Split branch
    branches = split_branch_into_codes(branch)
    
    result = []
    for group_code, full_branch in branches:
        result.append({
            "Semester": sem_display,
            "Branch": full_branch,
            "Day": day_full,
            "Course Code": course_clean,
            "Instructor": instructor or "",
            "Room": room_clean,
            "Time": time_str,
            "Remarks": remarks or "",
        })
    
    return result


def normalize_slots(raw_slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a list of raw parser slots."""
    normalized = []
    for raw in raw_slots:
        normalized.extend(normalize_slot(raw))
    return normalized