# parser.py edit log (recovered from OpenCode session export)

Every COMPLETED edit to backend/app/features/timetable/parser.py, in order. `OLD` = text that was replaced, `NEW` = what it became.
Caveat: the file was also modified outside this session between msgs 2783-2784 (dedup block / Step 1c), so some later OLD anchors will not match your file verbatim. Use NEW blocks as the source of truth for intended behaviour.


## Edit 1 — msg 371 — 2026-10-10 04:36 UTC
Intent: The issue is that "TBA" (To Be Announced) is not recognized as a valid room by the parser. It's treated as a placeholder instead of a valid room value. Let me fix this.

### OLD
```python
def _is_room_token(token: str) -> bool:
    """
    Is this token a room name?

    Covers the shapes the published grid uses: ``L-102``, ``CR104``, ``CR-104``,
    ``CC-GF``, ``CC 3F``, ``CC-2F``, ``AUDITORIUM``. A course code is never one of
    these, because it puts subject letters directly before the digits with no
    separator.

    Two limits keep names that merely look like rooms out:

    - at most **three** letters before the number. ``MAKE5`` fits the shape but is
      a garbled cell, not a room; ``CR``, ``CC`` and ``L`` are the real buildings.
    - at least **two** digits after a single letter. ``A1``, ``B2`` and ``G1`` are
      lab groups in this document, not rooms; ``L102`` and ``CC2`` are.
    """
    if not token:
        return False
    candidate = token.strip().strip("()").upper().replace(" ", "")
    if not candidate or candidate in {"CR", "CC", "LAB", "GF"}:
        return False
    # A course code also fits letters-then-digits ("CS5031"), so a subject
    # prefix is never a room: it is decided by _is_course first.
    if _is_course(candidate):
        return False

    letters = re.fullmatch(r"([A-Z]{1,4})-?(\d{1,4})", candidate)
    if letters:
        prefix, digits = letters.groups()
        return _prefix_can_be_a_building(prefix, digits)

    # A building with a number *and* a floor: "CC2-GF", "CC-3F".
    if re.fullmatch(rf"[A-Z]{{1,3}}\d{{1,3}}-{FLOOR_PATTERN}", candidate):
        return True
    # A building joined to a floor: "CC-GF", "CC-3F", "CC-FF".
    if re.fullmatch(rf"[A-Z]{{1,3}}-?{FLOOR_PATTERN}", candidate):
        return True
    return candidate in {"AUDITORIUM", "AUDI", "SEMINARHALL"}
```

### NEW
```python
def _is_room_token(token: str) -> bool:
    """
    Is this token a room name?

    Covers the shapes the published grid uses: ``L-102``, ``CR104``, ``CR-104``,
    ``CC-GF``, ``CC 3F``, ``CC-2F``, ``AUDITORIUM``. A course code is never one of
    these, because it puts subject letters directly before the digits with no
    separator.

    Two limits keep names that merely look like rooms out:

    - at most **three** letters before the number. ``MAKE5`` fits the shape but is
      a garbled cell, not a room; ``CR``, ``CC`` and ``L`` are the real buildings.
    - at least **two** digits after a single letter. ``A1``, ``B2`` and ``G1`` are
      lab groups in this document, not rooms; ``L102`` and ``CC2`` are.

    "TBA" (To Be Announced) is explicitly accepted as a valid room placeholder.
    """
    if not token:
        return False
    candidate = token.strip().strip("()").upper().replace(" ", "")
    if not candidate or candidate in {"CR", "CC", "LAB", "GF"}:
        return False
    # "TBA" (To Be Announced) is a valid room value meaning room not yet assigned
    if candidate == "TBA":
        return True
    # A course code also fits letters-then-digits ("CS5031"), so a subject
    # prefix is never a room: it is decided by _is_course first.
    if _is_course(candidate):
        return False

    letters = re.fullmatch(r"([A-Z]{1,4})-?(\d{1,4})", candidate)
    if letters:
        prefix, digits = letters.groups()
        return _prefix_can_be_a_building(prefix, digits)

    # A building with a number *and* a floor: "CC2-GF", "CC-3F".
    if re.fullmatch(rf"[A-Z]{{1,3}}\d{{1,3}}-{FLOOR_PATTERN}", candidate):
        return True
    # A building joined to a floor: "CC-GF", "CC-3F", "CC-FF".
    if re.fullmatch(rf"[A-Z]{{1,3}}-?{FLOOR_PATTERN}", candidate):
        return True
    return candidate in {"AUDITORIUM", "AUDI", "SEMINARHALL"}
```


## Edit 2 — msg 372 — 2026-10-10 04:36 UTC
Intent: The issue is that "TBA" (To Be Announced) is not recognized as a valid room by the parser. It's treated as a placeholder instead of a valid room value. Let me fix this.

### OLD
```python
def normalize_room(room: str) -> str:
    """Normalize room strings: 'L 201' -> 'L-201', 'CR 103' -> 'CR-103'."""
    if not room:
        return ""
    room = room.strip().upper()
    # Insert dash between letters and digits if missing
    room = re.sub(r"([A-Z]+)\s*(\d+)", r"\1-\2", room)
    # Collapse multiple spaces/dashes
    return re.sub(r"\s+", " ", room).replace(" - ", "-").replace(" -", "-").replace("- ", "-")
```

### NEW
```python
def normalize_room(room: str) -> str:
    """Normalize room strings: 'L 201' -> 'L-201', 'CR 103' -> 'CR-103'."""
    if not room:
        return ""
    room = room.strip().upper()
    # "TBA" (To Be Announced) is a valid room value - preserve it
    if room == "TBA":
        return "TBA"
    # Insert dash between letters and digits if missing
    room = re.sub(r"([A-Z]+)\s*(\d+)", r"\1-\2", room)
    # Collapse multiple spaces/dashes
    return re.sub(r"\s+", " ", room).replace(" - ", "-").replace(" -", "-").replace("- ", "-")
```


## Edit 3 — msg 373 — 2026-10-10 04:37 UTC
Intent: The issue is that "TBA" (To Be Announced) is not recognized as a valid room by the parser. It's treated as a placeholder instead of a valid room value. Let me fix this.

### OLD
```python
# Placeholders a timetable uses instead of real data. These must never be
# mistaken for a course, so a cell containing only one of them parses to nothing.
PLACEHOLDER_RE = re.compile(r"^[A-Z/]*$|^(TBA|TBC|N/?A|NIL|NONE|STAFF|STAFF\s*\d*|\d*)$", re.IGNORECASE)
```

### NEW
```python
# Placeholders a timetable uses instead of real data. These must never be
# mistaken for a course, so a cell containing only one of them parses to nothing.
# "TBA" and "TBC" are valid room values (To Be Announced / Confirmed), so they
# are excluded from this list - they are handled in _is_room_token instead.
PLACEHOLDER_RE = re.compile(r"^[A-Z/]*$|^(TBC|N/?A|NIL|NONE|STAFF|STAFF\s*\d*|\d*)$", re.IGNORECASE)
```


## Edit 4 — msg 397 — 2026-10-10 04:44 UTC
Intent: The issue is that `L` (used for lab courses like `ME3010L`) is also a building code for rooms (`L-102`, `L-206`). When the tokenizer encounters `ME3010L-MZA-L-206`, the `L` in the course code can get confused with the bu

### OLD
```python
def _split_welded_code(tokens: List[str]) -> List[str]:
    """
    Separate a course code from initials the grid ran together.

    ``ME8016HSN-CR107`` and ``EC5C01_MDB-`` are a course and its teacher with
    nothing between them. Left alone, the whole thing is read as one long course
    code and the teacher is lost. A single trailing ``L`` is left attached,
    because that is a lab paper's suffix.
    """
    split: List[str] = []
    for token in tokens:
        piece = _repair_course_code(token)
        match = WELDED_INNER_RE.match(piece) or WELDED_RE.match(piece)
        if match:
            code, initials = match.group(1), match.group(2)
            # "CS3010L" is a lab, not initials.
            if len(initials) >= 2 and not _is_course(initials):
                split.extend([code, initials])
                continue
        split.append(piece)
    return split
```

### NEW
```python
def _split_welded_code(tokens: List[str]) -> List[str]:
    """
    Separate a course code from initials the grid ran together.

    ``ME8016HSN-CR107`` and ``EC5C01_MDB-`` are a course and its teacher with
    nothing between them. Left alone, the whole thing is read as one long course
    code and the teacher is lost. A single trailing ``L`` is left attached,
    because that is a lab paper's suffix.
    """
    # First pass: split welded course+initials
    split: List[str] = []
    for token in tokens:
        piece = _repair_course_code(token)
        match = WELDED_INNER_RE.match(piece) or WELDED_RE.match(piece)
        if match:
            code, initials = match.group(1), match.group(2)
            # "CS3010L" is a lab, not initials.
            if len(initials) >= 2 and not _is_course(initials):
                split.extend([code, initials])
                continue
        split.append(piece)

    # Second pass: rejoin a course code that was split from its lab suffix "L"
    # e.g. ["ME3010", "L", "MZA"] -> ["ME3010L", "MZA"]
    # This happens when the PDF writes "ME3010 L" with a space before the lab suffix.
    rejoined: List[str] = []
    i = 0
    while i < len(split):
        if (
            i + 1 < len(split)
            and split[i + 1] == "L"
            and _is_course(split[i] + "L")
            and not _is_course(split[i])
        ):
            # The "L" is a lab suffix that got separated from its course code.
            rejoined.append(split[i] + "L")
            i += 2
        else:
            rejoined.append(split[i])
            i += 1

    return rejoined
```


## Edit 5 — msg 493 — 2026-10-10 05:04 UTC
Intent: Now I understand the issues. Let me fix both:

### OLD
```python
# A trailing letter on a full-length code: a lab paper ("CS3010L"), or a
    # combined course the grid splits by letter ("EC203a/EC203b" -> "EC204A").
    return bool(re.match(r"^[A-Z]{2,4}\d{3,4}[A-Z]\d{0,3}$", token))
```

### NEW
```python
# A trailing letter on a full-length code: a lab paper ("CS3010L"), or a
    # combined course the grid splits by letter ("EC203a/EC203b" -> "EC204A").
    # We match it but strip the trailing 'L' for lab papers.
    m = re.match(r"^([A-Z]{2,4}\d{3,4})[A-Z]\d{0,3}$", token)
    if m:
        return True
    return False
```


## Edit 6 — msg 494 — 2026-10-10 05:05 UTC
Intent: Now I understand the issues. Let me fix both:

### OLD
```python
for token in tokens:
        compact = token.upper().replace(" ", "")
        if compact in consumed:
            continue
        if not course_code and _is_course(compact):
            course_code = compact
            consumed.add(compact)
```

### NEW
```python
for token in tokens:
        compact = token.upper().replace(" ", "")
        if compact in consumed:
            continue
        if not course_code and _is_course(compact):
            # Strip trailing 'L' lab suffix from course codes (e.g., ME3010L -> ME3010)
            course_code = re.sub(r'^([A-Z]{2,4}\d{3,4})[A-Z]$', r'\1', compact)
            consumed.add(compact)
```


## Edit 7 — msg 513 — 2026-10-10 05:14 UTC
Intent: 

### OLD
```python
#: The Saturday Sem-1 "Extra" section in the PDF has no branch labels,
#: so the day-section parser emits those slots with branch="Unknown".
#: Collect every distinct Sem-1 branch that appears elsewhere in the
#: timetable and replicate the Unknown slots for each of them.
```

### NEW
```python
#: The Saturday Sem-1 "Extra" section in the PDF has no branch labels,
#: so the day-section parser emits those slots with branch="Unknown".
#: Collect every distinct Sem-1 branch that appears elsewhere in the
#: timetable and replicate the Unknown slots for each of them.
def _expand_unknown_sem1_saturday(slots: List[Dict]) -> List[Dict]:
    sem1_branches = {
        s["branch_or_program"]
        for s in slots
        if s["semester"] == 1 and s["branch_or_program"] != "Unknown"
    }
    if not sem1_branches:
        return slots

    unknown_sat = [
        s for s in slots
        if s["semester"] == 1 and s["day"] == "Sat" and s["branch_or_program"] == "Unknown"
    ]
    if not unknown_sat:
        return slots

    expanded = []
    for slot in slots:
        # Skip the original Unknown-branch Saturday Sem-1 slots; we replace them
        # with per-branch copies below.
        if slot in unknown_sat:
            continue
        expanded.append(slot)

    for slot in unknown_sat:
        for branch in sorted(sem1_branches):
            expanded.append({**slot, "branch_or_program": branch})
    return expanded


def _post_process_slots(slots: List[Dict]) -> List[Dict]:
    """
    Post-process parsed slots to fix common issues:

    1. Strip trailing 'L' lab suffix from course codes (e.g., ME3010L -> ME3010).
    2. Merge duplicate entries: if the same course appears twice on the same day
       with different rooms (one TBA, one real), keep the one with the real room.
    """
    # Step 1: Strip trailing 'L' from course codes
    for slot in slots:
        code = slot.get("course_code", "")
        if code and re.match(r"^[A-Z]{2,4}\d{3,4}[A-Z]$", code):
            # Trailing single letter after full code -> lab suffix
            slot["course_code"] = code[:-1]

    # Step 2: Deduplicate - merge entries with same course/day/start_time but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        key = (slot.get("day"), slot.get("course_code"), slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    return list(seen.values())


#: The Saturday Sem-1 "Extra" section in the PDF has no branch labels,
#: so the day-section parser emits those slots with branch="Unknown".
#: Collect every distinct Sem-1 branch that appears elsewhere in the
#: timetable and replicate the Unknown slots for each of them.
```


## Edit 8 — msg 514 — 2026-10-10 05:14 UTC
Intent: 

### OLD
```python
raw = {"tables": tables}

    return {
```

### NEW
```python
raw = {"tables": tables}

    # Post-process: fix course codes (strip lab suffix) and merge duplicate entries
    slots = _post_process_slots(slots)

    return {
```


## Edit 9 — msg 2036 — 2026-10-10 23:19 UTC
Intent: Now I understand the full picture. The issues are:

### OLD
```python
def _post_process_slots(slots: List[Dict]) -> List[Dict]:
    """
    Post-process parsed slots to fix common issues:

    1. Strip trailing 'L' lab suffix from course codes (e.g., ME3010L -> ME3010).
    2. Merge duplicate entries: if the same course appears twice on the same day
       with different rooms (one TBA, one real), keep the one with the real room.
    """
    # Step 1: Strip trailing 'L' from course codes
    for slot in slots:
        code = slot.get("course_code", "")
        if code and re.match(r"^[A-Z]{2,4}\d{3,4}[A-Z]$", code):
            # Trailing single letter after full code -> lab suffix
            slot["course_code"] = code[:-1]

    # Step 2: Deduplicate - merge entries with same course/day/start_time but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        key = (slot.get("day"), slot.get("course_code"), slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    return list(seen.values())
```

### NEW
```python
def _post_process_slots(slots: List[Dict]) -> List[Dict]:
    """
    Post-process parsed slots to fix common issues:

    1. Keep lab course codes intact (e.g., ME3010L stays ME3010L) - the 'L'
       identifies the lab component. Deduplication still works on the base
       code because we compare case-insensitively and with/without the L.
    2. Merge duplicate entries: if the same course appears twice on the same day
       with different rooms (one TBA, one real), keep the one with the real room.
    """
    # Step 1: Normalize course codes for dedup (compare without trailing L)
    # but keep the original code with L for display/attendance.
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Track the base code (without trailing single L) for dedup key
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            slot["_course_base"] = code[:-1]
        else:
            slot["_course_base"] = code

    # Step 2: Deduplicate - merge entries with same base course/day/start_time but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        key = (slot.get("day"), base, slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```


## Edit 10 — msg 2038 — 2026-10-10 23:20 UTC
Intent: Now I'll add lab venue recognition to `_is_room_token` and the fragment merger.

### OLD
```python
def _is_room_token(token: str) -> bool:
    """
    Is this token a room name?

    Covers the shapes the published grid uses: ``L-102``, ``CR104``, ``CR-104``,
    ``CC-GF``, ``CC 3F``, ``CC-2F``, ``AUDITORIUM``. A course code is never one of
    these, because it puts subject letters directly before the digits with no
    separator.

    Two limits keep names that merely look like rooms out:

    - at most **three** letters before the number. ``MAKE5`` fits the shape but is
      a garbled cell, not a room; ``CR``, ``CC`` and ``L`` are the real buildings.
    - at least **two** digits after a single letter. ``A1``, ``B2`` and ``G1`` are
      lab groups in this document, not rooms; ``L102`` and ``CC2`` are.

    "TBA" (To Be Announced) is explicitly accepted as a valid room placeholder.
    """
    if not token:
        return False
    candidate = token.strip().strip("()").upper().replace(" ", "")
    if not candidate or candidate in {"CR", "CC", "LAB", "GF"}:
        return False
    # "TBA" (To Be Announced) is a valid room value meaning room not yet assigned
    if candidate == "TBA":
        return True
    # A course code also fits letters-then-digits ("CS5031"), so a subject
    # prefix is never a room: it is decided by _is_course first.
    if _is_course(candidate):
        return False

    letters = re.fullmatch(r"([A-Z]{1,4})-?(\d{1,4})", candidate)
    if letters:
        prefix, digits = letters.groups()
        return _prefix_can_be_a_building(prefix, digits)

    # A building with a number *and* a floor: "CC2-GF", "CC-3F".
    if re.fullmatch(rf"[A-Z]{{1,3}}\d{{1,3}}-{FLOOR_PATTERN}", candidate):
        return True
    # A building joined to a floor: "CC-GF", "CC-3F", "CC-FF".
    if re.fullmatch(rf"[A-Z]{{1,3}}-?{FLOOR_PATTERN}", candidate):
        return True
    return candidate in {"AUDITORIUM", "AUDI", "SEMINARHALL"}
```

### NEW
```python
#: Lab/venue suffixes that appear after a building code.
LAB_VENUE_SUFFIXES = ("LAB", "WORKSHOP", "VLSI")


def _is_room_token(token: str) -> bool:
    """
    Is this token a room name?

    Covers the shapes the published grid uses: ``L-102``, ``CR104``, ``CR-104``,
    ``CC-GF``, ``CC 3F``, ``CC-2F``, ``AUDITORIUM``, ``CPPS Lab``, ``HMT Lab``.
    A course code is never one of these, because it puts subject letters directly
    before the digits with no separator.

    Two limits keep names that merely look like rooms out:

    - at most **three** letters before the number. ``MAKE5`` fits the shape but is
      a garbled cell, not a room; ``CR``, ``CC`` and ``L`` are the real buildings.
    - at least **two** digits after a single letter. ``A1``, ``B2`` and ``G1`` are
      lab groups in this document, not rooms; ``L102`` and ``CC2`` are.

    "TBA" (To Be Announced) is explicitly accepted as a valid room placeholder.
    """
    if not token:
        return False
    candidate = token.strip().strip("()").upper().replace(" ", "")
    if not candidate or candidate in {"CR", "CC", "LAB", "GF"}:
        return False
    # "TBA" (To Be Announced) is a valid room value meaning room not yet assigned
    if candidate == "TBA":
        return True
    # A course code also fits letters-then-digits ("CS5031"), so a subject
    # prefix is never a room: it is decided by _is_course first.
    if _is_course(candidate):
        return False

    letters = re.fullmatch(r"([A-Z]{1,4})-?(\d{1,4})", candidate)
    if letters:
        prefix, digits = letters.groups()
        return _prefix_can_be_a_building(prefix, digits)

    # A building with a number *and* a floor: "CC2-GF", "CC-3F".
    if re.fullmatch(rf"[A-Z]{{1,3}}\d{{1,3}}-{FLOOR_PATTERN}", candidate):
        return True
    # A building joined to a floor: "CC-GF", "CC-3F", "CC-FF".
    if re.fullmatch(rf"[A-Z]{{1,3}}-?{FLOOR_PATTERN}", candidate):
        return True

    # Lab / workshop venues: building + "Lab" / "Workshop" / "VLSI"
    # e.g. "CPPSLab", "HMTLab", "MCLab", "AMPLab", "VLSILab", "Workshop"
    for suffix in LAB_VENUE_SUFFIXES:
        if candidate.endswith(suffix) and len(candidate) > len(suffix):
            prefix = candidate[:-len(suffix)]
            if prefix in BUILDING_CODES:
                return True
    if candidate in {"LAB", "WORKSHOP"}:
        return True

    return candidate in {"AUDITORIUM", "AUDI", "SEMINARHALL"}
```


## Edit 11 — msg 2040 — 2026-10-10 23:20 UTC
Intent: Now I need to update the room fragment merger to join building + "Lab"/"Workshop" tokens.

### OLD
```python
def _merge_room_fragments(tokens: List[str]) -> List[str]:
    """
    Rejoin a room that the tokenizer split across pieces.

    ``CC-3F``, ``CR 104`` and ``CC 3F`` arrive as separate tokens once surrounding
    separators are treated as field breaks. A building code immediately followed
    by a number or floor is one room, so the two are joined back together.
    """
    merged: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None

        if following is not None and _ROOM_BUILDING_RE.match(token.upper().strip("()")):
            tail = following.strip("()")
            # "CR" + "104" or "3F" -> "CR-104" / "CR-3F"
            if re.fullmatch(r"\d{1,4}|\d{1,2}F|GF", tail, re.IGNORECASE):
                merged.append(f"{token}-{tail}")
                index += 2
                continue

        merged.append(token)
        index += 1

    return merged
```

### NEW
```python
def _merge_room_fragments(tokens: List[str]) -> List[str]:
    """
    Rejoin a room that the tokenizer split across pieces.

    ``CC-3F``, ``CR 104`` and ``CC 3F`` arrive as separate tokens once surrounding
    separators are treated as field breaks. A building code immediately followed
    by a number or floor is one room, so the two are joined back together.

    Also joins building + lab/venue suffix: ``CPPS`` + ``Lab`` -> ``CPPS Lab``.
    """
    merged: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None

        if following is not None and _ROOM_BUILDING_RE.match(token.upper().strip("()")):
            tail = following.strip("()")
            # "CR" + "104" or "3F" -> "CR-104" / "CR-3F"
            if re.fullmatch(r"\d{1,4}|\d{1,2}F|GF", tail, re.IGNORECASE):
                merged.append(f"{token}-{tail}")
                index += 2
                continue
            # "CPPS" + "Lab" / "Workshop" / "VLSI" -> "CPPS Lab"
            if tail.upper() in LAB_VENUE_SUFFIXES:
                merged.append(f"{token} {tail}")
                index += 2
                continue

        merged.append(token)
        index += 1

    return merged
```


## Edit 12 — msg 2048 — 2026-10-10 23:22 UTC
Intent: Now I need to add the lab venue merging to the complex `_merge_room_fragments` function that's actually used.

### OLD
```python
# Pass 2: a bare building code followed by a number or a floor.
    index = 0
    while index < len(merged):
        token = merged[index].strip()
        following = merged[index + 1] if index + 1 < len(merged) else None
        if following is not None and _is_building_token(token):
            tail = following.strip()
            if re.fullmatch(r"\d{1,4}", tail) or _is_floor_token(tail):
                merged[index : index + 2] = [f"{token}-{tail}"]
                index += 1
                continue
        index += 1

    # Pass 3: a floor joins a room.
```

### NEW
```python
# Pass 2: a bare building code followed by a number or a floor.
    index = 0
    while index < len(merged):
        token = merged[index].strip()
        following = merged[index + 1] if index + 1 < len(merged) else None
        if following is not None and _is_building_token(token):
            tail = following.strip()
            if re.fullmatch(r"\d{1,4}", tail) or _is_floor_token(tail):
                merged[index : index + 2] = [f"{token}-{tail}"]
                index += 1
                continue
        index += 1

    # Pass 2b: a bare building code followed by a lab/venue suffix
    # e.g. "CPPS" + "Lab" -> "CPPS Lab", "HMT" + "Lab" -> "HMT Lab"
    index = 0
    while index < len(merged):
        token = merged[index].strip()
        following = merged[index + 1] if index + 1 < len(merged) else None
        if following is not None and _is_building_token(token):
            tail = following.strip()
            if tail.upper() in LAB_VENUE_SUFFIXES:
                merged[index : index + 2] = [f"{token} {tail}"]
                index += 1
                continue
        index += 1

    # Pass 3: a floor joins a room.
```


## Edit 13 — msg 2053 — 2026-10-10 23:22 UTC
Intent: Found it - line 548-549 strips the L from course codes. Let me fix this.

### OLD
```python
for token in tokens:
        compact = token.upper().replace(" ", "")
        if compact in consumed:
            continue
        if not course_code and _is_course(compact):
            # Strip trailing 'L' lab suffix from course codes (e.g., ME3010L -> ME3010)
            course_code = re.sub(r'^([A-Z]{2,4}\d{3,4})[A-Z]$', r'\1', compact)
            consumed.add(compact)
```

### NEW
```python
for token in tokens:
        compact = token.upper().replace(" ", "")
        if compact in consumed:
            continue
        if not course_code and _is_course(compact):
            # Keep lab suffix (trailing 'L') - it identifies the lab component.
            # Only strip a single trailing letter if it's NOT 'L' (for cases like ME3010A).
            if re.match(r"^[A-Z]{2,4}\d{3,4}L$", compact, re.IGNORECASE):
                course_code = compact  # Keep ME3010L, CS3010L, etc.
            else:
                # Strip trailing single letter (e.g., ME3010A -> ME3010)
                course_code = re.sub(r'^([A-Z]{2,4}\d{3,4})[A-Z]$', r'\1', compact)
            consumed.add(compact)
```


## Edit 14 — msg 2056 — 2026-10-10 23:23 UTC
Intent: Now let me add the missing building codes (MC, AMP, VLSI).

### OLD
```python
BUILDING_CODES = ("CR", "CC", "L", "LAB", "NB", "AUD", "AUDI", "HMT", "CPPS", "SH", "TR")
```

### NEW
```python
BUILDING_CODES = ("CR", "CC", "L", "LAB", "NB", "AUD", "AUDI", "HMT", "CPPS", "SH", "TR", "MC", "AMP", "VLSI")
```


## Edit 15 — msg 2065 — 2026-10-10 23:24 UTC
Intent: The issue is that `EC5N03L` has a letter inside the number portion (`N`) AND a trailing `L`. Let me update `_is_course` to handle this pattern.

### OLD
```python
# prefix + digits + a letter inside the number, then digits: "EC5C01".
    # At least one digit must follow the letter, or the shape also swallows
    # fragments of a damaged code such as "ME5D", which the PDF truncates to
    # nothing usable.
    if re.match(r"^[A-Z]{2,4}\d{1,2}[A-Z]\d{1,3}$", token):
        return True

    # A trailing letter on a full-length code: a lab paper ("CS3010L"), or a
    # combined course the grid splits by letter ("EC203a/EC203b" -> "EC204A").
    # We match it but strip the trailing 'L' for lab papers.
    m = re.match(r"^([A-Z]{2,4}\d{3,4})[A-Z]\d{0,3}$", token)
    if m:
        return True
    return False
```

### NEW
```python
# prefix + digits + a letter inside the number, then digits: "EC5C01".
    # At least one digit must follow the letter, or the shape also swallows
    # fragments of a damaged code such as "ME5D", which the PDF truncates to
    # nothing usable.
    if re.match(r"^[A-Z]{2,4}\d{1,2}[A-Z]\d{1,3}$", token):
        return True

    # Lab course with letter inside the number AND trailing lab suffix:
    # "EC5N03L", "CS8K12L" - prefix + digits/letter/digits + L
    if re.match(r"^[A-Z]{2,4}\d{1,2}[A-Z]\d{1,3}L$", token, re.IGNORECASE):
        return True

    # A trailing letter on a full-length code: a lab paper ("CS3010L"), or a
    # combined course the grid splits by letter ("EC203a/EC203b" -> "EC204A").
    # We match it but strip the trailing 'L' for lab papers.
    m = re.match(r"^([A-Z]{2,4}\d{3,4})[A-Z]\d{0,3}$", token)
    if m:
        return True
    return False
```


## Edit 16 — msg 2072 — 2026-10-10 23:25 UTC
Intent: I'll add a pass in `_split_welded_code` to handle trailing batch markers.

### OLD
```python
def _split_welded_code(tokens: List[str]) -> List[str]:
    """
    Separate a course code from initials the grid ran together.

    ``ME8016HSN-CR107`` and ``EC5C01_MDB-`` are a course and its teacher with
    nothing between them. Left alone, the whole thing is read as one long course
    code and the teacher is lost. A single trailing ``L`` is left attached,
    because that is a lab paper's suffix.
    """
    # First pass: split welded course+initials
    split: List[str] = []
    for token in tokens:
        piece = _repair_course_code(token)
        match = WELDED_INNER_RE.match(piece) or WELDED_RE.match(piece)
        if match:
            code, initials = match.group(1), match.group(2)
            # "CS3010L" is a lab, not initials.
            if len(initials) >= 2 and not _is_course(initials):
                split.extend([code, initials])
                continue
        split.append(piece)

    # Second pass: rejoin a course code that was split from its lab suffix "L"
    # e.g. ["ME3010", "L", "MZA"] -> ["ME3010L", "MZA"]
    # This happens when the PDF writes "ME3010 L" with a space before the lab suffix.
    rejoined: List[str] = []
    i = 0
    while i < len(split):
        if (
            i + 1 < len(split)
            and split[i + 1] == "L"
            and _is_course(split[i] + "L")
            and not _is_course(split[i])
        ):
            # The "L" is a lab suffix that got separated from its course code.
            rejoined.append(split[i] + "L")
            i += 2
        else:
            rejoined.append(split[i])
            i += 1

    return rejoined
```

### NEW
```python
def _split_welded_code(tokens: List[str]) -> List[str]:
    """
    Separate a course code from initials the grid ran together.

    ``ME8016HSN-CR107`` and ``EC5C01_MDB-`` are a course and its teacher with
    nothing between them. Left alone, the whole thing is read as one long course
    code and the teacher is lost. A single trailing ``L`` is left attached,
    because that is a lab paper's suffix.
    """
    # First pass: split welded course+initials
    split: List[str] = []
    for token in tokens:
        piece = _repair_course_code(token)
        match = WELDED_INNER_RE.match(piece) or WELDED_RE.match(piece)
        if match:
            code, initials = match.group(1), match.group(2)
            # "CS3010L" is a lab, not initials.
            if len(initials) >= 2 and not _is_course(initials):
                split.extend([code, initials])
                continue
        split.append(piece)

    # Second pass: rejoin a course code that was split from its lab suffix "L"
    # e.g. ["ME3010", "L", "MZA"] -> ["ME3010L", "MZA"]
    # This happens when the PDF writes "ME3010 L" with a space before the lab suffix.
    rejoined: List[str] = []
    i = 0
    while i < len(split):
        if (
            i + 1 < len(split)
            and split[i + 1] == "L"
            and _is_course(split[i] + "L")
            and not _is_course(split[i])
        ):
            # The "L" is a lab suffix that got separated from its course code.
            rejoined.append(split[i] + "L")
            i += 2
        else:
            rejoined.append(split[i])
            i += 1

    # Third pass: handle trailing batch markers on lab course codes
    # - "ME3010L-0" -> split into "ME3010L" and "0"
    # - "ME3010L0"  -> strip trailing single digit -> "ME3010L"
    final: List[str] = []
    for token in rejoined:
        # Split "CODE-L" where L is a lab suffix followed by "-<digit>"
        split_dash = re.match(r"^(.+L)-\d$", token, re.IGNORECASE)
        if split_dash:
            final.append(split_dash.group(1))
            # The digit will be dropped later as noise
            continue
        # Strip trailing single digit from lab code: "ME3010L0" -> "ME3010L"
        strip_digit = re.match(r"^(.+L)\d$", token, re.IGNORECASE)
        if strip_digit:
            final.append(strip_digit.group(1))
            continue
        final.append(token)

    return final
```


## Edit 17 — msg 2101 — 2026-10-10 23:33 UTC
Intent: You're right - batch information is critical for distinguishing lab sections. Let me update the parser to append the batch letter as a suffix to the course code.

### OLD
```python
# Third pass: handle trailing batch markers on lab course codes
    # - "ME3010L-0" -> split into "ME3010L" and "0"
    # - "ME3010L0"  -> strip trailing single digit -> "ME3010L"
    final: List[str] = []
    for token in rejoined:
        # Split "CODE-L" where L is a lab suffix followed by "-<digit>"
        split_dash = re.match(r"^(.+L)-\d$", token, re.IGNORECASE)
        if split_dash:
            final.append(split_dash.group(1))
            # The digit will be dropped later as noise
            continue
        # Strip trailing single digit from lab code: "ME3010L0" -> "ME3010L"
        strip_digit = re.match(r"^(.+L)\d$", token, re.IGNORECASE)
        if strip_digit:
            final.append(strip_digit.group(1))
            continue
        final.append(token)

    return final
```

### NEW
```python
# Third pass: handle trailing batch markers on lab course codes
    # - "ME3010L-0" -> split into "ME3010L" and "0"
    # - "ME3010L0"  -> strip trailing single digit -> "ME3010L"
    # Fourth pass: detect "Batch X" and append batch letter to the course code
    final: List[str] = []
    batch_letter: str = ""
    for token in rejoined:
        # Split "CODE-L" where L is a lab suffix followed by "-<digit>"
        split_dash = re.match(r"^(.+L)-\d$", token, re.IGNORECASE)
        if split_dash:
            final.append(split_dash.group(1))
            continue
        # Strip trailing single digit from lab code: "ME3010L0" -> "ME3010L"
        strip_digit = re.match(r"^(.+L)\d$", token, re.IGNORECASE)
        if strip_digit:
            final.append(strip_digit.group(1))
            continue
        final.append(token)

    # Fourth pass: detect "Batch" + letter and append to nearest course code
    # Tokens like ["ME3010L", "MZA", "Batch", "A", "CPPS", "Lab"]
    # -> append "A" to "ME3010L" -> "ME3010L-A"
    if "Batch" in final:
        batch_idx = final.index("Batch")
        if batch_idx + 1 < len(final):
            letter = final[batch_idx + 1].strip().upper()
            if re.fullmatch(r"[A-Z]", letter):
                batch_letter = letter
                # Find the course code token (first one that looks like a course)
                for i, t in enumerate(final):
                    if _is_course(t.upper().replace(" ", "")):
                        final[i] = f"{t}-{letter}"
                        break

    # Remove "Batch" and its letter from the token list
    if batch_letter:
        final = [t for t in final if t != "Batch" and t != batch_letter]

    return final
```


## Edit 18 — msg 2106 — 2026-10-10 23:35 UTC
Intent: The course code with batch suffix isn't recognized. Let me update `_is_course` to handle the `-A` / `-B` batch suffix.

### OLD
```python
# Lab course with letter inside the number AND trailing lab suffix:
    # "EC5N03L", "CS8K12L" - prefix + digits/letter/digits + L
    if re.match(r"^[A-Z]{2,4}\d{1,2}[A-Z]\d{1,3}L$", token, re.IGNORECASE):
        return True

    # A trailing letter on a full-length code: a lab paper ("CS3010L"), or a
    # combined course the grid splits by letter ("EC203a/EC203b" -> "EC204A").
    # We match it but strip the trailing 'L' for lab papers.
    m = re.match(r"^([A-Z]{2,4}\d{3,4})[A-Z]\d{0,3}$", token)
    if m:
        return True
    return False
```

### NEW
```python
# Lab course with letter inside the number AND trailing lab suffix:
    # "EC5N03L", "CS8K12L" - prefix + digits/letter/digits + L
    if re.match(r"^[A-Z]{2,4}\d{1,2}[A-Z]\d{1,3}L$", token, re.IGNORECASE):
        return True

    # Lab course with batch suffix: "ME3010L-A", "CS3010L-B"
    if re.match(r"^[A-Z]{2,4}\d{3,4}L-[A-Z]$", token, re.IGNORECASE):
        return True

    # A trailing letter on a full-length code: a lab paper ("CS3010L"), or a
    # combined course the grid splits by letter ("EC203a/EC203b" -> "EC204A").
    # We match it but strip the trailing 'L' for lab papers.
    m = re.match(r"^([A-Z]{2,4}\d{3,4})[A-Z]\d{0,3}$", token)
    if m:
        return True
    return False
```


## Edit 19 — msg 2260 — 2026-10-11 03:38 UTC
Intent: You're right - the same course ME3010L should have consistent batch suffix across all days. The PDF just omits "Batch A" on Thursday. Let me fix this by propagating batch suffixes across same-course occurrences.

### OLD
```python
# Step 1: Normalize course codes for dedup (compare without trailing L)
    # but keep the original code with L for display/attendance.
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Track the base code (without trailing single L) for dedup key
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            slot["_course_base"] = code[:-1]
        else:
            slot["_course_base"] = code

    # Step 2: Deduplicate - merge entries with same base course/day/start_time but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        key = (slot.get("day"), base, slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```

### NEW
```python
# Step 1: Normalize course codes for dedup (compare without trailing L)
    # but keep the original code with L for display/attendance.
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Track the base code (without trailing single L) for dedup key
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            slot["_course_base"] = code[:-1]
        else:
            slot["_course_base"] = code

    # Step 1b: Propagate batch suffixes across same-course occurrences
    # If ME3010L-A appears on Monday, other ME3010L entries for same branch/semester
    # should also get the -A suffix (PDF often omits batch on some days).
    batch_by_course: Dict[tuple, str] = {}
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Extract batch suffix (e.g., "ME3010L-A" -> base="ME3010L", batch="A")
        match = re.match(r"^([A-Z]{2,4}\d{3,4}L)-([A-Z])$", code, re.IGNORECASE)
        if match:
            base, batch = match.group(1), match.group(2).upper()
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            if key not in batch_by_course or batch < batch_by_course[key]:
                batch_by_course[key] = batch

    # Apply batch suffixes to slots missing them
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            base = code
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            if key in batch_by_course:
                slot["course_code"] = f"{base}-{batch_by_course[key]}"

    # Step 2: Deduplicate - merge entries with same base course/day/start_time but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        key = (slot.get("day"), base, slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```


## Edit 20 — msg 2268 — 2026-10-11 03:39 UTC
Intent: The logic needs to assign sequential batch letters (A, B, C...) based on chronological order, not just propagate the first one found. Let me fix this.

### OLD
```python
# Step 1b: Propagate batch suffixes across same-course occurrences
    # If ME3010L-A appears on Monday, other ME3010L entries for same branch/semester
    # should also get the -A suffix (PDF often omits batch on some days).
    batch_by_course: Dict[tuple, str] = {}
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Extract batch suffix (e.g., "ME3010L-A" -> base="ME3010L", batch="A")
        match = re.match(r"^([A-Z]{2,4}\d{3,4}L)-([A-Z])$", code, re.IGNORECASE)
        if match:
            base, batch = match.group(1), match.group(2).upper()
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            if key not in batch_by_course or batch < batch_by_course[key]:
                batch_by_course[key] = batch

    # Apply batch suffixes to slots missing them
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            base = code
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            if key in batch_by_course:
                slot["course_code"] = f"{base}-{batch_by_course[key]}"
```

### NEW
```python
# Step 1b: Assign sequential batch suffixes to lab courses with same base/branch/semester
    # If ME3010L appears on Mon 10:00 and Thu 10:00 for same branch/semester,
    # they're different batches -> assign A, B, C... chronologically.
    from collections import defaultdict
    
    # Group slots by (base_course, branch, semester)
    course_groups = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Check if it's a lab course without batch suffix
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            base = code
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            course_groups[key].append(slot)

    # For each group with multiple occurrences, assign sequential batches A, B, C...
    for key, group_slots in course_groups.items():
        if len(group_slots) > 1:
            # Sort by day order then start time
            day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            group_slots.sort(key=lambda s: (day_order.get(s.get("day", ""), 99), s.get("start_time", "")))
            # Assign sequential batch letters A, B, C...
            for i, slot in enumerate(group_slots):
                batch_letter = chr(ord('A') + i)
                slot["course_code"] = f"{slot['course_code']}-{batch_letter}"
```


## Edit 21 — msg 2276 — 2026-10-11 03:41 UTC
Intent: The issue is that Monday's entry already has "-A" suffix from the PDF, so my grouping logic skips it (regex only matches plain `ME3010L`). I need to include already-suffixed entries in the grouping.

### OLD
```python
# Step 1b: Assign sequential batch suffixes to lab courses with same base/branch/semester
    # If ME3010L appears on Mon 10:00 and Thu 10:00 for same branch/semester,
    # they're different batches -> assign A, B, C... chronologically.
    from collections import defaultdict
    
    # Group slots by (base_course, branch, semester)
    course_groups = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Check if it's a lab course without batch suffix
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            base = code
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            course_groups[key].append(slot)

    # For each group with multiple occurrences, assign sequential batches A, B, C...
    for key, group_slots in course_groups.items():
        if len(group_slots) > 1:
            # Sort by day order then start time
            day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            group_slots.sort(key=lambda s: (day_order.get(s.get("day", ""), 99), s.get("start_time", "")))
            # Assign sequential batch letters A, B, C...
            for i, slot in enumerate(group_slots):
                batch_letter = chr(ord('A') + i)
                slot["course_code"] = f"{slot['course_code']}-{batch_letter}"
```

### NEW
```python
# Step 1b: Assign sequential batch suffixes to lab courses with same base/branch/semester
    # If ME3010L appears on Mon 10:00 and Thu 10:00 for same branch/semester,
    # they're different batches -> assign A, B, C... chronologically.
    from collections import defaultdict
    
    # Group slots by (base_course, branch, semester)
    # Include both plain "ME3010L" and already-suffixed "ME3010L-A"
    course_groups = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Check if it's a lab course (with or without batch suffix)
        base_match = re.match(r"^([A-Z]{2,4}\d{3,4}L)(?:-([A-Z]))?$", code, re.IGNORECASE)
        if base_match:
            base = base_match.group(1)
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            course_groups[key].append(slot)

    # For each group with multiple occurrences, assign sequential batches A, B, C...
    for key, group_slots in course_groups.items():
        if len(group_slots) > 1:
            # Sort by day order then start time
            day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            group_slots.sort(key=lambda s: (day_order.get(s.get("day", ""), 99), s.get("start_time", "")))
            # Assign sequential batch letters A, B, C...
            for i, slot in enumerate(group_slots):
                batch_letter = chr(ord('A') + i)
                base = re.match(r"^([A-Z]{2,4}\d{3,4}L)", slot["course_code"], re.IGNORECASE).group(1)
                slot["course_code"] = f"{base}-{batch_letter}"
```


## Edit 22 — msg 2343 — 2026-10-11 04:02 UTC
Intent: Now I understand the issue. The Friday page has combined branch labels like "ECE ME SM", "CSE ECE", "ME SM" in the first column that the parser treats as single branch labels. Also, row 34 has "DS OE2M10-TC-CR109 VII Sem

### OLD
```python
# A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    branch = " ".join(first.split())
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```

### NEW
```python
# A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    # Handle combined branch labels like "ECE ME SM", "CSE ECE", "ME SM"
                    # Split on known separators and process each branch separately
                    cleaned = " ".join(first.split())
                    branch_candidates = re.split(r"[\s,;/&+]+", cleaned)
                    # Filter to only valid branch families
                    valid_branches = []
                    for candidate in branch_candidates:
                        if _is_branch_label(candidate):
                            valid_branches.append(candidate)
                    if valid_branches:
                        # For combined labels, we'll process each branch in the row separately
                        branch = valid_branches[0]  # Primary branch for this row
                        slot._extra_branches = valid_branches[1:]  # Store extras for row expansion
                    else:
                        branch = cleaned
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```


## Edit 23 — msg 2345 — 2026-10-11 04:02 UTC
Intent: Now I understand the issue. The Friday page has combined branch labels like "ECE ME SM", "CSE ECE", "ME SM" in the first column that the parser treats as single branch labels. Also, row 34 has "DS OE2M10-TC-CR109 VII Sem

### OLD
```python
if not day or not time_columns:
                continue

            for col_index, slot_start, slot_end in time_columns:
                if col_index >= len(row):
                    continue
                for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    if not course_code:
                        continue
                    slots.append({
                        "day": day,
                        "start_time": slot_start,
                        "end_time": slot_end,
                        "room": room or "TBA",
                        "course_code": course_code,
                        "instructor": instructor or None,
                        "branch_or_program": branch,
                        "semester": semester,
                    })
```

### NEW
```python
if not day or not time_columns:
                continue

            # Handle combined branch labels (e.g., "ECE ME SM" -> separate slots for ECE, ME, SM)
            branches_to_process = [branch]
            if hasattr(slot, '_extra_branches') and slot._extra_branches:
                branches_to_process.extend(slot._extra_branches)

            for col_index, slot_start, slot_end in time_columns:
                if col_index >= len(row):
                    continue
                for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    if not course_code:
                        continue
                    # Create a slot for each branch in combined labels
                    for br in branches_to_process:
                        slots.append({
                            "day": day,
                            "start_time": slot_start,
                            "end_time": slot_end,
                            "room": room or "TBA",
                            "course_code": course_code,
                            "instructor": instructor or None,
                            "branch_or_program": br,
                            "semester": semester,
                        })
```


## Edit 24 — msg 2347 — 2026-10-11 04:03 UTC
Intent: Now I understand the issue. The Friday page has combined branch labels like "ECE ME SM", "CSE ECE", "ME SM" in the first column that the parser treats as single branch labels. Also, row 34 has "DS OE2M10-TC-CR109 VII Sem

### OLD
```python
# A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    # Handle combined branch labels like "ECE ME SM", "CSE ECE", "ME SM"
                    # Split on known separators and process each branch separately
                    cleaned = " ".join(first.split())
                    branch_candidates = re.split(r"[\s,;/&+]+", cleaned)
                    # Filter to only valid branch families
                    valid_branches = []
                    for candidate in branch_candidates:
                        if _is_branch_label(candidate):
                            valid_branches.append(candidate)
                    if valid_branches:
                        # For combined labels, we'll process each branch in the row separately
                        branch = valid_branches[0]  # Primary branch for this row
                        slot._extra_branches = valid_branches[1:]  # Store extras for row expansion
                    else:
                        branch = cleaned
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```

### NEW
```python
# A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    # Handle combined branch labels like "ECE ME SM", "CSE ECE", "ME SM"
                    # Split on known separators and process each branch separately
                    cleaned = " ".join(first.split())
                    branch_candidates = re.split(r"[\s,;/&+]+", cleaned)
                    # Filter to only valid branch families
                    valid_branches = []
                    for candidate in branch_candidates:
                        if _is_branch_label(candidate):
                            valid_branches.append(candidate)
                    if valid_branches:
                        # For combined labels, we'll process each branch in the row separately
                        branch = valid_branches[0]  # Primary branch for this row
                        slot._extra_branches = valid_branches[1:]  # Store extras for row expansion
                    else:
                        branch = cleaned
                # Handle mixed content like "DS OE2M10-TC-CR109 VII Sem"
                # Extract branch from mixed content (branch + course + semester band)
                elif re.search(r'\b(I|V|VII)\s*Sem\b', first, re.IGNORECASE):
                    # Extract branch from start of string before course/semester
                    # e.g., "DS OE2M10-TC-CR109 VII Sem" -> "DS"
                    branch_match = re.match(r"^([A-Z]{2,4})\b", first)
                    if branch_match:
                        branch = branch_match.group(1)
                    else:
                        branch = "Unknown"
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```


## Edit 25 — msg 2350 — 2026-10-11 04:03 UTC
Intent: 

### OLD
```python
# A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    # Handle combined branch labels like "ECE ME SM", "CSE ECE", "ME SM"
                    # Split on known separators and process each branch separately
                    cleaned = " ".join(first.split())
                    branch_candidates = re.split(r"[\s,;/&+]+", cleaned)
                    # Filter to only valid branch families
                    valid_branches = []
                    for candidate in branch_candidates:
                        if _is_branch_label(candidate):
                            valid_branches.append(candidate)
                    if valid_branches:
                        # For combined labels, we'll process each branch in the row separately
                        branch = valid_branches[0]  # Primary branch for this row
                        slot._extra_branches = valid_branches[1:]  # Store extras for row expansion
                    else:
                        branch = cleaned
                # Handle mixed content like "DS OE2M10-TC-CR109 VII Sem"
                # Extract branch from mixed content (branch + course + semester band)
                elif re.search(r'\b(I|V|VII)\s*Sem\b', first, re.IGNORECASE):
                    # Extract branch from start of string before course/semester
                    # e.g., "DS OE2M10-TC-CR109 VII Sem" -> "DS"
                    branch_match = re.match(r"^([A-Z]{2,4})\b", first)
                    if branch_match:
                        branch = branch_match.group(1)
                    else:
                        branch = "Unknown"
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```

### NEW
```python
# A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    # Handle combined branch labels like "ECE ME SM", "CSE ECE", "ME SM"
                    # Split on known separators and process each branch separately
                    cleaned = " ".join(first.split())
                    branch_candidates = re.split(r"[\s,;/&+]+", cleaned)
                    # Filter to only valid branch families
                    valid_branches = []
                    for candidate in branch_candidates:
                        if _is_branch_label(candidate):
                            valid_branches.append(candidate)
                    if valid_branches:
                        # For combined labels, we'll process each branch in the row separately
                        branch = valid_branches[0]  # Primary branch for this row
                        extra_branches = valid_branches[1:]  # Store extras for row expansion
                    else:
                        branch = cleaned
                # Handle mixed content like "DS OE2M10-TC-CR109 VII Sem"
                # Extract branch from mixed content (branch + course + semester band)
                elif re.search(r'\b(I|V|VII)\s*Sem\b', first, re.IGNORECASE):
                    # Extract branch from start of string before course/semester
                    # e.g., "DS OE2M10-TC-CR109 VII Sem" -> "DS"
                    branch_match = re.match(r"^([A-Z]{2,4})\b", first)
                    if branch_match:
                        branch = branch_match.group(1)
                    else:
                        branch = "Unknown"
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```


## Edit 26 — msg 2352 — 2026-10-11 04:04 UTC
Intent: 

### OLD
```python
# Handle combined branch labels (e.g., "ECE ME SM" -> separate slots for ECE, ME, SM)
            branches_to_process = [branch]
            if hasattr(slot, '_extra_branches') and slot._extra_branches:
                branches_to_process.extend(slot._extra_branches)

            for col_index, slot_start, slot_end in time_columns:
```

### NEW
```python
# Handle combined branch labels (e.g., "ECE ME SM" -> separate slots for ECE, ME, SM)
            branches_to_process = [branch]
            # Check if we stored extra branches for this row
            if 'extra_branches' in locals():
                branches_to_process.extend(extra_branches)

            for col_index, slot_start, slot_end in time_columns:
```


## Edit 27 — msg 2370 — 2026-10-11 04:08 UTC
Intent: 

### OLD
```python
# A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    # Handle combined branch labels like "ECE ME SM", "CSE ECE", "ME SM"
                    # Split on known separators and process each branch separately
                    cleaned = " ".join(first.split())
                    branch_candidates = re.split(r"[\s,;/&+]+", cleaned)
                    # Filter to only valid branch families
                    valid_branches = []
                    for candidate in branch_candidates:
                        if _is_branch_label(candidate):
                            valid_branches.append(candidate)
                    if valid_branches:
                        # For combined labels, we'll process each branch in the row separately
                        branch = valid_branches[0]  # Primary branch for this row
                        extra_branches = valid_branches[1:]  # Store extras for row expansion
                    else:
                        branch = cleaned
                # Handle mixed content like "DS OE2M10-TC-CR109 VII Sem"
                # Extract branch from mixed content (branch + course + semester band)
                elif re.search(r'\b(I|V|VII)\s*Sem\b', first, re.IGNORECASE):
                    # Extract branch from start of string before course/semester
                    # e.g., "DS OE2M10-TC-CR109 VII Sem" -> "DS"
                    branch_match = re.match(r"^([A-Z]{2,4})\b", first)
                    if branch_match:
                        branch = branch_match.group(1)
                    else:
                        branch = "Unknown"
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```

### NEW
```python
# A blank leading cell continues the branch of the row above.
            if first:
                extra_branches = []  # Initialize for this row
                if _is_branch_label(first):
                    # Handle combined branch labels like "ECE ME SM", "CSE ECE", "ME SM"
                    # Split on known separators and process each branch separately
                    cleaned = " ".join(first.split())
                    branch_candidates = re.split(r"[\s,;/&+]+", cleaned)
                    # Filter to only valid branch families
                    valid_branches = []
                    for candidate in branch_candidates:
                        if _is_branch_label(candidate):
                            valid_branches.append(candidate)
                    if valid_branches:
                        # For combined labels, we'll process each branch in the row separately
                        branch = valid_branches[0]  # Primary branch for this row
                        extra_branches = valid_branches[1:]  # Store extras for row expansion
                    else:
                        branch = cleaned
                # Handle mixed content like "DS OE2M10-TC-CR109 VII Sem"
                # Extract branch from mixed content (branch + course + semester band)
                elif re.search(r'\b(I|V|VII)\s*Sem\b', first, re.IGNORECASE):
                    # Extract branch from start of string before course/semester
                    # e.g., "DS OE2M10-TC-CR109 VII Sem" -> "DS"
                    branch_match = re.match(r"^([A-Z]{2,4})\b", first)
                    if branch_match:
                        branch = branch_match.group(1)
                    else:
                        branch = "Unknown"
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue
```


## Edit 28 — msg 2392 — 2026-10-11 04:14 UTC
Intent: 

### OLD
```python
def _is_branch_label(text: str) -> bool:
    """
    Is this the leading column of a data row, i.e. a branch or programme?

    True for "CSE", "ECE", "M.Tech (AI)", "Ph.D. (NS)"; false for a semester
    band ("V Sem") or a time. A blank cell means "same branch as the row above",
    which is how the published grid continues a branch across its groups.
    """
    if not text:
        return False
    if SEMESTER_BAND_RE.match(text):
        return False
    return not (TIME_HEADER_RE.search(text) or TIME_SINGLE_RE.match(text))
```

### NEW
```python
def _is_branch_label(text: str) -> bool:
    """
    Is this the leading column of a data row, i.e. a branch or programme?

    True for "CSE", "ECE", "M.Tech (AI)", "Ph.D. (NS)"; false for a semester
    band ("V Sem") or a time. A blank cell means "same branch as the row above",
    which is how the published grid continues a branch across its groups.
    """
    if not text:
        return False
    if SEMESTER_BAND_RE.match(text):
        return False
    if TIME_HEADER_RE.search(text) or TIME_SINGLE_RE.match(text):
        return False
    # Only accept known branch codes/families to avoid treating course codes
    # or random text as branch labels.
    valid_branches = {
        "CSE", "CSE A", "CSE B",
        "ECE",
        "ME",
        "SM",
        "DS",
        "PG",
        "MDes", "MDES",
        "M.Tech", "M.Tech (AI)", "M.Tech (CSP)", "M.Tech (P&C)", "M.Tech (Nano)",
        "M.Tech (Design)", "M.Tech (CAD/CAM)", "M.Tech (Mfg)", "M.Tech (Mechatronics)",
        "Ph.D.", "Ph.D. (CSE)", "Ph.D. (ECE)", "Ph.D. (ME)", "Ph.D. (Design)", "Ph.D. (NS)",
        "MDes", "MDes (Sem I)", "MDes (Sem III)",
    }
    cleaned = " ".join(text.split())
    if cleaned in valid_branches:
        return True
    # Also accept branch families (CSE, ECE, ME, SM, DS, PG, MDES)
    if cleaned in {"CSE", "ECE", "ME", "SM", "DS", "PG", "MDES"}:
        return True
    return False
```


## Edit 29 — msg 2394 — 2026-10-11 04:14 UTC
Intent: 

### OLD
```python
def _is_branch_label(text: str) -> bool:
    """
    Is this the leading column of a data row, i.e. a branch or programme?

    True for "CSE", "ECE", "M.Tech (AI)", "Ph.D. (NS)"; false for a semester
    band ("V Sem") or a time. A blank cell means "same branch as the row above",
    which is how the published grid continues a branch across its groups.
    """
    if not text:
        return False
    if SEMESTER_BAND_RE.match(text):
        return False
    if TIME_HEADER_RE.search(text) or TIME_SINGLE_RE.match(text):
        return False
    # Only accept known branch codes/families to avoid treating course codes
    # or random text as branch labels.
    valid_branches = {
        "CSE", "CSE A", "CSE B",
        "ECE",
        "ME",
        "SM",
        "DS",
        "PG",
        "MDes", "MDES",
        "M.Tech", "M.Tech (AI)", "M.Tech (CSP)", "M.Tech (P&C)", "M.Tech (Nano)",
        "M.Tech (Design)", "M.Tech (CAD/CAM)", "M.Tech (Mfg)", "M.Tech (Mechatronics)",
        "Ph.D.", "Ph.D. (CSE)", "Ph.D. (ECE)", "Ph.D. (ME)", "Ph.D. (Design)", "Ph.D. (NS)",
        "MDes", "MDes (Sem I)", "MDes (Sem III)",
    }
    cleaned = " ".join(text.split())
    if cleaned in valid_branches:
        return True
    # Also accept branch families (CSE, ECE, ME, SM, DS, PG, MDES)
    if cleaned in {"CSE", "ECE", "ME", "SM", "DS", "PG", "MDES"}:
        return True
    return False
```

### NEW
```python
def _is_branch_label(text: str) -> bool:
    """
    Is this the leading column of a data row, i.e. a branch or programme?

    True for "CSE", "ECE", "M.Tech (AI)", "Ph.D. (NS)"; false for a semester
    band ("V Sem") or a time. A blank cell means "same branch as the row above",
    which is how the published grid continues a branch across its groups.
    """
    if not text:
        return False
    if SEMESTER_BAND_RE.match(text):
        return False
    if TIME_HEADER_RE.search(text) or TIME_SINGLE_RE.match(text):
        return False
    # Check if the whole text is a known branch
    valid_branches = {
        "CSE", "CSE A", "CSE B",
        "ECE",
        "ME",
        "SM",
        "DS",
        "PG",
        "MDes", "MDES",
        "M.Tech", "M.Tech (AI)", "M.Tech (CSP)", "M.Tech (P&C)", "M.Tech (Nano)",
        "M.Tech (Design)", "M.Tech (CAD/CAM)", "M.Tech (Mfg)", "M.Tech (Mechatronics)",
        "Ph.D.", "Ph.D. (CSE)", "Ph.D. (ECE)", "Ph.D. (ME)", "Ph.D. (Design)", "Ph.D. (NS)",
        "MDes", "MDes (Sem I)", "MDes (Sem III)",
    }
    cleaned = " ".join(text.split())
    if cleaned in valid_branches:
        return True
    # Also accept branch families (CSE, ECE, ME, SM, DS, PG, MDES)
    if cleaned in {"CSE", "ECE", "ME", "SM", "DS", "PG", "MDES"}:
        return True
    # For combined labels like "ECE ME SM", check if all components are valid branch families
    parts = re.split(r"[\s,;/&+]+", cleaned)
    if len(parts) > 1:
        return all(p in {"CSE", "ECE", "ME", "SM", "DS", "PG", "MDES"} for p in parts)
    return False
```


## Edit 30 — msg 2404 — 2026-10-11 04:16 UTC
Intent: 

### OLD
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        key = (slot.get("day"), base, slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```

### NEW
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/branch but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        key = (slot.get("day"), base, slot.get("branch_or_program", ""), slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```


## Edit 31 — msg 2455 — 2026-10-11 04:46 UTC
Intent: The PDF has `OE3M27/ME5D02` — **two electives in one cell** — but the parser treats it as one code. Let me add slash-splitting for electives and a reinforcement pattern-learning model.

### OLD
```python
def _starts_course(chunk: str) -> bool:
    """Does this fragment begin with something shaped like a course code?"""
    token = chunk.strip("()")
    return bool(re.match(r"^(?:OE|OI)?[A-Z]{1,4}[-_. ]?\d", token, re.IGNORECASE))
```

### NEW
```python
def _starts_course(chunk: str) -> bool:
    """Does this fragment begin with something shaped like a course code?"""
    token = chunk.strip("()")
    return bool(re.match(r"^(?:OE|OI)?[A-Z]{1,4}[-_. ]?\d", token, re.IGNORECASE))


def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    """
    # Match patterns like "OE3M27/ME5D02" or "OE2C02/OE2C12"
    # Both sides must look like course codes (letters + digits)
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    result = []
    for part in parts:
        part = part.strip()
        if part and re.match(r"^(?:OE|OI)?[A-Z]{1,4}\d", part, re.IGNORECASE):
            result.append(part)
        elif result:
            # Append to previous if it's a continuation (e.g., room)
            result[-1] = f"{result[-1]}/{part}"
    
    return result if result else [text]
```


## Edit 32 — msg 2456 — 2026-10-11 04:47 UTC
Intent: Now let me integrate the slash-splitting into `_split_cell_entries` and add the reinforcement pattern-learning model.

### OLD
```python
text = " ".join((cell or "").split())
    if not text or text.lower() in EMPTY_CELL_VALUES:
        return []

    # A group label such as "OE1:" or "OE11:" precedes its papers.
    group = re.match(r"^(OE|OI)\s*\d+\s*:\s*", text, re.IGNORECASE)
    if group:
        text = text[group.end():]

    chunks = [c for c in text.split() if c]
```

### NEW
```python
text = " ".join((cell or "").split())
    if not text or text.lower() in EMPTY_CELL_VALUES:
        return []

    # A group label such as "OE1:" or "OE11:" precedes its papers.
    group = re.match(r"^(OE|OI)\s*\d+\s*:\s*", text, re.IGNORECASE)
    if group:
        text = text[group.end():]

    # Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"]
    # The PDF maker often crams multiple electives into one cell.
    slash_parts = _split_slash_electives(text)
    if len(slash_parts) > 1:
        # Process each part separately and combine
        all_entries = []
        for part in slash_parts:
            part_entries = _split_cell_entries(part)
            all_entries.extend(part_entries)
        return all_entries

    chunks = [c for c in text.split() if c]
```


## Edit 33 — msg 2460 — 2026-10-11 04:48 UTC
Intent: Now let me integrate the reinforcement model into the parser and create a migration for the new table.

### OLD
```python
from collections import defaultdict
    
    # Group slots by (base_course, branch, semester)
```

### NEW
```python
from collections import defaultdict

    # Apply reinforcement patterns to fix known PDF maker mistakes
    from features.timetable.reinforcement import get_reinforcement_model
    reinforcement = get_reinforcement_model()

    # Group slots by (base_course, branch, semester)
```


## Edit 34 — msg 2462 — 2026-10-11 04:49 UTC
Intent: Now let me integrate the reinforcement model into the parser and create a migration for the new table.

### OLD
```python
def _post_process_slots(slots: List[Dict]) -> List[Dict]:
    """
    Post-process parsed slots to fix common issues:

    1. Keep lab course codes intact (e.g., ME3010L stays ME3010L) - the 'L'
       identifies the lab component. Deduplication still works on the base
       code because we compare case-insensitively and with/without the L.
    2. Merge duplicate entries: if the same course appears twice on the same day
       with different rooms (one TBA, one real), keep the one with the real room.
    """
    # Step 1: Normalize course codes for dedup (compare without trailing L)
    # but keep the original code with L for display/attendance.
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Track the base code (without trailing single L) for dedup key
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            slot["_course_base"] = code[:-1]
        else:
            slot["_course_base"] = code

    # Step 1b: Assign sequential batch suffixes to lab courses with same base/branch/semester
    # If ME3010L appears on Mon 10:00 and Thu 10:00 for same branch/semester,
    # they're different batches -> assign A, B, C... chronologically.
    from collections import defaultdict

    # Apply reinforcement patterns to fix known PDF maker mistakes
    from features.timetable.reinforcement import get_reinforcement_model
    reinforcement = get_reinforcement_model()

    # Group slots by (base_course, branch, semester)
    # Include both plain "ME3010L" and already-suffixed "ME3010L-A"
    course_groups = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Check if it's a lab course (with or without batch suffix)
        base_match = re.match(r"^([A-Z]{2,4}\d{3,4}L)(?:-([A-Z]))?$", code, re.IGNORECASE)
        if base_match:
            base = base_match.group(1)
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            course_groups[key].append(slot)
```

### NEW
```python
def _post_process_slots(slots: List[Dict]) -> List[Dict]:
    """
    Post-process parsed slots to fix common issues:

    1. Keep lab course codes intact (e.g., ME3010L stays ME3010L) - the 'L'
       identifies the lab component. Deduplication still works on the base
       code because we compare case-insensitively and with/without the L.
    2. Merge duplicate entries: if the same course appears twice on the same day
       with different rooms (one TBA, one real), keep the one with the real room.
    3. Apply reinforcement patterns to fix known PDF maker mistakes.
    """
    # Step 1: Normalize course codes for dedup (compare without trailing L)
    # but keep the original code with L for display/attendance.
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Track the base code (without trailing single L) for dedup key
        if re.match(r"^[A-Z]{2,4}\d{3,4}L$", code, re.IGNORECASE):
            slot["_course_base"] = code[:-1]
        else:
            slot["_course_base"] = code

    # Step 1b: Assign sequential batch suffixes to lab courses with same base/branch/semester
    # If ME3010L appears on Mon 10:00 and Thu 10:00 for same branch/semester,
    # they're different batches -> assign A, B, C... chronologically.
    from collections import defaultdict

    # Apply reinforcement patterns to fix known PDF maker mistakes
    from features.timetable.reinforcement import get_reinforcement_model
    reinforcement = get_reinforcement_model()

    # Group slots by (base_course, branch, semester)
    # Include both plain "ME3010L" and already-suffixed "ME3010L-A"
    course_groups = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        if not code:
            continue
        # Check if it's a lab course (with or without batch suffix)
        base_match = re.match(r"^([A-Z]{2,4}\d{3,4}L)(?:-([A-Z]))?$", code, re.IGNORECASE)
        if base_match:
            base = base_match.group(1)
            branch = slot.get("branch_or_program", "")
            semester = slot.get("semester")
            key = (base, branch, semester)
            course_groups[key].append(slot)
```


## Edit 35 — msg 2464 — 2026-10-11 04:50 UTC
Intent: Now let me apply the reinforcement patterns to fix the slash-joined electives. Let me add the pattern application to the parser.

### OLD
```python
# For each group with multiple occurrences, assign sequential batches A, B, C...
    for key, group_slots in course_groups.items():
        if len(group_slots) > 1:
            # Sort by day order then start time
            day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            group_slots.sort(key=lambda s: (day_order.get(s.get("day", ""), 99), s.get("start_time", "")))
            # Assign sequential batch letters A, B, C...
            for i, slot in enumerate(group_slots):
                batch_letter = chr(ord('A') + i)
                base = re.match(r"^([A-Z]{2,4}\d{3,4}L)", slot["course_code"], re.IGNORECASE).group(1)
                slot["course_code"] = f"{base}-{batch_letter}"

    # Step 2: Deduplicate - merge entries with same base course/day/start_time/branch but different rooms
```

### NEW
```python
# For each group with multiple occurrences, assign sequential batches A, B, C...
    for key, group_slots in course_groups.items():
        if len(group_slots) > 1:
            # Sort by day order then start time
            day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            group_slots.sort(key=lambda s: (day_order.get(s.get("day", ""), 99), s.get("start_time", "")))
            # Assign sequential batch letters A, B, C...
            for i, slot in enumerate(group_slots):
                batch_letter = chr(ord('A') + i)
                base = re.match(r"^([A-Z]{2,4}\d{3,4}L)", slot["course_code"], re.IGNORECASE).group(1)
                slot["course_code"] = f"{base}-{batch_letter}"

    # Step 1c: Apply reinforcement patterns to fix known PDF maker mistakes
    # Split slash-joined electives: "OE3M27/ME5D02" -> two separate slots
    expanded_slots: List[Dict] = []
    for slot in slots:
        code = slot.get("course_code", "")
        # Check for slash-joined electives
        if "/" in code:
            parts = _split_slash_electives(code)
            if len(parts) > 1:
                # Create a separate slot for each elective
                for part in parts:
                    # Parse the part to extract course code, instructor, room
                    part_code, part_instructor, part_room = split_slot_cell(part)
                    if part_code:
                        expanded_slots.append({
                            **slot,
                            "course_code": part_code,
                            "instructor": part_instructor or slot.get("instructor"),
                            "room": part_room or slot.get("room", "TBA"),
                        })
                continue
        expanded_slots.append(slot)
    slots = expanded_slots

    # Step 2: Deduplicate - merge entries with same base course/day/start_time/branch but different rooms
```


## Edit 36 — msg 2482 — 2026-10-11 04:59 UTC
Intent: The garbled cells are being parsed but instructor/room are wrong. Let me apply the reinforcement patterns in `split_slot_cell` to clean garbled text before parsing.

### OLD
```python
if not cell:
        return "", "", ""

    # Group and role markers say who the class is for, not where it meets, so
    # they go before parsing rather than after.
    cell = ROLE_MARKER_RE.sub(" ", cell)

    tokens = _split_welded_code(_merge_room_fragments(_tokenize_cell(cell)))
```

### NEW
```python
if not cell:
        return "", "", ""

    # Group and role markers say who the class is for, not where it meets, so
    # they go before parsing rather than after.
    cell = ROLE_MARKER_RE.sub(" ", cell)

    # Apply reinforcement patterns to fix garbled PDF text
    # e.g., "OE3E40 K- DSN -CS R-C 1R 021 0 1" -> "OE3E40-SNS-CR101"
    from features.timetable.reinforcement import get_reinforcement_model
    reinforcement = get_reinforcement_model()
    cell = reinforcement.apply(cell)

    tokens = _split_welded_code(_merge_room_fragments(_tokenize_cell(cell)))
```


## Edit 37 — msg 2566 — 2026-10-11 05:59 UTC
Intent: The deduplication key includes branch (line 1450), so ME3009 with different branches (ECE, ME, SM) are treated as different entries. I need to remove branch from the dedup key.

### OLD
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/branch but different rooms
    # Prefer non-TBA rooms over TBA
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        key = (slot.get("day"), base, slot.get("branch_or_program", ""), slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```

### NEW
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time but different rooms
    # Prefer non-TBA rooms over TBA. Branch is NOT part of the key so that
    # shared-cell expansions (ECE/ME/SM) for the same course in the same room
    # are collapsed into one entry.
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        key = (slot.get("day"), base, slot.get("start_time"))
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```


## Edit 38 — msg 2604 — 2026-10-11 06:17 UTC
Intent: Now I understand the issue. The parser expands combined branches (ECE ME SM) into multiple slots at lines 1151-1175. For core courses, we should NOT expand - instead, determine the correct branch from the course code pre

### OLD
```python
# Handle combined branch labels (e.g., "ECE ME SM" -> separate slots for ECE, ME, SM)
            branches_to_process = [branch]
            # Check if we stored extra branches for this row
            if 'extra_branches' in locals():
                branches_to_process.extend(extra_branches)

            for col_index, slot_start, slot_end in time_columns:
                if col_index >= len(row):
                    continue
                for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    if not course_code:
                        continue
                    # Create a slot for each branch in combined labels
                    for br in branches_to_process:
                        slots.append({
                            "day": day,
                            "start_time": slot_start,
                            "end_time": slot_end,
                            "room": room or "TBA",
                            "course_code": course_code,
                            "instructor": instructor or None,
                            "branch_or_program": br,
                            "semester": semester,
                        })
```

### NEW
```python
# For core courses in combined branch cells, assign to correct branch based on course code prefix.
            # Electives (OE prefix) may span multiple branches and are handled separately.
            from features.exam.parser import is_open_elective, infer_branch_from_course_code

            is_elective = is_open_elective(course_code) if course_code else False
            
            # For core courses in combined branch cells, assign to correct branch based on course code prefix
            if not is_elective and extra_branches:
                # Core course in combined cell: determine correct branch from course code prefix
                course_branch = infer_branch_from_course_code(course_code)
                # Only keep the slot for the matching branch
                if course_branch and course_branch in branches_to_process:
                    assigned_branch = course_branch
                else:
                    # Fallback: use first branch if no match
                    assigned_branch = branches_to_process[0]
                branches_to_process = [assigned_branch]
            # For electives, we may want to keep all branches (they can be shared)
            # but typically electives are not branch-specific either

            for col_index, slot_start, slot_end in time_columns:
                if col_index >= len(row):
                    continue
                for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    if not course_code:
                        continue
                    
                    # Re-check elective status for each entry (in case entry has different course)
                    is_elective = is_open_elective(course_code)
                    
                    # Determine branches for this specific course
                    entry_branches = branches_to_process
                    if not is_open_elective(course_code) and extra_branches:
                        course_branch = infer_branch_from_course_code(course_code)
                        if course_branch and course_branch in branches_to_process:
                            entry_branches = [course_branch]
                        else:
                            entry_branches = [branches_to_process[0]]
                    
                    for br in entry_branches:
                        slots.append({
                            "day": day,
                            "start_time": slot_start,
                            "end_time": slot_end,
                            "room": room or "TBA",
                            "course_code": course_code,
                            "instructor": instructor or None,
                            "branch_or_program": br,
                            "semester": semester,
                        })
```


## Edit 39 — msg 2616 — 2026-10-11 06:22 UTC
Intent: Let me add debug output to the parser to see what's happening.

### OLD
```python
if not day or not time_columns:
                continue

            # For core courses in combined branch cells, assign to correct branch based on course code prefix.
            # Electives (OE prefix) may span multiple branches and are handled separately.
            from features.exam.parser import is_open_elective, infer_branch_from_course_code

            is_elective = is_open_elective(course_code) if course_code else False
            
            # For core courses in combined branch cells, assign to correct branch based on course code prefix
            if not is_elective and extra_branches:
                # Core course in combined cell: determine correct branch from course code prefix
                course_branch = infer_branch_from_course_code(course_code)
                # Only keep the slot for the matching branch
                if course_branch and course_branch in branches_to_process:
                    assigned_branch = course_branch
                else:
                    # Fallback: use first branch if no match
                    assigned_branch = branches_to_process[0]
                branches_to_process = [assigned_branch]
            # For electives, we may want to keep all branches (they can be shared)
            # but typically electives are not branch-specific either

            for col_index, slot_start, slot_end in time_columns:
                if col_index >= len(row):
                    continue
                for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    if not course_code:
                        continue
                    
                    # Re-check elective status for each entry (in case entry has different course)
                    is_elective = is_open_elective(course_code)
                    
                    # Determine branches for this specific course
                    entry_branches = branches_to_process
                    if not is_open_elective(course_code) and extra_branches:
                        course_branch = infer_branch_from_course_code(course_code)
                        if course_branch and course_branch in branches_to_process:
                            entry_branches = [course_branch]
                        else:
                            entry_branches = [branches_to_process[0]]
                    
                    for br in entry_branches:
                        slots.append({
                            "day": day,
                            "start_time": slot_start,
                            "end_time": slot_end,
                            "room": room or "TBA",
                            "course_code": course_code,
                            "instructor": instructor or None,
                            "branch_or_program": br,
                            "semester": semester,
                        })
```

### NEW
```python
if not day or not time_columns:
                continue

            # Handle combined branch labels (e.g., "ECE ME SM" -> separate slots for ECE, ME, SM)
            branches_to_process = [branch]
            # Check if we stored extra branches for this row
            if extra_branches:
                branches_to_process.extend(extra_branches)

            for col_index, slot_start, slot_end in time_columns:
                if col_index >= len(row):
                    continue
                for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    if not course_code:
                        continue
                    
                    # Check if this course is an elective (OE prefix)
                    is_elective = is_open_elective(course_code)
                    
                    # For core courses in combined branch cells, assign to correct branch based on course code prefix
                    entry_branches = branches_to_process
                    if not is_open_elective(course_code) and extra_branches:
                        # Core course in combined cell: determine correct branch from course code prefix
                        course_branch = infer_branch_from_course_code(course_code)
                        # Only keep the slot for the matching branch
                        if course_branch and course_branch in branches_to_process:
                            entry_branches = [course_branch]
                        else:
                            # Fallback: use first branch if no match
                            entry_branches = [branches_to_process[0]]
                    
                    for br in entry_branches:
                        slots.append({
                            "day": day,
                            "start_time": slot_start,
                            "end_time": slot_end,
                            "room": room or "TBA",
                            "course_code": course_code,
                            "instructor": instructor or None,
                            "branch_or_program": br,
                            "semester": semester,
                        })
```


## Edit 40 — msg 2620 — 2026-10-11 06:24 UTC
Intent: 

### OLD
```python
def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
    """
    Parse the college's published weekly grid.

    The document is laid out as one *section* per weekday rather than one column
    per weekday, so it cannot be read by looking for a row of day names:

    - a lone cell holding a weekday starts that day's section
    - the next row is the time header, e.g. ``8:00-8:55``, ``14:00-14:55``
    - ``I Sem`` / ``V Sem`` rows open a semester band
    - each data row is ``branch | group | slot | slot ...``; a blank branch cell
      continues the branch above, which is how one branch spans groups A, B, C

    Rows are matched to a student's profile later, so every branch and semester
    in the document is kept.
    """
    slots: List[Dict] = []
    warnings: List[str] = []
```

### NEW
```python
def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
    """
    Parse the college's published weekly grid.

    The document is laid out as one *section* per weekday rather than one column
    per weekday, so it cannot be read by looking for a row of day names:

    - a lone cell holding a weekday starts that day's section
    - the next row is the time header, e.g. ``8:00-8:55``, ``14:00-14:55``
    - ``I Sem`` / ``V Sem`` rows open a semester band
    - each data row is ``branch | group | slot | slot ...``; a blank branch cell
      continues the branch above, which is how one branch spans groups A, B, C

    Rows are matched to a student's profile later, so every branch and semester
    in the document is kept.
    """
    from features.exam.parser import is_open_elective, infer_branch_from_course_code
    
    slots: List[Dict] = []
    warnings: List[str] = []
```


## Edit 41 — msg 2687 — 2026-10-11 06:54 UTC
Intent: 

### OLD
```python
"semester": semester,
                        ))
```

### NEW
```python
"semester": semester,
                        })
```


## Edit 42 — msg 2785 — 2026-10-11 07:28 UTC
Intent: 

### OLD
```python
# Step 1c: Apply reinforcement patterns to fix known PDF maker mistakes
    # Split slash-joined electives: "OE3M27/ME5D02" -> two separate slots
    expanded_slots: List[Dict] = []
    for slot in slots:
        code = slot.get("course_code", "")
        # Check for slash-joined electives
        if "/" in code:
            parts = _split_slash_electives(code)
            if len(parts) > 1:
                # Create a separate slot for each elective
                for part in parts:
                    # Parse the part to extract course code, instructor, room
                    part_code, part_instructor, part_room = split_slot_cell(part)
                    if part_code:
                        expanded_slots.append({
                            **slot,
                            "course_code": part_code,
                            "instructor": part_instructor or slot.get("instructor"),
                            "room": part_room or slot.get("room", "TBA"),
                        })
                continue
        expanded_slots.append(slot)
    slots = expanded_slots

    # Step 2: Deduplicate - merge entries with same base course/day/start_time/room but different branches
    # For shared cells (ECE ME SM), keep all branches. Only deduplicate if room also matches.
    # Branch information is critical for the schedule service to filter by student's branch.
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        base = slot.get("_course_base", slot.get("course_code", ""))
        # Include branch in the dedup key so we don't collapse different branches
        key = (slot.get("day"), base, slot.get("branch_or_program", ""), slot.get("start_time"), slot.get("room", "").upper())
        room = slot.get("room", "").upper()
        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```

### NEW
```python
# Step 1c: Apply reinforcement patterns to fix known PDF maker mistakes
    # Split slash-joined electives: "OE3M27/ME5D02" -> two separate slots
    expanded_slots: List[Dict] = []
    for slot in slots:
        code = slot.get("course_code", "")
        # Check for slash-joined electives
        if "/" in code:
            parts = _split_slash_electives(code)
            if len(parts) > 1:
                # Create a separate slot for each elective
                for part in parts:
                    # Parse the part to extract course code, instructor, room
                    part_code, part_instructor, part_room = split_slot_cell(part)
                    if part_code:
                        expanded_slots.append({
                            **slot,
                            "course_code": part_code,
                            "instructor": part_instructor or slot.get("instructor"),
                            "room": part_room or slot.get("room", "TBA"),
                        })
                continue
        expanded_slots.append(slot)
    slots = expanded_slots

    # Step 2: Deduplicate - merge entries with same base course/day/start_time/room
    # For electives: no branch (empty string), dedupe by (day, base_course, start_time, end_time, room)
    # For core courses: dedupe by (day, base_course, start_time, end_time, room, branch)
    # For shared cells with core courses: only keep the branch matching the course prefix
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        branch = slot.get("branch_or_program", "")
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        room = slot.get("room", "").upper()

        # Check if this is an elective (OE prefix) - electives have no branch
        is_elective = is_open_elective(code)

        if is_open_elective(code):
            # Electives: no branch, dedupe by (day, base, start, end, room)
            key = (day, base, start, end, room)
        else:
            # Core courses: dedupe by (day, base, start, end, room, branch)
            key = (day, base, start, end, room, branch)

        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```


## Edit 43 — msg 2793 — 2026-10-11 07:30 UTC
Intent: 

### OLD
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/room
    # For electives: no branch (empty string), dedupe by (day, base_course, start_time, end_time, room)
    # For core courses: dedupe by (day, base_course, start_time, end_time, room, branch)
    # For shared cells with core courses: only keep the branch matching the course prefix
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        branch = slot.get("branch_or_program", "")
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        room = slot.get("room", "").upper()

        # Check if this is an elective (OE prefix) - electives have no branch
        is_elective = is_open_elective(code)

        if is_open_elective(code):
            # Electives: no branch, dedupe by (day, base, start, end, room)
            key = (day, base, start, end, room)
        else:
            # Core courses: dedupe by (day, base, start, end, room, branch)
            key = (day, base, start, end, room, branch)

        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```

### NEW
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/end_time
    # For electives: no branch (empty string), dedupe by (day, base_course, start_time, end_time)
    # For core courses: dedupe by (day, base_course, start_time, end_time, branch)
    # For shared cells with core courses: only keep the branch matching the course prefix
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        branch = slot.get("branch_or_program", "")
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        room = slot.get("room", "").upper()

        # Check if this is an elective (OE prefix) - electives have no branch
        is_elective = is_open_elective(code)

        if is_open_elective(code):
            # Electives: no branch, dedupe by (day, base, start, end)
            key = (day, base, start, end)
        else:
            # Core courses: dedupe by (day, base, start, end, branch)
            key = (day, base, start, end, branch)

        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())
```


## Edit 44 — msg 2829 — 2026-10-11 08:05 UTC
Intent: 

### OLD
```python
"""Timetable PDF/CSV parser with debug support."""
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import date, datetime, time, timedelta
import pdfplumber

from core.config import DAYS_ORDER, COLLEGE_START_HOUR

logger = logging.getLogger(__name__)
```

### NEW
```python
"""Timetable PDF/CSV parser with debug support."""
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import date, datetime, time, timedelta
import pdfplumber

from core.config import DAYS_ORDER, COLLEGE_START_HOUR
from features.exam.parser import is_open_elective

logger = logging.getLogger(__name__)
```


## Edit 45 — msg 2848 — 2026-10-11 08:15 UTC
Intent: Now I understand - the Saturday Sem-1 expansion expands to ALL branches, but it should use the course prefix logic. Let me fix this.

### OLD
```python
#: The Saturday Sem-1 "Extra" section in the PDF has no branch labels,
#: so the day-section parser emits those slots with branch="Unknown".
#: Collect every distinct Sem-1 branch that appears elsewhere in the
#: timetable and replicate the Unknown slots for each of them.
def _expand_unknown_sem1_saturday(slots: List[Dict]) -> List[Dict]:
    sem1_branches = {
        s["branch_or_program"]
        for s in slots
        if s["semester"] == 1 and s["branch_or_program"] != "Unknown"
    }
    if not sem1_branches:
        return slots

    unknown_sat = [
        s for s in slots
        if s["semester"] == 1 and s["day"] == "Sat" and s["branch_or_program"] == "Unknown"
    ]
    if not unknown_sat:
        return slots

    expanded = []
    for slot in slots:
        # Skip the original Unknown-branch Saturday Sem-1 slots; we replace them
        # with per-branch copies below.
        if slot in unknown_sat:
            continue
        expanded.append(slot)

    for slot in unknown_sat:
        for branch in sorted(sem1_branches):
            expanded.append({**slot, "branch_or_program": branch})
    return expanded


def _post_process_slots(slots: List[Dict]) -> List[Dict]:
```

### NEW
```python
#: The Saturday Sem-1 "Extra" section in the PDF has no branch labels,
#: so the day-section parser emits those slots with branch="Unknown".
#: For core courses, assign branch based on course code prefix.
#: For electives (OE), keep no branch (empty string).
def _expand_unknown_sem1_saturday(slots: List[Dict]) -> List[Dict]:
    unknown_sat = [
        s for s in slots
        if s["semester"] == 1 and s["day"] == "Sat" and s["branch_or_program"] == "Unknown"
    ]
    if not unknown_sat:
        return slots

    expanded = []
    for slot in slots:
        # Skip the original Unknown-branch Saturday Sem-1 slots; we replace them
        # with correctly-branched copies below.
        if slot in unknown_sat:
            continue
        expanded.append(slot)

    for slot in unknown_sat:
        code = slot.get("course_code", "")
        # Electives get no branch
        if is_open_elective(code):
            expanded.append({**slot, "branch_or_program": ""})
        else:
            # Core courses: assign branch from course code prefix
            branch = infer_branch_from_course_code(code)
            if branch:
                expanded.append({**slot, "branch_or_program": branch})
            else:
                # Fallback: if no prefix match, keep as-is (will be filtered later)
                expanded.append({**slot, "branch_or_program": ""})
    return expanded


def _post_process_slots(slots: List[Dict]) -> List[Dict]:
```


## Edit 46 — msg 2868 — 2026-10-11 08:23 UTC
Intent: The second definition (old version) is overriding my fix. Let me remove it.

### OLD
```python
#: The Saturday Sem-1 "Extra" section in the PDF has no branch labels,
#: so the day-section parser emits those slots with branch="Unknown".
#: Collect every distinct Sem-1 branch that appears elsewhere in the
#: timetable and replicate the Unknown slots for each of them.
def _expand_unknown_sem1_saturday(slots: List[Dict]) -> List[Dict]:
    sem1_branches = {
        s["branch_or_program"]
        for s in slots
        if s["semester"] == 1 and s["branch_or_program"] != "Unknown"
    }
    if not sem1_branches:
        return slots

    unknown_sat = [
        s for s in slots
        if s["semester"] == 1 and s["day"] == "Sat" and s["branch_or_program"] == "Unknown"
    ]
    if not unknown_sat:
        return slots

    expanded = []
    for slot in slots:
        # Skip the original Unknown-branch Saturday Sem-1 slots; we replace them
        # with per-branch copies below.
        if slot in unknown_sat:
            continue
        expanded.append(slot)

    for slot in unknown_sat:
        for branch in sorted(sem1_branches):
            expanded.append({**slot, "branch_or_program": branch})
    return expanded


def parse_timetable_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
```

### NEW
```python
def parse_timetable_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
```


## Edit 47 — msg 2876 — 2026-10-11 08:25 UTC
Intent: The import for `infer_branch_from_course_code` is missing. Let me add it.

### OLD
```python
from core.config import DAYS_ORDER, COLLEGE_START_HOUR
from features.exam.parser import is_open_elective
```

### NEW
```python
from core.config import DAYS_ORDER, COLLEGE_START_HOUR
from features.exam.parser import is_open_elective, infer_branch_from_course_code
```


## Edit 48 — msg 2900 — 2026-10-11 08:36 UTC
Intent: I see the issue. The parser creates multiple entries for the same course at the same time with different branches (from separate PDF rows). The deduplication logic keeps them all because they have different branches. But

### OLD
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/end_time
    # For electives: no branch (empty string), dedupe by (day, base_course, start_time, end_time)
    # For core courses: dedupe by (day, base_course, start_time, end_time, branch)
    # For shared cells with core courses: only keep the branch matching the course prefix
    seen: Dict[tuple, Dict] = {}
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        branch = slot.get("branch_or_program", "")
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        room = slot.get("room", "").upper()

        # Check if this is an elective (OE prefix) - electives have no branch
        is_elective = is_open_elective(code)

        if is_open_elective(code):
            # Electives: no branch, dedupe by (day, base, start, end)
            key = (day, base, start, end)
        else:
            # Core courses: dedupe by (day, base, start, end, branch)
            key = (day, base, start, end, branch)

        if key not in seen:
            seen[key] = slot
        else:
            existing_room = seen[key].get("room", "").upper()
            # Prefer non-TBA room
            if room != "TBA" and existing_room == "TBA":
                seen[key] = slot
            # If both are TBA or both are real, keep the first one

    # Clean up helper field
    for slot in seen.values():
        slot.pop("_course_base", None)

    return list(seen.values())


def parse_timetable_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
```

### NEW
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/end_time
    # For electives: no branch (empty string), dedupe by (day, base_course, start_time, end_time)
    # For core courses: only keep the branch matching the course prefix (e.g., NS1002 -> CSE, ME3009 -> ME)
    from collections import defaultdict

    # Group slots by (day, base, start, end)
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        key = (day, base, start, end)
        grouped[key].append(slot)

    # For each group, select the correct slot(s)
    deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
            # Electives: keep first one (all have no branch after expansion)
            deduplicated.append(group[0])
        else:
            # Core courses: find the slot where branch matches course prefix
            correct_branch = infer_branch_from_course_code(code)
            # First try to find exact match
            matched = None
            for slot in group:
                if slot.get("branch_or_program", "") == correct_branch:
                    matched = slot
                    break
            if matched:
                deduplicated.append(matched)
            else:
                # Fallback: if no exact match, prefer non-TBA room, then first
                non_tba = [s for s in group if s.get("room", "").upper() != "TBA"]
                if non_tba:
                    deduplicated.append(non_tba[0])
                else:
                    deduplicated.append(group[0])

    # Clean up helper field
    for slot in deduplicated:
        slot.pop("_course_base", None)

    return deduplicated


def parse_timetable_file(file_path: Path, is_csv: bool = False) -> Dict[str, Any]:
```


## Edit 49 — msg 2959 — 2026-10-11 08:51 UTC
Intent: The ES courses are in single-branch cells with "Unknown" branch, so the parser trusts the PDF. Let me fix the parser to use course prefix when PDF branch is "Unknown".

### OLD
```python
# For electives: no branch (they're not branch-specific)
                    # For core courses in combined branch cells, assign to correct branch based on course code prefix
                    if is_open_elective(course_code):
                        # Electives have no branch - they're not branch-specific
                        entry_branches = [""]
                    elif extra_branches:
                        # Core course in combined cell: determine correct branch from course code prefix
                        course_branch = infer_branch_from_course_code(course_code)
                        if course_branch and course_branch in branches_to_process:
                            entry_branches = [course_branch]
                        else:
                            # Fallback: use first branch if no match
                            entry_branches = [branches_to_process[0]]
                    else:
                        entry_branches = branches_to_process
```

### NEW
```python
# For electives: no branch (they're not branch-specific)
                    # For core courses in combined branch cells OR with Unknown branch, assign to correct branch based on course code prefix
                    if is_open_elective(course_code):
                        # Electives have no branch - they're not branch-specific
                        entry_branches = [""]
                    elif extra_branches or branches_to_process[0] == "Unknown":
                        # Core course in combined cell OR with Unknown branch: determine correct branch from course code prefix
                        course_branch = infer_branch_from_course_code(course_code)
                        if course_branch:
                            entry_branches = [course_branch]
                        else:
                            # Fallback: use first branch if no match
                            entry_branches = [branches_to_process[0]]
                    else:
                        entry_branches = branches_to_process
```


## Edit 50 — msg 3236 — 2026-10-11 10:44 UTC
Intent: 

### OLD
```python
def _rejoin_split_course_code(tokens: List[str]) -> List[str]:
    """
    Put back a course code the grid wrote with a space: ``HS 1001``.

    **Only at the start of the cell.** A course code is the first field, so a
    letters-then-digits pair anywhere else is something else entirely: in
    ``OE4E21-SKJ- 101`` the pair is an instructor and a room number, and joining
    it produced the nonsense room ``SKJ-101``. Likewise ``OE4L73-JAMF- C R 202``
    lost its ``C`` this way, leaving the room as ``R-202``.

    So the room reconstruction below has to do the rest.
    """
    if len(tokens) >= 2 and re.fullmatch(r"[A-Za-z]{1,4}", tokens[0]) and re.fullmatch(
        r"\d{2,4}", tokens[1]
    ):
        return [f"{tokens[0]}{tokens[1]}", *tokens[2:]]
    return tokens
```

### NEW
```python
def _rejoin_split_course_code(tokens: List[str]) -> List[str]:
    """
    Put back a course code the grid wrote with a space: ``HS 1001``.
    Also rejoin slash-separated course codes: ``OE3M27/ME5D02``.

    **Only at the start of the cell.** A course code is the first field, so a
    letters-then-digits pair anywhere else is something else entirely: in
    ``OE4E21-SKJ- 101`` the pair is an instructor and a room number, and joining
    it produced the nonsense room ``SKJ-101``. Likewise ``OE4L73-JAMF- C R 202``
    lost its ``C`` this way, leaving the room as ``R-202``.

    So the room reconstruction below has to do the rest.
    """
    # First, rejoin slash-separated course codes at the start
    # Pattern: two course codes separated by "/" -> join with "/"
    if len(tokens) >= 3 and tokens[1] == "/" and _is_course(tokens[0]) and _is_course(tokens[2]):
        return [f"{tokens[0]}/{tokens[2]}", *tokens[3:]]

    # Original: space-separated course code at start (e.g., "HS 1001")
    if len(tokens) >= 2 and re.fullmatch(r"[A-Za-z]{1,4}", tokens[0]) and re.fullmatch(
        r"\d{2,4}", tokens[1]
    ):
        return [f"{tokens[0]}{tokens[1]}", *tokens[2:]]
    return tokens
```


## Edit 51 — msg 3239 — 2026-10-11 10:45 UTC
Intent: 

### OLD
```python
if char in "/:|" or char == "\n":
            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            index += 1
            while index < length and text[index].isspace():
                index += 1
            continue
```

### NEW
```python
if char in "/:|" or char == "\n":
            # Check if "/" is between two course-like codes (e.g., OE3M27/ME5D02)
            # Don't split if it joins two course-like codes
            if char == "/":
                left = buffer[-1] if buffer else ""
                right = text[index + 1] if index + 1 < length else ""
                # Don't split if both sides look like course code characters
                if left.isalnum() and right.isalnum():
                    buffer += char
                    index += 1
                    continue

            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            index += 1
            while index < length and text[index].isspace():
                index += 1
            continue
```


## Edit 52 — msg 3249 — 2026-10-11 10:50 UTC
Intent: 

### OLD
```python
def _is_course(token: str) -> bool:
    """
    Does this token read as a course code?

    Three shapes occur in the published grid:

    - **regular** - a 2-4 letter subject prefix then 3-4 digits: ``CS5031``,
      ``ME3001``, ``NS1002``, ``HS1001``
    - **elective** - an ``OE``/``OI`` prefix with a letter inside the number:
      ``OE3E33``, ``OE4M76``
    - **letter inside, digits either side** - ``EC5C01``, ``CS8K12``,
      ``CS3010L``, where the trailing letter marks a lab or a combined paper

    ``HS 1001`` also occurs with a space, which is rejoined before this runs.
    """
    if ELECTIVE_RE.match(token):
        return True

    # prefix + 3-4 digits: "CS5031", "NS1002", "HS1001"
    if re.match(r"^[A-Z]{2,4}\d{3,4}$", token):
```

### NEW
```python
def _is_course(token: str) -> bool:
    """
    Does this token read as a course code?

    Three shapes occur in the published grid:

    - **regular** - a 2-4 letter subject prefix then 3-4 digits: ``CS5031``,
      ``ME3001``, ``NS1002``, ``HS1001``
    - **elective** - an ``OE``/``OI`` prefix with a letter inside the number:
      ``OE3E33``, ``OE4M76``
    - **letter inside, digits either side** - ``EC5C01``, ``CS8K12``,
      ``CS3010L``, where the trailing letter marks a lab or a combined paper
    - **slash-separated** - two course codes joined by slash: ``OE3M27/ME5D02``

    ``HS 1001`` also occurs with a space, which is rejoined before this runs.
    """
    # Handle slash-separated course codes (e.g., OE3M27/ME5D02)
    if "/" in token:
        parts = token.split("/")
        return all(_is_course(part) for part in parts)

    if ELECTIVE_RE.match(token):
        return True

    # prefix + 3-4 digits: "CS5031", "NS1002", "HS1001"
    if re.match(r"^[A-Z]{2,4}\d{3,4}$", token):
```


## Edit 53 — msg 3259 — 2026-10-11 10:53 UTC
Intent: 

### OLD
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/end_time
    # For electives: no branch (empty string), dedupe by (day, base_course, start_time, end_time)
    # For core courses: only keep the branch matching the course prefix (e.g., NS1002 -> CSE, ME3009 -> ME)
    from collections import defaultdict

    # Group slots by (day, base, start, end)
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        key = (day, base, start, end)
        grouped[key].append(slot)

    # For each group, select the correct slot(s)
    deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
            # Electives: keep first one (all have no branch after expansion)
            deduplicated.append(group[0])
        else:
            # Core courses: find the slot where branch matches course prefix
            correct_branch = infer_branch_from_course_code(code)
            # First try to find exact match
            matched = None
            for slot in group:
                if slot.get("branch_or_program", "") == correct_branch:
                    matched = slot
                    break
            if matched:
                deduplicated.append(matched)
            else:
                # Fallback: if no exact match, prefer non-TBA room, then first
                non_tba = [s for s in group if s.get("room", "").upper() != "TBA"]
                if non_tba:
                    deduplicated.append(non_tba[0])
                else:
                    deduplicated.append(group[0])
```

### NEW
```python
# Step 2: Deduplicate - merge entries with same base course/day/start_time/end_time
    # For electives: no branch (empty string), dedupe by (day, base_course, start_time, end_time)
    # For core courses: only keep the branch matching the course prefix (e.g., NS1002 -> CSE, ME3009 -> ME)
    from collections import defaultdict

    # Group slots by (day, base, start, end) but for electives include course code in key
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        is_elective = is_open_elective(code)
        # For electives, include course code in key to avoid deduplicating different electives at same time
        if is_elective:
            key = (day, code, start, end)
        else:
            key = (day, base, start, end)
        grouped[key].append(slot)

    # For each group, select the correct slot(s)
    deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
            # Electives: keep all (different electives can be at same time)
            deduplicated.extend(group)
        else:
            # Core courses: find the slot where branch matches course prefix
            correct_branch = infer_branch_from_course_code(code)
            # First try to find exact match
            matched = None
            for slot in group:
                if slot.get("branch_or_program", "") == correct_branch:
                    matched = slot
                    break
            if matched:
                deduplicated.append(matched)
            else:
                # Fallback: if no exact match, prefer non-TBA room, then first
                non_tba = [s for s in group if s.get("room", "").upper() != "TBA"]
                if non_tba:
                    deduplicated.append(non_tba[0])
                else:
                    deduplicated.append(group[0])
```


## Edit 54 — msg 3279 — 2026-10-11 10:59 UTC
Intent: Now I understand the issue. The `_resolve_instructor` function handles slash-joined course codes by removing the second course code, but it doesn't handle the case where "/" separates two faculty names (collaborated facu

### OLD
```python
def _resolve_instructor(parts: List[str], course_code: str) -> str:
    """
    Work out who teaches this, from whatever is left in the cell.

    The awkward part of the grid is that a class is often labelled with things
    that are not the instructor *and* not the room - "Batch A", "CPPS Lab",
    "(Extra)", "Workshop". Those used to be enough to fail the name check, and
    because the whole string was discarded the real initials went with it:
    ``ME3010L-MZA-Batch A-CPPS Lab`` lost ``MZA``.

    So the leftovers are cleaned rather than rejected:

    1. drop the class and venue words, and a "Batch X" pair as a unit
    2. drop a stray room or group label ("101", "A1", "OE3")
    3. drop a second course code, which is the other half of a slash-joined cell
       ("EC204a/EC204b" is two papers; only one became the course)
    4. if what remains reads as a name, use all of it
    5. otherwise keep the leading run of initial groups - the name is written
       first in every one of these cells, so the tail is the noise
    """
    tokens = [part.strip() for part in parts if part and part.strip()]
    cleaned: List[str] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower().strip(".,")

        if lowered in CLASS_NOISE_WORDS or lowered in VENUE_NOISE_WORDS:
            # "Batch A" is one label, not two tokens: drop the letter too.
            if lowered == "batch" and index + 1 < len(tokens) and re.fullmatch(r"[A-Za-z]", tokens[index + 1].strip()):
                index += 1
            index += 1
            continue

        # A room or group label, not a person.
        if re.fullmatch(r"\d{1,4}|[A-Z]{1,3}-?\d{1,4}", token, re.IGNORECASE):
            index += 1
            continue

        cleaned.append(token)
        index += 1

    # The other paper in "EC204a/EC204b-PR/KD/SNS": a code, so not a teacher.
    if course_code and len(cleaned) > 1:
        cleaned = [
            token for token in cleaned if not _is_course(token.upper().replace(" ", ""))
        ] or cleaned

    if not cleaned:
        return ""

    candidate = " ".join(cleaned).strip()
    candidate = ROLE_MARKER_RE.sub("", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)

    if candidate and INSTRUCTOR_RE.match(candidate):
        name = candidate
    else:
        # Fall back to the leading run of initials, which is where the name is.
        salvaged: List[str] = []
        for token in cleaned:
            if INSTRUCTOR_RE.match(token):
                salvaged.append(token)
            else:
                break
        name = " ".join(salvaged).strip()
```

### NEW
```python
def _resolve_instructor(parts: List[str], course_code: str) -> str:
    """
    Work out who teaches this, from whatever is left in the cell.

    The awkward part of the grid is that a class is often labelled with things
    that are not the instructor *and* not the room - "Batch A", "CPPS Lab",
    "(Extra)", "Workshop". Those used to be enough to fail the name check, and
    because the whole string was discarded the real initials went with it:
    ``ME3010L-MZA-Batch A-CPPS Lab`` lost ``MZA``.

    So the leftovers are cleaned rather than rejected:

    1. drop the class and venue words, and a "Batch X" pair as a unit
    2. drop a stray room or group label ("101", "A1", "OE3")
    3. drop a second course code, which is the other half of a slash-joined cell
       ("EC204a/EC204b" is two papers; only one became the course)
    5. if what remains reads as a name, use all of it
    5. otherwise keep the leading run of initial groups - the name is written
       first in every one of these cells, so the tail is the noise

    Special handling:
    - "/" between course codes: already handled by cell parsing (split into separate slots)
    - "/" between faculty names: indicates collaborated faculty, keep both names
    """
    tokens = [part.strip() for part in parts if part and part.strip()]
    cleaned: List[str] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower().strip(".,")

        if lowered in CLASS_NOISE_WORDS or lowered in VENUE_NOISE_WORDS:
            # "Batch A" is one label, not two tokens: drop the letter too.
            if lowered == "batch" and index + 1 < len(tokens) and re.fullmatch(r"[A-Za-z]", tokens[index + 1].strip()):
                index += 1
            index += 1
            continue

        # A room or group label, not a person.
        if re.fullmatch(r"\d{1,4}|[A-Z]{1,3}-?\d{1,4}", token, re.IGNORECASE):
            index += 1
            continue

        cleaned.append(token)
        index += 1

    # The other paper in "EC204a/EC204b-PR/KD/SNS": a code, so not a teacher.
    if course_code and len(cleaned) > 1:
        cleaned = [
            token for token in cleaned if not _is_course(token.upper().replace(" ", ""))
        ] or cleaned

    if not cleaned:
        return ""

    candidate = " ".join(cleaned).strip()
    candidate = ROLE_MARKER_RE.sub("", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)

    # Handle collaborated faculty: "/" between two faculty names (e.g., "VKG/SKJ")
    # Check if candidate has "/" separating two valid instructor names
    if "/" in candidate:
        parts = [p.strip() for p in candidate.split("/") if p.strip()]
        valid_parts = []
        for part in parts:
            # Each part should look like an instructor (initials or name)
            if INSTRUCTOR_RE.match(part.strip()):
                valid_parts.append(part.strip())
            # Also check if it's initials without INSTRUCTOR_RE match (e.g., "VKG")
            elif re.fullmatch(r"[A-Z]{2,4}", part.strip(), re.IGNORECASE):
                valid_parts.append(part.strip().upper())
        
        if len(valid_parts) >= 2:
            # Multiple valid faculty members - keep all
            candidate = " / ".join(valid_parts)

    if candidate and INSTRUCTOR_RE.match(candidate):
        name = candidate
    else:
        # Fall back to the leading run of initials, which is where the name is.
        salvaged: List[str] = []
        for token in cleaned:
            if INSTRUCTOR_RE.match(token):
                salvaged.append(token)
            else:
                break
        name = " ".join(salvaged).strip()
```


## Edit 55 — msg 3286 — 2026-10-11 11:03 UTC
Intent: 

### OLD
```python
def _resolve_instructor(parts: List[str], course_code: str) -> str:
    """
    Work out who teaches this, from whatever is left in the cell.

    The awkward part of the grid is that a class is often labelled with things
    that are not the instructor *and* not the room - "Batch A", "CPPS Lab",
    "(Extra)", "Workshop". Those used to be enough to fail the name check, and
    because the whole string was discarded the real initials went with it:
    ``ME3010L-MZA-Batch A-CPPS Lab`` lost ``MZA``.

    So the leftovers are cleaned rather than rejected:

    1. drop the class and venue words, and a "Batch X" pair as a unit
    2. drop a stray room or group label ("101", "A1", "OE3")
    3. drop a second course code, which is the other half of a slash-joined cell
       ("EC204a/EC204b" is two papers; only one became the course)
    5. if what remains reads as a name, use all of it
    5. otherwise keep the leading run of initial groups - the name is written
       first in every one of these cells, so the tail is the noise

    Special handling:
    - "/" between course codes: already handled by cell parsing (split into separate slots)
    - "/" between faculty names: indicates collaborated faculty, keep both names
    """
    tokens = [part.strip() for part in parts if part and part.strip()]
    cleaned: List[str] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower().strip(".,")

        if lowered in CLASS_NOISE_WORDS or lowered in VENUE_NOISE_WORDS:
            # "Batch A" is one label, not two tokens: drop the letter too.
            if lowered == "batch" and index + 1 < len(tokens) and re.fullmatch(r"[A-Za-z]", tokens[index + 1].strip()):
                index += 1
            index += 1
            continue

        # A room or group label, not a person.
        if re.fullmatch(r"\d{1,4}|[A-Z]{1,3}-?\d{1,4}", token, re.IGNORECASE):
            index += 1
            continue

        cleaned.append(token)
        index += 1

    # The other paper in "EC204a/EC204b-PR/KD/SNS": a code, so not a teacher.
    if course_code and len(cleaned) > 1:
        cleaned = [
            token for token in cleaned if not _is_course(token.upper().replace(" ", ""))
        ] or cleaned

    if not cleaned:
        return ""

    candidate = " ".join(cleaned).strip()
    candidate = ROLE_MARKER_RE.sub("", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)

    # Handle collaborated faculty: "/" between two faculty names (e.g., "VKG/SKJ")
    # Check if candidate has "/" separating two valid instructor names
    if "/" in candidate:
        parts = [p.strip() for p in candidate.split("/") if p.strip()]
        valid_parts = []
        for part in parts:
            # Each part should look like an instructor (initials or name)
            if INSTRUCTOR_RE.match(part.strip()):
                valid_parts.append(part.strip())
            # Also check if it's initials without INSTRUCTOR_RE match (e.g., "VKG")
            elif re.fullmatch(r"[A-Z]{2,4}", part.strip(), re.IGNORECASE):
                valid_parts.append(part.strip().upper())
        
        if len(valid_parts) >= 2:
            # Multiple valid faculty members - keep all
            candidate = " / ".join(valid_parts)

    if candidate and INSTRUCTOR_RE.match(candidate):
        name = candidate
    else:
        # Fall back to the leading run of initials, which is where the name is.
        salvaged: List[str] = []
        for token in cleaned:
            if INSTRUCTOR_RE.match(token):
                salvaged.append(token)
            else:
                break
        name = " ".join(salvaged).strip()
```

### NEW
```python
def _resolve_instructor(parts: List[str], course_code: str) -> str:
    """
    Work out who teaches this, from whatever is left in the cell.

    The awkward part of the grid is that a class is often labelled with things
    that are not the instructor *and* not the room - "Batch A", "CPPS Lab",
    "(Extra)", "Workshop". Those used to be enough to fail the name check, and
    because the whole string was discarded the real initials went with it:
    ``ME3010L-MZA-Batch A-CPPS Lab`` lost ``MZA``.

    So the leftovers are cleaned rather than rejected:

    1. drop the class and venue words, and a "Batch X" pair as a unit
    2. drop a stray room or group label ("101", "A1", "OE3")
    3. drop a second course code, which is the other half of a slash-joined cell
       ("EC204a/EC204b" is two papers; only one became the course)
    4. if what remains reads as a name, use all of it
    5. otherwise keep the leading run of initial groups - the name is written
       first in every one of these cells, so the tail is the noise

    Special handling:
    - "/" between course codes: already handled by cell parsing (split into separate slots)
    - "/" between faculty names: indicates collaborated faculty, keep both names
    """
    # Pre-process tokens: split any token that contains "/" between faculty initials
    # e.g., "VKG/SKJ" -> ["VKG", "SKJ"]
    expanded_parts: List[str] = []
    for part in parts:
        if part and part.strip():
            # Split on "/" if it looks like faculty initials (e.g., VKG/SKJ)
            # but not if it's a course code (handled earlier)
            subparts = [p.strip() for p in part.split("/") if p.strip()]
            expanded_parts.extend(subparts)
    
    tokens = [part.strip() for part in expanded_parts if part and part.strip()]
    cleaned: List[str] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower().strip(".,")

        if lowered in CLASS_NOISE_WORDS or lowered in VENUE_NOISE_WORDS:
            # "Batch A" is one label, not two tokens: drop the letter too.
            if lowered == "batch" and index + 1 < len(tokens) and re.fullmatch(r"[A-Za-z]", tokens[index + 1].strip()):
                index += 1
            index += 1
            continue

        # A room or group label, not a person.
        if re.fullmatch(r"\d{1,4}|[A-Z]{1,3}-?\d{1,4}", token, re.IGNORECASE):
            index += 1
            continue

        cleaned.append(token)
        index += 1

    # The other paper in "EC204a/EC204b-PR/KD/SNS": a code, so not a teacher.
    if course_code and len(cleaned) > 1:
        cleaned = [
            token for token in cleaned if not _is_course(token.upper().replace(" ", ""))
        ] or cleaned

    if not cleaned:
        return ""

    candidate = " ".join(cleaned).strip()
    candidate = ROLE_MARKER_RE.sub("", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)

    # Handle collaborated faculty: "/" between two faculty names (e.g., "VKG/SKJ")
    # Check if candidate has "/" separating two valid instructor names
    if "/" in candidate:
        parts = [p.strip() for p in candidate.split("/") if p.strip()]
        valid_parts = []
        for part in parts:
            # Each part should look like an instructor (initials or name)
            if INSTRUCTOR_RE.match(part.strip()):
                valid_parts.append(part.strip())
            # Also check if it's initials without INSTRUCTOR_RE match (e.g., "VKG")
            elif re.fullmatch(r"[A-Z]{2,4}", part.strip(), re.IGNORECASE):
                valid_parts.append(part.strip().upper())
        
        if len(valid_parts) >= 2:
            # Multiple valid faculty members - keep all
            candidate = " / ".join(valid_parts)

    if candidate and INSTRUCTOR_RE.match(candidate):
        name = candidate
    else:
        # Fall back to the leading run of initials, which is where the name is.
        salvaged: List[str] = []
        for token in cleaned:
            if INSTRUCTOR_RE.match(token):
                salvaged.append(token)
            else:
                break
        name = " ".join(salvaged).strip()
```


## Edit 56 — msg 3325 — 2026-10-11 11:23 UTC
Intent: I understand - you want the system to use instructor name as a fallback when course codes are truncated/cut off in the PDF. Let me implement a fallback that uses instructor name + semester + day to determine the course w

### OLD
```python
# Clean up helper field
    for slot in deduplicated:
        slot.pop("_course_base", None)

    return deduplicated
```

### NEW
```python
# Step 3: Resolve truncated course codes using instructor + day + semester
    # Build instructor -> course mapping from slots with valid course codes
    instructor_course_map = {}  # (instructor, day, semester) -> set of course codes
    for slot in deduplicated:
        instructor = slot.get("instructor", "").strip()
        course_code = slot.get("course_code", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        if instructor and course_code and day and semester:
            key = (instructor.upper(), day, semester)
            if key not in instructor_course_map:
                instructor_course_map[key] = set()
            instructor_course_map[key].add(course_code)

    # Now try to resolve slots with missing/invalid course codes but valid instructor
    for slot in deduplicated:
        code = slot.get("course_code", "").strip()
        instructor = slot.get("instructor", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        
        # Check if course code looks truncated (too short for a valid code)
        is_truncated = (
            not code 
            or len(code) < 5  # Minimum valid course code like "CS101"
            or (code and not _is_course(code))  # Invalid course code format
        )
        
        if is_truncated and instructor and day and semester:
            key = (instructor.upper(), day, semester)
            if key in instructor_course_map:
                possible_courses = instructor_course_map[key]
                if len(possible_courses) == 1:
                    # Only one course for this instructor on this day/semester - use it
                    slot["course_code"] = next(iter(possible_courses))
                    # Recalculate base
                    slot["_course_base"] = possible_courses.pop()
                elif len(possible_courses) > 1:
                    # Multiple courses - try to match by time
                    slot_start = slot.get("start_time")
                    slot_end = slot.get("end_time")
                    time_matches = [
                        c for c in possible_courses 
                        if any(s.get("course_code") == c and s.get("start_time") == slot.get("start_time") and s.get("end_time") == slot.get("end_time") for s in deduplicated)
                    ]
                    if len(time_matches) == 1:
                        slot["course_code"] = time_matches[0]
                        slot["_course_base"] = time_matches[0]

    # Clean up helper field
    for slot in deduplicated:
        slot.pop("_course_base", None)

    return deduplicated
```


## Edit 57 — msg 3331 — 2026-10-11 11:26 UTC
Intent: 

### OLD
```python
# Step 3: Resolve truncated course codes using instructor + day + semester
    # Build instructor -> course mapping from slots with valid course codes
    instructor_course_map = {}  # (instructor, day, semester) -> set of course codes
    for slot in deduplicated:
        instructor = slot.get("instructor", "").strip()
        course_code = slot.get("course_code", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        if instructor and course_code and day and semester:
            key = (instructor.upper(), day, semester)
            if key not in instructor_course_map:
                instructor_course_map[key] = set()
            instructor_course_map[key].add(course_code)
```

### NEW
```python
# Step 3: Resolve truncated course codes using instructor + day + semester
    # Build instructor -> course mapping from slots with VALID course codes only
    instructor_course_map = {}  # (instructor, day, semester) -> set of course codes
    for slot in deduplicated:
        instructor = slot.get("instructor", "").strip()
        course_code = slot.get("course_code", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        # Only use VALID course codes for the mapping
        if instructor and course_code and day and semester and _is_course(course_code):
            key = (instructor.upper(), day, semester)
            if key not in instructor_course_map:
                instructor_course_map[key] = set()
            instructor_course_map[key].add(course_code)
```


## Edit 58 — msg 3334 — 2026-10-11 11:27 UTC
Intent: 

### OLD
```python
# Clean up helper field
    for slot in deduplicated:
        slot.pop("_course_base", None)

    return deduplicated
```

### NEW
```python
# Clean up helper field
    for slot in deduplicated:
        slot.pop("_course_base", None)

    # Re-run deduplication to handle any duplicates created by instructor fallback
    # (e.g., resolved truncated code now duplicates an existing valid slot)
    # Re-group and re-deduplicate
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in deduplicated:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        is_elective = is_open_elective(code)
        if is_elective:
            key = (day, code, start, end)
        else:
            key = (day, base, start, end)
        grouped[key].append(slot)

    final_deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
            # Electives: keep all (different electives can be at same time)
            # But deduplicate exact duplicates (same code, same time, same room)
            seen_keys = set()
            for slot in group:
                dedup_key = (slot.get("day", ""), slot.get("course_code", ""), slot.get("start_time"), slot.get("end_time"), slot.get("room", ""))
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    final_deduplicated.append(slot)
        else:
            # Core courses: keep only one per group (by branch match)
            correct_branch = infer_branch_from_course_code(code)
            matched = None
            for slot in group:
                if slot.get("branch_or_program", "") == correct_branch:
                    matched = slot
                    break
            if matched:
                final_deduplicated.append(matched)
            else:
                non_tba = [s for s in group if s.get("room", "").upper() != "TBA"]
                if non_tba:
                    final_deduplicated.append(non_tba[0])
                else:
                    final_deduplicated.append(group[0])

    return final_deduplicated
```


## Edit 59 — msg 3338 — 2026-10-11 11:28 UTC
Intent: I see the current implementation. I need to modify the instructor_course_map to include branch for regular courses (branch-wise), while keeping it as-is for electives. Let me update the code:

### OLD
```python
# Step 3: Resolve truncated course codes using instructor + day + semester
    # Build instructor -> course mapping from slots with VALID course codes only
    instructor_course_map = {}  # (instructor, day, semester) -> set of course codes
    for slot in deduplicated:
        instructor = slot.get("instructor", "").strip()
        course_code = slot.get("course_code", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        # Only use VALID course codes for the mapping
        if instructor and course_code and day and semester and _is_course(course_code):
            key = (instructor.upper(), day, semester)
            if key not in instructor_course_map:
                instructor_course_map[key] = set()
            instructor_course_map[key].add(course_code)
```

### NEW
```python
# Step 3: Resolve truncated course codes using instructor + day + semester
    # Build instructor -> course mapping from slots with VALID course codes only
    # For electives: key = (instructor, day, semester)
    # For core courses: key = (instructor, day, semester, branch) - branch-wise
    instructor_course_map = {}  # key -> set of course codes
    for slot in deduplicated:
        instructor = slot.get("instructor", "").strip()
        course_code = slot.get("course_code", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        branch = slot.get("branch_or_program", "").strip()
        is_elective = is_open_elective(course_code)
        # Only use VALID course codes for the mapping
        if instructor and course_code and day and semester and _is_course(course_code):
            if is_elective:
                # Electives: instructor + day + semester (no branch)
                key = (instructor.upper(), day, semester)
            else:
                # Core courses: instructor + day + semester + branch (branch-wise)
                key = (instructor.upper(), day, semester, branch)
            if key not in instructor_course_map:
                instructor_course_map[key] = set()
            instructor_course_map[key].add(course_code)
```


## Edit 60 — msg 3339 — 2026-10-11 11:29 UTC
Intent: I see the current implementation. I need to modify the instructor_course_map to include branch for regular courses (branch-wise), while keeping it as-is for electives. Let me update the code:

### OLD
```python
# Now try to resolve slots with missing/invalid course codes but valid instructor
    for slot in deduplicated:
        code = slot.get("course_code", "").strip()
        instructor = slot.get("instructor", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        
        # Check if course code looks truncated (too short for a valid code)
        is_truncated = (
            not code 
            or len(code) < 5  # Minimum valid course code like "CS101"
            or (code and not _is_course(code))  # Invalid course code format
        )
        
        if is_truncated and instructor and day and semester:
            key = (instructor.upper(), day, semester)
            if key in instructor_course_map:
                possible_courses = instructor_course_map[key]
                if len(possible_courses) == 1:
                    # Only one course for this instructor on this day/semester - use it
                    slot["course_code"] = next(iter(possible_courses))
                    # Recalculate base
                    slot["_course_base"] = possible_courses.pop()
                elif len(possible_courses) > 1:
                    # Multiple courses - try to match by time
                    slot_start = slot.get("start_time")
                    slot_end = slot.get("end_time")
                    time_matches = [
                        c for c in possible_courses 
                        if any(s.get("course_code") == c and s.get("start_time") == slot.get("start_time") and s.get("end_time") == slot.get("end_time") for s in deduplicated)
                    ]
                    if len(time_matches) == 1:
                        slot["course_code"] = time_matches[0]
                        slot["_course_base"] = time_matches[0]
```

### NEW
```python
# Now try to resolve slots with missing/invalid course codes but valid instructor
    for slot in deduplicated:
        code = slot.get("course_code", "").strip()
        instructor = slot.get("instructor", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        branch = slot.get("branch_or_program", "").strip()
        is_elective = is_open_elective(code)
        
        # Check if course code looks truncated (too short for a valid code)
        is_truncated = (
            not code 
            or len(code) < 5  # Minimum valid course code like "CS101"
            or (code and not _is_course(code))  # Invalid course code format
        )
        
        if is_truncated and instructor and day and semester:
            if is_elective:
                # Electives: lookup by (instructor, day, semester)
                key = (instructor.upper(), day, semester)
            else:
                # Core courses: use branch-wise lookup
                key = (instructor.upper(), day, semester, branch)
            
            if key in instructor_course_map:
                possible_courses = instructor_course_map[key]
                if len(possible_courses) == 1:
                    # Only one course for this instructor on this day/semester(/branch) - use it
                    slot["course_code"] = next(iter(possible_courses))
                    # Recalculate base
                    slot["_course_base"] = possible_courses.pop()
                elif len(possible_courses) > 1:
                    # Multiple courses - try to match by time
                    slot_start = slot.get("start_time")
                    slot_end = slot.get("end_time")
                    time_matches = [
                        c for c in possible_courses 
                        if any(s.get("course_code") == c and s.get("start_time") == slot.get("start_time") and s.get("end_time") == slot.get("end_time") for s in deduplicated)
                    ]
                    if len(time_matches) == 1:
                        slot["course_code"] = time_matches[0]
                        slot["_course_base"] = time_matches[0]
```


## Edit 61 — msg 3341 — 2026-10-11 11:30 UTC
Intent: Now I need to update the re-deduplication logic to handle the branch correctly:

### OLD
```python
# Re-run deduplication to handle any duplicates created by instructor fallback
    # (e.g., resolved truncated code now duplicates an existing valid slot)
    # Re-group and re-deduplicate
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in deduplicated:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        is_elective = is_open_elective(code)
        if is_elective:
            key = (day, code, start, end)
        else:
            key = (day, base, start, end)
        grouped[key].append(slot)

    final_deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
```

### NEW
```python
# Re-run deduplication to handle any duplicates created by instructor fallback
    # (e.g., resolved truncated code now duplicates an existing valid slot)
    # Re-group and re-deduplicate
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in deduplicated:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        branch = slot.get("branch_or_program", "").strip()
        is_elective = is_open_elective(code)
        # For electives, use (day, code, start, end)
        # For core courses, use (day, base, start, end, branch) - branch-wise
        if is_elective:
            key = (day, code, start, end)
        else:
            key = (day, base, start, end, branch)
        grouped[key].append(slot)

    final_deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
```


## Edit 62 — msg 3345 — 2026-10-11 11:31 UTC
Intent: Now I need to update the re-deduplication logic to handle the branch correctly:

### OLD
```python
final_deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
```

### NEW
```python
final_deduplicated: List[Dict] = []
    for key, group in grouped.items():
        # Handle both key formats: (day, base/start, end) for electives
        # and (day, base, start, end, branch) for core courses
        if len(key) == 4:
            day, base, start, end = key
            branch = ""
        elif len(key) == 5:
            day, base, start, end, branch = key
        else:
            continue
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
```


## Edit 63 — msg 3381 — 2026-10-11 11:58 UTC
Intent: Found the bug! At line 1220, slots with empty course codes (due to truncation) are being **skipped entirely** before they even reach the instructor fallback logic. The fix is to keep slots with instructor names even when

### OLD
```python
for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    if not course_code:
                        continue
```

### NEW
```python
for entry in _split_cell_entries(row[col_index]):
                    course_code, instructor, room = split_slot_cell(entry)
                    # Keep slots even with empty course_code if instructor is present
                    # (will be resolved via instructor fallback in _post_process_slots)
                    if not course_code and not instructor:
                        continue
```


## Edit 64 — msg 3383 — 2026-10-11 11:59 UTC
Intent: Found the bug! At line 1220, slots with empty course codes (due to truncation) are being **skipped entirely** before they even reach the instructor fallback logic. The fix is to keep slots with instructor names even when

### OLD
```python
# Check if this course is an elective (OE prefix)
                                        # Check if this course is an elective (OE prefix)
                    is_elective = is_open_elective(course_code)
```

### NEW
```python
# Check if this course is an elective (OE prefix)
                    is_elective = is_open_elective(course_code) if course_code else False
```


## Edit 65 — msg 3385 — 2026-10-11 11:59 UTC
Intent: 

### OLD
```python
if is_open_elective(course_code):
                        # Electives have no branch - they're not branch-specific
                        entry_branches = [""]
                    elif extra_branches or branches_to_process[0] == "Unknown":
                        # Core course in combined cell OR with Unknown branch: determine correct branch from course code prefix
                        course_branch = infer_branch_from_course_code(course_code)
                        if course_branch:
                            entry_branches = [course_branch]
                        else:
                            # Fallback: use first branch if no match
                            entry_branches = [branches_to_process[0]]
```

### NEW
```python
if is_open_elective(course_code):
                        # Electives have no branch - they're not branch-specific
                        entry_branches = [""]
                    elif extra_branches or branches_to_process[0] == "Unknown":
                        # Core course in combined cell OR with Unknown branch: determine correct branch from course code prefix
                        course_branch = infer_branch_from_course_code(course_code) if course_code else None
                        if course_branch:
                            entry_branches = [course_branch]
                        else:
                            # Fallback: use first branch if no match
                            entry_branches = [branches_to_process[0]]
```


## Edit 66 — msg 3393 — 2026-10-11 12:03 UTC
Intent: 

### OLD
```python
# Group slots by (day, base, start, end) but for electives include course code in key
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        is_elective = is_open_elective(code)
        # For electives, include course code in key to avoid deduplicating different electives at same time
        if is_elective:
            key = (day, code, start, end)
        else:
            key = (day, base, start, end)
        grouped[key].append(slot)

    # For each group, select the correct slot(s)
    deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
            # Electives: keep all (different electives can be at same time)
            deduplicated.extend(group)
        else:
```

### NEW
```python
# Group slots by (day, base, start, end) but for electives include course code in key
    # For electives with empty course code, keep all slots (don't deduplicate) to allow instructor fallback
    grouped: defaultdict[tuple, List[Dict]] = defaultdict(list)
    for slot in slots:
        code = slot.get("course_code", "")
        base = slot.get("_course_base", slot.get("course_code", ""))
        day = slot.get("day", "")
        start = slot.get("start_time")
        end = slot.get("end_time")
        instructor = slot.get("instructor", "").strip()
        is_elective = is_open_elective(code)
        # For electives with valid course code, include code in key to avoid deduplicating different electives
        # For electives with empty course code, keep all slots (don't deduplicate) for instructor fallback
        if is_elective and code:
            key = (day, code, start, end)
        elif is_elective and not code:
            # Don't deduplicate empty-code electives - use unique key per slot
            key = (day, "EMPTY", id(slot), start, end)
        else:
            key = (day, base, start, end)
        grouped[key].append(slot)

    # For each group, select the correct slot(s)
    deduplicated: List[Dict] = []
    for key, group in grouped.items():
        day, base, start, end = key
        code = group[0].get("course_code", "") if group else ""
        is_elective = is_open_elective(code)

        if is_elective:
            # Electives: keep all (different electives can be at same time)
            # For empty-code electives, keep all for instructor fallback
            deduplicated.extend(group)
        else:
```


## Edit 67 — msg 3399 — 2026-10-11 12:06 UTC
Intent: 

### OLD
```python
# Now try to resolve slots with missing/invalid course codes but valid instructor
    for slot in deduplicated:
        code = slot.get("course_code", "").strip()
        instructor = slot.get("instructor", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        branch = slot.get("branch_or_program", "").strip()
        is_elective = is_open_elective(code)
        
        # Check if course code looks truncated (too short for a valid code)
        is_truncated = (
            not code 
            or len(code) < 5  # Minimum valid course code like "CS101"
            or (code and not _is_course(code))  # Invalid course code format
        )
        
        if is_truncated and instructor and day and semester:
            if is_elective:
                # Electives: lookup by (instructor, day, semester)
                key = (instructor.upper(), day, semester)
            else:
                # Core courses: use branch-wise lookup
                key = (instructor.upper(), day, semester, branch)
            
            if key in instructor_course_map:
                possible_courses = instructor_course_map[key]
                if len(possible_courses) == 1:
                    # Only one course for this instructor on this day/semester(/branch) - use it
                    slot["course_code"] = next(iter(possible_courses))
                    # Recalculate base
                    slot["_course_base"] = possible_courses.pop()
                elif len(possible_courses) > 1:
                    # Multiple courses - try to match by time
                    slot_start = slot.get("start_time")
                    slot_end = slot.get("end_time")
                    time_matches = [
                        c for c in possible_courses 
                        if any(s.get("course_code") == c and s.get("start_time") == slot.get("start_time") and s.get("end_time") == slot.get("end_time") for s in deduplicated)
                    ]
                    if len(time_matches) == 1:
                        slot["course_code"] = time_matches[0]
                        slot["_course_base"] = time_matches[0]
```

### NEW
```python
# Now try to resolve slots with missing/invalid course codes but valid instructor
    for slot in deduplicated:
        code = slot.get("course_code", "").strip()
        instructor = slot.get("instructor", "").strip()
        day = slot.get("day", "")
        semester = slot.get("semester")
        branch = slot.get("branch_or_program", "").strip()
        is_elective = is_open_elective(code)
        
        # Check if course code looks truncated (too short for a valid code)
        is_truncated = (
            not code 
            or len(code) < 5  # Minimum valid course code like "CS101"
            or (code and not _is_course(code))  # Invalid course code format
        )
        
        if is_truncated and instructor and day and semester:
            # For empty course codes, try BOTH elective and core lookups
            possible_courses = set()
            
            # Try elective lookup (instructor + day + semester)
            elective_key = (instructor.upper(), day, semester)
            if elective_key in instructor_course_map:
                possible_courses.update(instructor_course_map[elective_key])
            
            # Try core course lookup (instructor + day + semester + branch)
            core_key = (instructor.upper(), day, semester, branch)
            if core_key in instructor_course_map:
                possible_courses.update(instructor_course_map[core_key])
            
            if len(possible_courses) == 1:
                # Only one course for this instructor on this day/semester(/branch) - use it
                slot["course_code"] = next(iter(possible_courses))
                # Recalculate base
                slot["_course_base"] = possible_courses.pop()
            elif len(possible_courses) > 1:
                # Multiple courses - try to match by time
                slot_start = slot.get("start_time")
                slot_end = slot.get("end_time")
                time_matches = [
                    c for c in possible_courses 
                    if any(s.get("course_code") == c and s.get("start_time") == slot.get("start_time") and s.get("end_time") == slot.get("end_time") for s in deduplicated)
                ]
                if len(time_matches) == 1:
                    slot["course_code"] = time_matches[0]
                    slot["_course_base"] = time_matches[0]
```


## Edit 68 — msg 3425 — 2026-10-11 12:52 UTC
Intent: Looking at the raw PDF data, I can see the issue. The Wednesday V Sem CSE cell has multiple electives in one cell separated by newlines, and there's a "27/" prefix on "27/ME5D02" that needs to be handled. The parser is m

### OLD
```python
def _starts_course(chunk: str) -> bool:
    """Does this fragment begin with something shaped like a course code?"""
    token = chunk.strip("()")
    return bool(re.match(r"^(?:OE|OI)?[A-Z]{1,4}[-_. ]?\d", token, re.IGNORECASE))
```

### NEW
```python
def _starts_course(chunk: str) -> bool:
    """Does this fragment begin with something shaped like a course code?"""
    token = chunk.strip("()")
    # Handle course codes that may have trailing dash (e.g., "OE3E40-" before instructor)
    # Remove trailing dash if present before checking
    token = token.rstrip("-")
    return bool(re.match(r"^(?:OE|OI)?[A-Z]{1,4}[-_. ]?\d", token, re.IGNORECASE))
```


## Edit 69 — msg 3427 — 2026-10-11 12:53 UTC
Intent: Looking at the raw PDF data, I can see the issue. The Wednesday V Sem CSE cell has multiple electives in one cell separated by newlines, and there's a "27/" prefix on "27/ME5D02" that needs to be handled. The parser is m

### OLD
```python
def _split_cell_entries(cell: str) -> List[str]:
    """
    Break one timetable cell into its individual class entries.

    A slot can hold several papers, either on separate lines or run together
    after a group label: ``OE1: OE2C02-AO-L104 OE2C12-NaS (VF)-CR208``. Splitting
    them keeps one class from hiding the next.

    The separator varies across the document - ``-``, ``:``, ``_`` and a space -
    and room names contain their own hyphens (``CC-GF``), so chunks are rejoined
    greedily: a fragment is only a new entry once a course code has been seen and
    the next fragment starts another one.
    """
    text = " ".join((cell or "").split())
    if not text or text.lower() in EMPTY_CELL_VALUES:
        return []

    # A group label such as "OE1:" or "OE11:" precedes its papers.
    group = re.match(r"^(OE|OI)\s*\d+\s*:\s*", text, re.IGNORECASE)
    if group:
        text = text[group.end():]

    # Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"]
    # The PDF maker often crams multiple electives into one cell.
    slash_parts = _split_slash_electives(text)
    if len(slash_parts) > 1:
        # Process each part separately and combine
        all_entries = []
        for part in slash_parts:
            part_entries = _split_cell_entries(part)
            all_entries.extend(part_entries)
        return all_entries

    chunks = [c for c in text.split() if c]
    entries: List[str] = []
    current = ""

    for chunk in chunks:
        if not _looks_like_entry(chunk) and current:
            # Trailing room / qualifier belongs to the entry being built.
            current = f"{current} {chunk}"
            continue

        # A fragment that starts a fresh course code begins a new entry.
        if current and _starts_course(chunk) and _starts_course(_first_token(current)):
            entries.append(current)
            current = chunk
        elif current:
            current = f"{current} {chunk}"
        else:
            current = chunk

    if current:
        entries.append(current)

    return [entry for entry in entries if entry.strip()]
```

### NEW
```python
def _split_cell_entries(cell: str) -> List[str]:
    """
    Break one timetable cell into its individual class entries.

    A slot can hold several papers, either on separate lines or run together
    after a group label: ``OE1: OE2C02-AO-L104 OE2C12-NaS (VF)-CR208``. Splitting
    them keeps one class from hiding the next.

    The separator varies across the document - ``-``, ``:``, ``_`` and a space -
    and room names contain their own hyphens (``CC-GF``), so chunks are rejoined
    greedily: a fragment is only a new entry once a course code has been seen and
    the next fragment starts another one.

    Handles:
    - Multiple courses on separate lines (newlines)
    - "27/" prefix on course codes (e.g., "27/ME5D02" -> "ME5D02")
    - Multiple electives in one cell separated by newlines or spaces
    """
    if not cell or cell.strip().lower() in EMPTY_CELL_VALUES:
        return []

    # Split on newlines first to handle multi-line cells
    lines = [line.strip() for line in cell.split("\n") if line.strip()]
    if not lines:
        return []

    all_entries = []
    for line in lines:
        line_entries = _split_single_line_cell(line)
        all_entries.extend(line_entries)

    # Post-process: strip "27/" prefix from course codes
    processed = []
    for entry in all_entries:
        # Strip "27/" prefix from course codes like "27/ME5D02-VKG-CR201"
        entry = re.sub(r"^(\d{1,3})/([A-Z]{2}\d)", r"\2", entry)
        processed.append(entry)

    return [e for e in processed if e.strip()]


def _split_single_line_cell(text: str) -> List[str]:
    """
    Split a single line cell into entries.
    Handles group labels, slash-joined electives, and multiple courses on one line.
    """
    text = " ".join((text or "").split())
    if not text or text.lower() in EMPTY_CELL_VALUES:
        return []

    # A group label such as "OE1:" or "OE11:" precedes its papers.
    group = re.match(r"^(OE|OI)\s*\d+\s*:\s*", text, re.IGNORECASE)
    if group:
        text = text[group.end():]

    # Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"]
    slash_parts = _split_slash_electives(text)
    if len(slash_parts) > 1:
        all_entries = []
        for part in slash_parts:
            part_entries = _split_single_line_cell(part)
            all_entries.extend(part_entries)
        return all_entries

    chunks = [c for c in text.split() if c]
    entries: List[str] = []
    current = ""

    for chunk in chunks:
        if not _looks_like_entry(chunk) and current:
            # Trailing room / qualifier belongs to the entry being built.
            current = f"{current} {chunk}"
            continue

        # A fragment that starts a fresh course code begins a new entry.
        if current and _starts_course(chunk) and _starts_course(_first_token(current)):
            entries.append(current)
            current = chunk
        elif current:
            current = f"{current} {chunk}"
        else:
            current = chunk

    if current:
        entries.append(current)

    return [entry for entry in entries if entry.strip()]
```


## Edit 70 — msg 3436 — 2026-10-11 12:57 UTC
Intent: 

### OLD
```python
def _split_single_line_cell(text: str) -> List[str]:
    """
    Split a single line cell into entries.
    Handles group labels, slash-joined electives, and multiple courses on one line.
    """
    text = " ".join((text or "").split())
    if not text or text.lower() in EMPTY_CELL_VALUES:
        return []

    # A group label such as "OE1:" or "OE11:" precedes its papers.
    group = re.match(r"^(OE|OI)\s*\d+\s*:\s*", text, re.IGNORECASE)
    if group:
        text = text[group.end():]

    # Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"]
    slash_parts = _split_slash_electives(text)
    if len(slash_parts) > 1:
        all_entries = []
        for part in slash_parts:
            part_entries = _split_single_line_cell(part)
            all_entries.extend(part_entries)
        return all_entries

    chunks = [c for c in text.split() if c]
    entries: List[str] = []
    current = ""

    for chunk in chunks:
        if not _looks_like_entry(chunk) and current:
            # Trailing room / qualifier belongs to the entry being built.
            current = f"{current} {chunk}"
            continue

        # A fragment that starts a fresh course code begins a new entry.
        if current and _starts_course(chunk) and _starts_course(_first_token(current)):
            entries.append(current)
            current = chunk
        elif current:
            current = f"{current} {chunk}"
        else:
            current = chunk

    if current:
        entries.append(current)

    return [entry for entry in entries if entry.strip()]


def _first_token(entry: str) -> str:
    return entry.split()[0] if entry.split() else ""
```

### NEW
```python
def _split_single_line_cell(text: str) -> List[str]:
    """
    Split a single line cell into entries.
    Handles group labels, slash-joined electives, and multiple courses on one line.
    """
    text = " ".join((text or "").split())
    if not text or text.lower() in EMPTY_CELL_VALUES:
        return []

    # A group label such as "OE1:" or "OE11:" precedes its papers.
    group = re.match(r"^(OE|OI)\s*\d+\s*:\s*", text, re.IGNORECASE)
    if group:
        text = text[group.end():]

    # Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"]
    slash_parts = _split_slash_electives(text)
    if len(slash_parts) > 1:
        all_entries = []
        for part in slash_parts:
            part_entries = _split_single_line_cell(part)
            all_entries.extend(part_entries)
        return all_entries

    chunks = [c for c in text.split() if c]
    entries: List[str] = []
    current = ""

    for chunk in chunks:
        chunk_clean = chunk.rstrip("-")
        
        if not _looks_like_entry(chunk) and current:
            # Trailing room / qualifier belongs to the entry being built.
            current = f"{current} {chunk}"
            continue

        # A fragment that starts a fresh course code begins a new entry.
        chunk_starts_course = _starts_course(chunk_clean)
        current_starts_course = _starts_course(_first_token(current).rstrip("-"))
        
        if current and chunk_starts_course and current_starts_course:
            entries.append(current)
            current = chunk
        elif current:
            current = f"{current} {chunk}"
        else:
            current = chunk

    if current:
        entries.append(current)

    # Post-process entries: strip trailing dashes from course codes
    processed = []
    for entry in entries:
        # Strip trailing dash from course code if present (e.g., "OE3E40-" -> "OE3E40")
        # But keep the dash if it's followed by instructor/room
        entry = re.sub(r"^(OE\d[A-Z]\d{2})-(\s|$)", r"\1\2", entry)
        processed.append(entry)

    return [entry for entry in processed if entry.strip()]


def _first_token(entry: str) -> str:
    return entry.split()[0] if entry.split() else ""
```


## Edit 71 — msg 3443 — 2026-10-11 13:02 UTC
Intent: 

### OLD
```python
# Post-process entries: strip trailing dashes from course codes
    processed = []
    for entry in entries:
        # Strip trailing dash from course code if present (e.g., "OE3E40-" -> "OE3E40")
        # But keep the dash if it's followed by instructor/room
        entry = re.sub(r"^(OE\d[A-Z]\d{2})-(\s|$)", r"\1\2", entry)
        processed.append(entry)

    return [entry for entry in processed if entry.strip()]
```

### NEW
```python
# Post-process entries: strip trailing dashes from course codes
    processed = []
    for entry in entries:
        # Handle "OE3E40- SNS-CR101" -> "OE3E40 SNS-CR101" (strip trailing dash from course code)
        # Match OE3E40- followed by space or end of string anywhere in the entry
        entry = re.sub(r"(OE\d[A-Z]\d{2})-(\s|$)", r"\1\2", entry)
        processed.append(entry)

    return [entry for entry in processed if entry.strip()]
```


## Edit 72 — msg 3470 — 2026-10-11 13:17 UTC
Intent: The issue is in `_split_slash_electives` - it splits "OE3M27/ME5D02-VKG-R202" into ["OE3M27", "ME5D02"] but drops the instructor/room "VKG-R202". Let me fix this:

### OLD
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    """
    # Match patterns like "OE3M27/ME5D02" or "OE2C02/OE2C12"
    # Both sides must look like course codes (letters + digits)
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    result = []
    for part in parts:
        part = part.strip()
        if part and re.match(r"^(?:OE|OI)?[A-Z]{1,4}\d", part, re.IGNORECASE):
            result.append(part)
        elif result:
            # Append to previous if it's a continuation (e.g., room)
            result[-1] = f"{result[-1]}/{part}"
    
    return result if result else [text]
```

### NEW
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
    # Match patterns like "OE3M27/ME5D02" or "OE2C02/OE2C12"
    # Both sides must look like course codes (letters + digits)
    # But there may be trailing instructor/room after the last course
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    result = []
    # Extract trailing suffix after the last course code
    # Find the last course-like part and extract what follows
    last_course_idx = -1
    for i, part in enumerate(parts):
        part_clean = part.rstrip("-").rstrip()
        if re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part_clean, re.IGNORECASE):
            last_course_idx = i
    
    # If the last part contains more than just a course code, extract the suffix
    suffix = ""
    if last_course_idx == len(parts) - 1:
        # Last part is a course, check if it has trailing stuff
        pass
    elif last_course_idx >= 0 and last_course_idx < len(parts) - 1:
        # There's stuff after the last course code
        suffix = "/".join(parts[last_course_idx + 1:])
        parts = parts[:last_course_idx + 1]
    
    result = []
    for part in parts:
        part = part.strip()
        if part and re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part, re.IGNORECASE):
            # This is a course code, add suffix if present
            if suffix:
                result.append(part + "-" + suffix)
            else:
                result.append(part)
        elif result:
            # Append to previous if it's a continuation (e.g., room)
            result[-1] = f"{result[-1]}/{part}"
    
    return result if result else [text]
```


## Edit 73 — msg 3477 — 2026-10-11 13:20 UTC
Intent: 

### OLD
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
    # Match patterns like "OE3M27/ME5D02" or "OE2C02/OE2C12"
    # Both sides must look like course codes (letters + digits)
    # But there may be trailing instructor/room after the last course
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    result = []
    # Extract trailing suffix after the last course code
    # Find the last course-like part and extract what follows
    last_course_idx = -1
    for i, part in enumerate(parts):
        part_clean = part.rstrip("-").rstrip()
        if re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part_clean, re.IGNORECASE):
            last_course_idx = i
    
    # If the last part contains more than just a course code, extract the suffix
    suffix = ""
    if last_course_idx == len(parts) - 1:
        # Last part is a course, check if it has trailing stuff
        pass
    elif last_course_idx >= 0 and last_course_idx < len(parts) - 1:
        # There's stuff after the last course code
        suffix = "/".join(parts[last_course_idx + 1:])
        parts = parts[:last_course_idx + 1]
    
    result = []
    for part in parts:
        part = part.strip()
        if part and re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part, re.IGNORECASE):
            # This is a course code, add suffix if present
            if suffix:
                result.append(part + "-" + suffix)
            else:
                result.append(part)
        elif result:
            # Append to previous if it's a continuation (e.g., room)
            result[-1] = f"{result[-1]}/{part}"
    
    return result if result else [text]


def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
```

### NEW
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    # Find course code parts (pattern: 2 letters + digit + letter + 2 digits)
    course_parts = []
    for part in parts:
        part_clean = part.strip().rstrip("-")
        if re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part_clean, re.IGNORECASE):
            course_parts.append(part.strip())
    
    if len(course_parts) >= 2:
        # Check if there's trailing info after the last course code
        match = re.match(r"^([A-Z]{2}\d[A-Z]\d{2})(.*)$", parts[-1].strip(), re.IGNORECASE)
        suffix = ""
        if match:
            suffix = match.group(2)
        # Append suffix to all course codes
        if suffix:
            return [c + "-" + suffix.lstrip("-") for c in course_parts]
        return course_parts
    
    # Fallback
    return [p.strip() for p in parts if p.strip()]


def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
```


## Edit 74 — msg 3479 — 2026-10-11 13:21 UTC
Intent: 

### OLD
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    # Find course code parts (pattern: 2 letters + digit + letter + 2 digits)
    course_parts = []
    for part in parts:
        part_clean = part.strip().rstrip("-")
        if re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part_clean, re.IGNORECASE):
            course_parts.append(part.strip())
    
    if len(course_parts) >= 2:
        # Check if there's trailing info after the last course code
        match = re.match(r"^([A-Z]{2}\d[A-Z]\d{2})(.*)$", parts[-1].strip(), re.IGNORECASE)
        suffix = ""
        if match:
            suffix = match.group(2)
        # Append suffix to all course codes
        if suffix:
            return [c + "-" + suffix.lstrip("-") for c in course_parts]
        return course_parts
    
    # Fallback
    return [p.strip() for p in parts if p.strip()]


def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
```

### NEW
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    # Find course code parts (pattern: 2 letters + digit + letter + 2 digits)
    course_parts = []
    for part in parts:
        part_clean = part.strip().rstrip("-")
        if re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part_clean, re.IGNORECASE):
            course_parts.append(part.strip())
    
    if len(course_parts) >= 2:
        # Check if there's trailing info after the last course code
        match = re.match(r"^([A-Z]{2}\d[A-Z]\d{2})(.*)$", parts[-1].strip(), re.IGNORECASE)
        suffix = ""
        if match:
            suffix = match.group(2)
        # Append suffix to ALL course codes
        if suffix:
            return [c + "-" + suffix.lstrip("-") for c in course_parts]
        return course_parts
    
    # Fallback
    return [p.strip() for p in parts if p.strip()]


def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
```


## Edit 75 — msg 3486 — 2026-10-11 13:25 UTC
Intent: 

### OLD
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    # Find course code parts (pattern: 2 letters + digit + letter + 2 digits)
    course_parts = []
    for part in parts:
        part_clean = part.strip().rstrip("-")
        if re.match(r"^[A-Z]{2}\d[A-Z]\d{2}$", part_clean, re.IGNORECASE):
            course_parts.append(part.strip())
    
    if len(course_parts) >= 2:
        # Check if there's trailing info after the last course code
        match = re.match(r"^([A-Z]{2}\d[A-Z]\d{2})(.*)$", parts[-1].strip(), re.IGNORECASE)
        suffix = ""
        if match:
            suffix = match.group(2)
        # Append suffix to ALL course codes
        if suffix:
            return [c + "-" + suffix.lstrip("-") for c in course_parts]
        return course_parts
    
    # Fallback
    return [p.strip() for p in parts if p.strip()]


def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
```

### NEW
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
    parts = text.split("/")
    if len(parts) < 2:
        return [text]
    
    # Find course code parts (pattern: 2 letters + digit + letter + 2 digits, possibly with trailing suffix)
    course_parts = []
    for part in parts:
        part_clean = part.strip().rstrip("-")
        # Check if part STARTS with a course code pattern
        if re.match(r"^[A-Z]{2}\d[A-Z]\d{2}", part_clean, re.IGNORECASE):
            # Extract just the course code part
            match = re.match(r"^([A-Z]{2}\d[A-Z]\d{2})", part_clean, re.IGNORECASE)
            if match:
                course_parts.append(match.group(1))
    
    if len(course_parts) >= 2:
        # Check if there's trailing info after the last course code
        match = re.match(r"^([A-Z]{2}\d[A-Z]\d{2})(.*)$", parts[-1].strip(), re.IGNORECASE)
        suffix = ""
        if match:
            suffix = match.group(2)
        # Append suffix to ALL course codes
        if suffix:
            return [c + "-" + suffix.lstrip("-") for c in course_parts]
        return course_parts
    
    # Fallback
    return [p.strip() for p in parts if p.strip()]


def parse_day_section_timetable(tables: List[List[List[str]]]) -> tuple[List[Dict], List[str]]:
```


## Edit 76 — msg 3515 — 2026-10-11 13:38 UTC
Intent: 

### OLD
```python
if char in "/:|" or char == "\n":
            # Check if "/" is between two course-like codes (e.g., OE3M27/ME5D02)
            # Don't split if it joins two course-like codes
            if char == "/":
                left = buffer[-1] if buffer else ""
                right = text[index + 1] if index + 1 < length else ""
                # Don't split if both sides look like course code characters
                if left.isalnum() and right.isalnum():
                    buffer += char
                    index += 1
                    continue

            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            index += 1
            while index < length and text[index].isspace():
                index += 1
            continue
```

### NEW
```python
if char in "/:|" or char == "\n":
            # Check if "/" is between two course-like codes (e.g., OE3M27/ME5D02)
            # Don't split if it joins two course-like codes
            if char == "/":
                left = buffer[-1] if buffer else ""
                right = text[index + 1] if index + 1 < length else ""
                # Don't split if both sides look like course code characters
                if left.isalnum() and right.isalnum():
                    buffer += char
                    index += 1
                    continue
                # Also don't split if left is digits and right starts a course code (e.g., "27/ME5D02")
                if left.isdigit() and right.isalpha():
                    # Check if right side starts a course code pattern
                    if index + 1 < length and re.match(r"^[A-Z]{2}\d", text[index+1:], re.IGNORECASE):
                        buffer += char
                        index += 1
                        continue

            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            index += 1
            while index < length and text[index].isspace():
                index += 1
            continue
```


## Edit 77 — msg 3559 — 2026-10-11 14:44 UTC
Intent: Let me fix all three `.get("instructor", "").strip()` occurrences. There are 3 identical strings. I'll use replaceAll with a unique-ish context? The string `slot.get("instructor", "").strip()` appears 3 times identically

### OLD
```python
        instructor = slot.get("instructor", "").strip()
```

### NEW
```python
        instructor = (slot.get("instructor") or "").strip()
```


## Edit 78 — msg 3561 — 2026-10-11 14:44 UTC
Intent: Baseline (after `.strip()` fix): 427 slots.

### OLD
```python
    return all_tables


# A semester band marker such as "I Sem", "VII Sem".
```

### NEW
```python
    return all_tables


#: A slash-joined pair of complete course codes: ``OE3M27/ME5D02``.
ELECTIVE_PAIR_RE = re.compile(
    r"([A-Z]{2,4}\d[A-Z]?\d{1,3})/([A-Z]{2,4}\d[A-Z]?\d{1,3})",
    re.IGNORECASE,
)

#: The same pair with the head of the first code dropped, leaving digits:
#: ``27/ME5D02`` (the tail of ``OE3M27/ME5D02``).
TRUNCATED_ELECTIVE_RE = re.compile(
    r"(?<![A-Z0-9])(\d{1,3})/([A-Z]{2,4}\d[A-Z]?\d{1,3})",
    re.IGNORECASE,
)

#: A room whose building initials lost a letter: ``R202`` (should be ``CR202``).
TRUNCATED_ROOM_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Z])(\d{3})(?![A-Za-z0-9])", re.IGNORECASE
)

#: A lone letter left behind in a data column when a cell's text overflowed.
STRAY_LETTER_RE = re.compile(r"^[A-Z]$")


def _repair_overflow_artifacts(tables: List[List[List[str]]]) -> None:
    """
    Put back characters the table extractor dropped into a neighbouring cell.

    The published grid lets a cell's text overflow its column, and pdfplumber
    then assigns those characters to whichever cell they sit over. Two damaging
    cases are repaired here, both seen in the V-Semester elective block:

    - A slash-joined elective loses the head of its first code, leaving a
      numeric stub: ``OE3M27/ME5D02`` reads as ``27/ME5D02``. The full pair
      appears elsewhere in the document, so the head is recovered from a
      document-wide map of slash-joined pairs.
    - A room loses a leading building letter to a stray lone letter elsewhere:
      ``CR202`` reads as ``R202`` with a lone ``C`` left in another cell. The
      stray letter is put back when it forms a known building code.

    Stray lone letters in data columns are also cleared: on their own they
    parse as an instructor initial and would become an empty class.

    The tables are edited in place.
    """
    # Document-wide map of slash-joined elective pairs: right code -> left codes.
    pair_vocab: Dict[str, set] = {}
    for table in tables:
        for row in table:
            for cell in row:
                for left, right in ELECTIVE_PAIR_RE.findall(cell or ""):
                    pair_vocab.setdefault(right.upper(), set()).add(left.upper())

    for table in tables:
        # Collect stray lone letters in data columns. Column 0 holds the
        # branch/programme label and column 1 the group letter; a lone letter
        # past those is overflow.
        strays: List[str] = []
        for row in table:
            for index, cell in enumerate(row):
                if index >= 2 and STRAY_LETTER_RE.match((cell or "").strip()):
                    strays.append(cell.strip().upper())
                    row[index] = ""

        for row in table:
            for index, cell in enumerate(row):
                text = cell or ""
                if not text:
                    continue
                text = TRUNCATED_ELECTIVE_RE.sub(
                    lambda match: _restore_elective_head(match, pair_vocab), text
                )
                text = TRUNCATED_ROOM_RE.sub(
                    lambda match: _restore_room_letter(match, strays), text
                )
                row[index] = text


def _restore_elective_head(match: "re.Match", pair_vocab: Dict[str, set]) -> str:
    """Rebuild ``27/ME5D02`` back into ``OE3M27/ME5D02`` when the pair is known."""
    digits, right = match.group(1), match.group(2)
    heads = {head for head in pair_vocab.get(right.upper(), ()) if head.endswith(digits)}
    if len(heads) == 1:
        return f"{heads.pop()}/{right}"
    return match.group(0)


def _restore_room_letter(match: "re.Match", strays: List[str]) -> str:
    """Put a stray building letter back onto a room that lost it (``R202`` -> ``CR202``)."""
    letter, digits = match.group(1), match.group(2)
    if letter.upper() in BUILDING_CODES:
        return match.group(0)
    for stray in list(strays):
        if f"{stray}{letter}".upper() in BUILDING_CODES:
            strays.remove(stray)
            return f"{stray}{letter}{digits}"
    return match.group(0)


# A semester band marker such as "I Sem", "VII Sem".
```


## Edit 79 — msg 3562 — 2026-10-11 14:45 UTC
Intent: </think>Now wire it into `parse_timetable_file`:

### OLD
```python
        tables = extract_tables_from_pdf(file_path)
        slots, warnings = parse_day_section_timetable(tables)
```

### NEW
```python
        tables = extract_tables_from_pdf(file_path)
        # Put back characters the table extractor dropped into a neighbouring
        # cell (truncated elective heads, stray room letters).
        _repair_overflow_artifacts(tables)
        slots, warnings = parse_day_section_timetable(tables)
```


## Edit 80 — msg 3565 — 2026-10-11 14:45 UTC
Intent: Now let me edit `_split_cell_entries`:

### OLD
```python
    # Split on newlines first to handle multi-line cells
    lines = [line.strip() for line in cell.split("\n") if line.strip()]
    if not lines:
        return []

    all_entries = []
    for line in lines:
        line_entries = _split_single_line_cell(line)
        all_entries.extend(line_entries)
```

### NEW
```python
    # Split on newlines first to handle multi-line cells
    lines = [line.strip() for line in cell.split("\n") if line.strip()]
    if not lines:
        return []

    # A line ending in "-" is a visual wrap: the same entry continues on the
    # next line ("OE3M27/ME5D02-VKG-" + "CR202", "OE3E25-" + "KD-CR102"), so
    # rejoin them before splitting into entries.
    joined: List[str] = []
    for line in lines:
        if joined and joined[-1].endswith("-"):
            joined[-1] = joined[-1] + line
        else:
            joined.append(line)
    lines = joined

    all_entries = []
    for line in lines:
        line_entries = _split_single_line_cell(line)
        all_entries.extend(line_entries)
```


## Edit 81 — msg 3578 — 2026-10-11 14:48 UTC
Intent: Now let me evaluate each wrap pair with the "next starts with letter" rule:

### OLD
```python
    # A line ending in "-" is a visual wrap: the same entry continues on the
    # next line ("OE3M27/ME5D02-VKG-" + "CR202", "OE3E25-" + "KD-CR102"), so
    # rejoin them before splitting into entries.
    joined: List[str] = []
    for line in lines:
        if joined and joined[-1].endswith("-"):
            joined[-1] = joined[-1] + line
        else:
            joined.append(line)
    lines = joined
```

### NEW
```python
    # A line ending in "-" is usually a visual wrap: the same entry continues
    # on the next line ("OE3M27/ME5D02-VKG-" + "CR202", "OE3E25-" +
    # "KD-CR102"). Only rejoin when the next line starts with a letter, so a
    # genuinely separate digit-led fragment ("EC8004-AV-" + "1 ...") does not
    # get glued on and turn an instructor into a bogus room.
    joined: List[str] = []
    for line in lines:
        if joined and joined[-1].endswith("-") and line[:1].isalpha():
            joined[-1] = joined[-1] + line
        else:
            joined.append(line)
    lines = joined
```


## Edit 82 — msg 3672 — 2026-10-11 15:17 UTC
Intent: I now have the full picture. Let me implement the general fixes. First, fix the entry splitter so a trailing separator (dangling dash) doesn't split one class into two:

### OLD
```python
        # A fragment that starts a fresh course code begins a new entry.
        chunk_starts_course = _starts_course(chunk_clean)
        current_starts_course = _starts_course(_first_token(current).rstrip("-"))
        
        if current and chunk_starts_course and current_starts_course:
            entries.append(current)
            current = chunk
        elif current:
```

### NEW
```python
        # A fragment that starts a fresh course code begins a new entry.
        chunk_starts_course = _starts_course(chunk_clean)
        current_starts_course = _starts_course(_first_token(current).rstrip("-"))

        # ...unless the entry being built ends on a separator. "CS8018-ACP (VF)-
        # L107" and "OE4L73-JAMF- CR202" both end in a dangling "-": the next
        # fragment is the room of the same class, not a new one. Without this,
        # "L107" reads as the course shape "L107" and the entry is torn in two,
        # losing the room on one half and inventing an empty class on the other.
        if current and current.rstrip().endswith(("-", ":", "_")):
            current = f"{current} {chunk}"
        elif current and chunk_starts_course and current_starts_course:
            entries.append(current)
            current = chunk
        elif current:
```


## Edit 83 — msg 3673 — 2026-10-11 15:18 UTC
Intent: Now fix `split_slot_cell` to (a) recognize a leading hyphenated course code and (b) treat the *last* room-shaped token as the room:

### OLD
```python
    tokens = _split_welded_code(_merge_room_fragments(_tokenize_cell(cell)))
    if not tokens:
        return "", "", ""

    course_code = ""
    room = ""
    consumed: set[str] = set()

    # Rooms are claimed first: they are the narrower shape, and "CR208" would
    # otherwise pass as a course code. Floor and venue rooms ("CC-GF", "CC 3F",
    # "AUDITORIUM") are matched here too, since _is_room only covers numbered ones.
    for token in tokens:
        compact = token.upper().replace(" ", "")
        if room:
            continue
        if _is_room(compact) or _is_room_token(token):
            room = normalize_room(token)
            consumed.add(compact)
```

### NEW
```python
    tokens = _split_welded_code(_merge_room_fragments(_tokenize_cell(cell)))
    # A leading "LETTERS-DIGITS" whose joined form is a real course code is the
    # course, not a room: "HS-1001-JAMF-L102" is paper HS1001 in room L102, but
    # "HS-1001" also fits the room shape, so the room pass used to claim it and
    # the real room (L102) was dropped.
    if tokens:
        joined = re.fullmatch(r"([A-Za-z]{2,4})-(\d{3,4})", tokens[0])
        if joined and _is_course(f"{joined.group(1)}{joined.group(2)}".upper()):
            tokens = [f"{joined.group(1)}{joined.group(2)}".upper(), *tokens[1:]]
    if not tokens:
        return "", "", ""

    course_code = ""
    room = ""
    consumed: set[str] = set()

    # Rooms are claimed first: they are the narrower shape, and "CR208" would
    # otherwise pass as a course code. Floor and venue rooms ("CC-GF", "CC 3F",
    # "AUDITORIUM") are matched here too, since _is_room only covers numbered ones.
    #
    # When more than one token fits the room shape, the *last* one is the room:
    # a class reads "CODE-INSTRUCTOR-ROOM", so an earlier room-shaped fragment
    # ("M02" in "M02-SNS-CR102", "D03" in "D03-MZA-CR202") is a course whose
    # prefix the extractor dropped, not the venue.
    room_index: Optional[int] = None
    for idx, token in enumerate(tokens):
        compact = token.upper().replace(" ", "")
        if _is_room(compact) or _is_room_token(token):
            room_index = idx
    if room_index is not None:
        room = normalize_room(tokens[room_index])
        consumed.add(tokens[room_index].upper().replace(" ", ""))
```


## Edit 84 — msg 3674 — 2026-10-11 15:19 UTC
Intent: Now extend `_repair_overflow_artifacts` to mine a document-wide code/room vocabulary and repair code-prefix and wrapped-room truncation:

### OLD
```python
    # Document-wide map of slash-joined elective pairs: right code -> left codes.
    pair_vocab: Dict[str, set] = {}
    for table in tables:
        for row in table:
            for cell in row:
                for left, right in ELECTIVE_PAIR_RE.findall(cell or ""):
                    pair_vocab.setdefault(right.upper(), set()).add(left.upper())

    for table in tables:
        # Collect stray lone letters in data columns. Column 0 holds the
        # branch/programme label and column 1 the group letter; a lone letter
        # past those is overflow.
        strays: List[str] = []
        for row in table:
            for index, cell in enumerate(row):
                if index >= 2 and STRAY_LETTER_RE.match((cell or "").strip()):
                    strays.append(cell.strip().upper())
                    row[index] = ""

        for row in table:
            for index, cell in enumerate(row):
                text = cell or ""
                if not text:
                    continue
                text = TRUNCATED_ELECTIVE_RE.sub(
                    lambda match: _restore_elective_head(match, pair_vocab), text
                )
                text = TRUNCATED_ROOM_RE.sub(
                    lambda match: _restore_room_letter(match, strays), text
                )
                row[index] = text
```

### NEW
```python
    # Document-wide maps built from every complete token the document contains:
    # the same code or room appears intact somewhere even when one cell lost its
    # head, so a truncated fragment can be matched back to its whole form.
    pair_vocab: Dict[str, set] = {}
    course_vocab: set = set()
    room_vocab: set = set()
    for table in tables:
        for row in table:
            for cell in row:
                for left, right in ELECTIVE_PAIR_RE.findall(cell or ""):
                    pair_vocab.setdefault(right.upper(), set()).add(left.upper())
                for word in re.finditer(r"[A-Za-z0-9]+", cell or ""):
                    token = word.group(0).upper()
                    if _is_course(token):
                        course_vocab.add(token)
                    elif _is_room_token(token):
                        room_vocab.add(token)

    for table in tables:
        # Collect stray lone letters in data columns. Column 0 holds the
        # branch/programme label and column 1 the group letter; a lone letter
        # past those is overflow.
        strays: List[str] = []
        for row in table:
            for index, cell in enumerate(row):
                if index >= 2 and STRAY_LETTER_RE.match((cell or "").strip()):
                    strays.append(cell.strip().upper())
                    row[index] = ""

        for row in table:
            for index, cell in enumerate(row):
                text = cell or ""
                if not text:
                    continue
                text = TRUNCATED_ELECTIVE_RE.sub(
                    lambda match: _restore_elective_head(match, pair_vocab), text
                )
                text = TRUNCATED_ROOM_RE.sub(
                    lambda match: _restore_room_letter(match, strays), text
                )
                text = _restore_wrapped_rooms(text, room_vocab)
                text = _restore_code_heads(text, course_vocab)
                row[index] = text
```


## Edit 85 — msg 3675 — 2026-10-11 15:19 UTC
Intent: Now extend `_repair_overflow_artifacts` to mine a document-wide code/room vocabulary and repair code-prefix and wrapped-room truncation:

### OLD
```python
def _restore_room_letter(match: "re.Match", strays: List[str]) -> str:
    """Put a stray building letter back onto a room that lost it (``R202`` -> ``CR202``)."""
    letter, digits = match.group(1), match.group(2)
    if letter.upper() in BUILDING_CODES:
        return match.group(0)
    for stray in list(strays):
        if f"{stray}{letter}".upper() in BUILDING_CODES:
            strays.remove(stray)
            return f"{stray}{letter}{digits}"
    return match.group(0)
```

### NEW
```python
def _restore_room_letter(match: "re.Match", strays: List[str]) -> str:
    """Put a stray building letter back onto a room that lost it (``R202`` -> ``CR202``)."""
    letter, digits = match.group(1), match.group(2)
    if letter.upper() in BUILDING_CODES:
        return match.group(0)
    for stray in list(strays):
        if f"{stray}{letter}".upper() in BUILDING_CODES:
            strays.remove(stray)
            return f"{stray}{letter}{digits}"
    return match.group(0)


#: A room fragment on its own line, after a wrap: the ``101`` of ``CR101``.
_WRAPPED_ROOM_RE = re.compile(r"-\n([A-Za-z]?\d{1,4})(?=\s|$)", re.MULTILINE)


def _restore_wrapped_rooms(text: str, room_vocab: set) -> str:
    """
    Put back the head of a room that wrapped onto its own line.

    ``OE4E21-SKJ-`` / ``101`` is one class; the ``101`` is the tail of ``CR101``.
    Without this the two lines stay apart, the room is lost and the class parses
    with an empty venue. The head is only supplied when the fragment matches
    exactly one room seen whole elsewhere in the document.
    """

    def replace(match: "re.Match") -> str:
        fragment = match.group(1)
        if _is_room_token(fragment) or _is_floor_token(fragment):
            return match.group(0)
        compact = fragment.upper()
        matches = [
            room for room in room_vocab
            if room.replace("-", "").endswith(compact) and len(room.replace("-", "")) > len(compact)
        ]
        if len(matches) == 1:
            return "-" + sorted(matches)[0]
        return match.group(0)

    return _WRAPPED_ROOM_RE.sub(replace, text)


def _restore_code_heads(text: str, course_vocab: set) -> str:
    """
    Put back the head of a course code the extractor dropped.

    The same paper is written ``C5M03-AK-CR102`` in one cell and
    ``EC5M03-AK-CR102`` in another; ``M02-SNS-CR102`` loses the ``EC5`` of
    ``EC5M02``. The head is recovered only for the *first* field of an entry
    (the course position) and only when the fragment matches exactly one code
    seen whole elsewhere, so a room or a stray word is never rewritten.
    """

    def fix_chunk(chunk: str) -> str:
        head, separator, tail = chunk.partition("-")
        token = head.upper()
        if len(token) < 3 or not any(char.isdigit() for char in token):
            return chunk
        if _is_course(token):
            return chunk
        matches = [
            code for code in course_vocab
            if code.endswith(token) and len(code) > len(token)
        ]
        if len(matches) == 1:
            return sorted(matches)[0] + (separator + tail if separator else "")
        return chunk

    lines = text.split("\n")
    return "\n".join(" ".join(fix_chunk(part) for part in line.split(" ")) for line in lines)
```


## Edit 86 — msg 3742 — 2026-10-11 15:36 UTC
Intent: Understood — `/` = merged course code or collaborated instructors, not a separator. Now I can see the root cause: `_split_slash_electives`'s **fallback** blindly splits on every `/`. Let me fix it:

### OLD
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split slash-joined electives: "OE3M27/ME5D02" -> ["OE3M27", "ME5D02"].
    
    The PDF maker often crams multiple electives into one cell separated by
    a slash. Without splitting, the whole string is read as one long course
    code and both papers are lost.
    
    Also handles trailing instructor/room: "OE3M27/ME5D02-VKG-R202" 
    -> ["OE3M27-VKG-R202", "ME5D02-VKG-R202"]
    """
```

### NEW
```python
def _split_slash_electives(text: str) -> List[str]:
    """
    Split a cell that lists two slash-joined *papers*.

    A slash between two elective codes means either paper can fill the slot, so
    each gets its own entry and both are kept:
    ``OE3M27/ME5D02-VKG-R202`` -> ``["OE3M27-VKG-R202", "ME5D02-VKG-R202"]``.

    Every other slash belongs to a single class and must NOT split it:

    - **merged paper's sections** - ``EC204a/EC204b`` is one paper taught as two
      sections, not two papers
    - **collaborated instructors** - ``PR/KD/SNS`` or ``SKC/DSR`` are the team
      taking the class

    So the fallback only breaks on a slash that is *spaced* - the one separator
    that does mark two independent classes
    (``...EC2002L-TK-(C1) /IT2002-VF-CC-GF (C2)``). Embedded slashes stay whole.
    """
```


## Edit 87 — msg 3743 — 2026-10-11 15:37 UTC
Intent: Understood — `/` = merged course code or collaborated instructors, not a separator. Now I can see the root cause: `_split_slash_electives`'s **fallback** blindly splits on every `/`. Let me fix it:

### OLD
```python
    # Fallback
    return [p.strip() for p in parts if p.strip()]
```

### NEW
```python
    # Fallback: a *spaced* slash still separates two independent classes
    # ("...EC2002L-TK-(C1) /IT2002-VF-CC-GF (C2)"). An embedded slash does not -
    # it is a merged paper's sections ("EC204a/EC204b") or a team of instructors
    # ("PR/KD/SNS"), both of which are one entry.
    spaced = re.split(r"\s+/\s*|\s*/\s+", text)
    if len(spaced) > 1:
        return [p.strip() for p in spaced if p.strip()]
    return [text]
```


## Edit 88 — msg 3744 — 2026-10-11 15:37 UTC
Intent: Now normalize a merged-section code (`EC204a/EC204b` → `EC204`) in `split_slot_cell`:

### OLD
```python
        if not course_code and _is_course(compact):
            # Keep lab suffix (trailing 'L') - it identifies the lab component.
            # Only strip a single trailing letter if it's NOT 'L' (for cases like ME3010A).
            if re.match(r"^[A-Z]{2,4}\d{3,4}L$", compact, re.IGNORECASE):
                course_code = compact  # Keep ME3010L, CS3010L, etc.
            else:
                # Strip trailing single letter (e.g., ME3010A -> ME3010)
                course_code = re.sub(r'^([A-Z]{2,4}\d{3,4})[A-Z]$', r'\1', compact)
            consumed.add(compact)
```

### NEW
```python
        if not course_code and _is_course(compact):
            # A merged paper is written as its two sections ("EC204a/EC204b").
            # The section letters are not two papers, so the code is the root
            # both sections share; slash-joined *paper* pairs were split earlier.
            sections = compact.split("/")
            roots = [re.sub(r"^([A-Z]{2,4}\d{3,4})[A-Z]?$", r"\1", s) for s in sections]
            if len(sections) > 1 and len(set(roots)) == 1:
                course_code = roots[0]
            # Keep lab suffix (trailing 'L') - it identifies the lab component.
            # Only strip a single trailing letter if it's NOT 'L' (for cases like ME3010A).
            elif re.match(r"^[A-Z]{2,4}\d{3,4}L$", compact, re.IGNORECASE):
                course_code = compact  # Keep ME3010L, CS3010L, etc.
            else:
                # Strip trailing single letter (e.g., ME3010A -> ME3010)
                course_code = re.sub(r'^([A-Z]{2,4}\d{3,4})[A-Z]$', r'\1', compact)
            consumed.add(compact)
```


## Edit 89 — msg 3760 — 2026-10-11 15:58 UTC
Intent: I see the one CR regression from my room-last claim change. Let me fix it: if there's only one room-like token, keep first-claim (regression-safe); only use last-claim when there are multiple room candidates:

### OLD
```python
# When more than one token fits the room shape, the *last* one is the room:
    # a class reads "CODE-INSTRUCTOR-ROOM", so an earlier room-shaped fragment
    # ("M02" in "M02-SNS-CR102", "D03" in "D03-MZA-CR202") is a course whose
    # prefix the extractor dropped, not the venue.
    room_index: Optional[int] = None
    for idx, token in enumerate(tokens):
        compact = token.upper().replace(" ", "")
        if _is_room(compact) or _is_room_token(token):
            room_index = idx
```

### NEW
```python
# When more than one token fits the room shape, the *last* one is the room:
    # a class reads "CODE-INSTRUCTOR-ROOM", so an earlier room-shaped fragment
    # ("M02" in "M02-SNS-CR102", "D03" in "D03-MZA-CR202") is a course whose
    # prefix the extractor dropped, not the venue.
    # *If there's only one room-like token, use the first (keeps existing
    # baseline behaviour for cells with a single room such as ``L107``, ``CR208``).*
    room_indices = [
        idx for idx, token in enumerate(tokens)
        if _is_room(token.upper().replace(" ", "")) or _is_room_token(token)
    ]
    room_index = room_indices[-1] if len(room_indices) > 1 else (room_indices[0] if room_indices else None)
```


## Helper script that patched parser.py (msg 2678, ran OK at 2679)
```python
import re

with open(r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app\features\timetable\parser.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the exact section to replace
idx = content.find("is_elective = is_open_elective(course_code)")
if idx >= 0:
    # Find the start of the block
    start_idx = content.rfind("                    # Check if this course is an elective (OE prefix)", 0, idx)
    if start_idx < 0:
        start_idx = content.rfind("                    # Check if this course is an elective", 0, idx)
    
    # Find the end of the block - look for the closing of the for loop
    end_idx = content.find("                    for br in entry_branches:", idx)
    if end_idx >= 0:
        # Find the end of the for loop block
        brace_count = 0
        end_pos = content.find("                        slots.append({", idx)
        if end_pos >= 0:
            brace_count = 0
            for i in range(end_pos, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Check if next non-whitespace is not part of the same block
                        next_pos = i + 1
                        while next_pos < len(content) and content[next_pos].isspace():
                            next_pos += 1
                        if next_pos < len(content) and content[next_pos] != ' ' and content[next_pos] != '\t':
                            end_pos = i + 1
                            break
    
    if end_pos > 0:
        old_block = content[idx:end_pos]
        
        new_block = '''                    # Check if this course is an elective (OE prefix)
                    is_elective = is_open_elective(course_code)
                    
                    # For electives: no branch (they're not branch-specific)
                    # For core courses in combined branch cells, assign to correct branch based on course code prefix
                    if is_open_elective(course_code):
                        # Electives have no branch - they're not branch-specific
                        entry_branches = [""]
                    elif extra_branches:
                        # Core course in combined cell: determine correct branch from course code prefix
                        course_branch = infer_branch_from_course_code(course_code)
                        if course_branch and course_branch in branches_to_process:
                            entry_branches = [course_branch]
                        else:
                            # Fallback: use first branch if no match
                            entry_branches = [branches_to_process[0]]
                    else:
                        entry_branches = branches_to_process
                    
                    for br in entry_branches:
                        slots.append({
                            "day": day,
                            "start_time": slot_start,
                            "end_time": slot_end,
                            "room": room or "TBA",
                            "course_code": course_code,
                            "instructor": instructor or None,
                            "branch_or_program": br,
                            "semester": semester,
                        )'''
        
        if old_block in content:
            content = content.replace(old_block, new_block)
            with open(r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app\features\timetable\parser.py", "w", encoding="utf-8") as f:
                f.write(content)
            print("Successfully replaced")
        else:
            print("Old block not found exactly")
            print("Looking at:", repr(content[idx:idx+200]))
else:
    print("Pattern not found")

with open(r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app\features\timetable\parser.py", "w", encoding="utf-8") as f:
    f.write(content)
```
