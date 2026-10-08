"""Timetable PDF/CSV parser with debug support."""
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import date, datetime, time, timedelta
import pdfplumber

from core.config import DAYS_ORDER, COLLEGE_START_HOUR

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
        dt = datetime.combine(date.today(), t)
        end = (dt + timedelta(hours=1)).time()
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
    return re.sub(r"\s+", " ", room).replace(" - ", "-").replace(" -", "-").replace("- ", "-")


# A course code is letters then digits, optionally with an elective prefix:
# "CS5031", "OE3E33", "HS1001", "ME3001". The elective prefix is kept because
# it is what distinguishes one course from another in a crowded timetable cell.
# Course codes come in the shapes used by IIITDMJ:
#   prefix + digits      "CS5031", "ME3001", "HS1001", "SM3012"
#   prefix + digit+letter+digits, for open electives and a few core papers
#                        "OE3E33" (elective), "EC5C01" (ECE), "CS8K12"
# The second shape is deliberately generous, then _is_course() narrows it.
COURSE_CODE_RE = re.compile(r"^[A-Z]{2,4}\d{1,4}[A-Z]\d{0,3}$")

# Open electives always start OE or OI, and put a letter inside the number:
# "OE3E33" is OE + 3 + E + 33, i.e. the *group* digit then the paper.
ELECTIVE_RE = re.compile(r"^(OE|OI)\d[A-Z]\d{2}$")

# A room is a letter group then a number, with or without a separator:
# "L-202", "CR208", "L202", "A-12". A digit-leading code never counts as a room.
ROOM_TOKEN_RE = re.compile(r"^[A-Z]{1,3}[-]?\d{1,4}$")

# Separators between the three fields. A dash is genuinely ambiguous here: it is
# both a field separator ("ME3001-SKC") and part of a room ("CR-208"), so the
# split cannot simply drop dashes. Instead the text is tokenised on the
# unambiguous separators first, and each piece is *then* split again on a dash
# that separates a room's letters from its digits.
FIELD_SPLIT_RE = re.compile(r"\s*[-–—/:|]\s*|\s*\n\s*")

# An instructor is initials or a short name: "SKC", "R.K.S", "AnS", "ShM".
#
# Lower-case letters are allowed so real surnames survive, which is why the
# department writes them as "AnS" and "BiG" rather than "ANS" or "BIG".
#
# Fully anchored on both sides: `|` binds looser than concatenation, so an
# unanchored branch would let "MAKE-5" match on its first letter alone.
INSTRUCTOR_RE = re.compile(
    r"^[A-Z][a-z]{0,3}"              # "S", "A"+"n", "Ma"
    r"(?:[A-Z][a-z]{0,3})*"          # "SKT", "AnS", "BiG" - capitals need no separator
    r"(?:[.\s]+[A-Za-z]{1,4})*$"     # "R.K.S", "A. Kumar"
)


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
        letters = re.match(r"^[A-Z]+", token).group(0)
        digits = re.search(r"\d+", token).group(0)
        # "CR208" fits that shape too, but a room's letter group is short (1-3)
        # and names a building; a course's is a subject prefix of 2-4.
        return not (len(letters) <= 2 and len(digits) <= 3)

    # prefix + digits + a letter inside the number, then digits: "EC5C01".
    # At least one digit must follow the letter, or the shape also swallows
    # fragments of a damaged code such as "ME5D", which the PDF truncates to
    # nothing usable.
    if re.match(r"^[A-Z]{2,4}\d{1,2}[A-Z]\d{1,3}$", token):
        return True

    # A trailing letter on a full-length code: a lab paper ("CS3010L"), or a
    # combined course the grid splits by letter ("EC203a/EC203b" -> "EC204A").
    return bool(re.match(r"^[A-Z]{2,4}\d{3,4}[A-Z]\d{0,3}$", token))


def _is_room(token: str) -> bool:
    """
    Is this token a room?

    Delegates to :func:`_is_room_token`. The two used to be separate predicates
    with different limits, and the looser one won: ``A1`` and ``B1`` passed here
    and became rooms, even though they are lab groups. One authority means a rule
    only has to be written - and changed - once.
    """
    return _is_room_token(token)


# Placeholders a timetable uses instead of real data. These must never be
# mistaken for a course, so a cell containing only one of them parses to nothing.
PLACEHOLDER_RE = re.compile(r"^[A-Z/]*$|^(TBA|TBC|N/?A|NIL|NONE|STAFF|STAFF\s*\d*|\d*)$", re.IGNORECASE)


def _looks_like_course_name(token: str) -> bool:
    """
    Could this token be a course written out rather than coded?

    Some timetables spell the subject out instead of using a code. Those are
    words, so anything without a letter or made only of placeholders is rejected.
    """
    cleaned = token.strip("()[]")
    if not cleaned or not re.search(r"[A-Za-z]{3}", cleaned):
        return False
    return not PLACEHOLDER_RE.match(cleaned)


#: Building codes used in room names, e.g. "L-102", "CR-104", "CC-3F".
_ROOM_BUILDING_RE = re.compile(r"^(?:CR|CC|L|LAB|NB|AUD|AUDI|HMT|CPPS|SH|TR)$")


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


def _prefix_can_be_a_building(prefix: str, digits: str) -> bool:
    """
    Can this letters-then-digits shape be a room?

    Three limits, each from a real mis-parse in the published grid:

    - at most three letters: ``MAKE5`` fits the shape but is a garbled cell
    - a single letter plus a single digit is a lab group, not a room: ``A1``,
      ``B1``, ``G1``
    - ``OE``/``OI`` plus digits is an elective group label (``OE3:``), never a
      room
    """
    if len(prefix) > 3:
        return False
    if len(prefix) == 1 and len(digits) == 1:
        return False
    return not (prefix in ("OE", "OI") and not re.fullmatch(r"[A-Z]\d{2}", digits))


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


def _tokenize_cell(cell: str) -> List[str]:
    """
    Break a cell into candidate fields.

    ``FIELD_SPLIT_RE`` cannot be applied blindly because ``-`` is both a field
    separator (``ME3001-SKC``) and part of a room (``CR-208``). Splitting on
    everything turns ``CR-208`` into ``CR`` and ``208``, which then read as an
    instructor and a stray number.

    So a dash is treated as a separator *except* where it joins the two halves of
    one room. The way to tell them apart is what sits either side of it:

    - ``CR-208``  letters then digits      -> a room, keep whole
    - ``ME3001-SKC`` digits then letters   -> a separator

    Everything else is split on the remaining separators, and whitespace is a
    separator too so ``ME3001 SKC CR208`` behaves like the dashed form.
    """
    text = cell.strip()
    tokens: List[str] = []
    buffer = ""

    index = 0
    length = len(text)
    while index < length:
        char = text[index]

        if char in "-–—":
            # Look at what comes before and after within this token.
            left = buffer[-1] if buffer else ""
            right = text[index + 1] if index + 1 < length else ""

            # A dash inside a room: letters before, digits after.
            if left.isalpha() and right.isdigit():
                buffer += char
                index += 1
                continue

            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            index += 1
            # Swallow spaces that follow the separator.
            while index < length and text[index].isspace():
                index += 1
            continue

        if char in "/:|" or char == "\n":
            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            index += 1
            while index < length and text[index].isspace():
                index += 1
            continue

        if char.isspace():
            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            index += 1
            continue

        buffer += char
        index += 1

    if buffer.strip():
        tokens.append(buffer.strip())

    return _rejoin_split_course_code(tokens)


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


#: A group or role marker in parentheses: "(C1)", "(VF)", "(Tut.)", "(Extra)".
#: These describe the class, not where it meets and not who teaches it, so they
#: are removed before anything is parsed - otherwise "(C1)" is the last token left
#: over and gets mistaken for a room, or "(Extra)" breaks a correct instructor.
ROLE_MARKER_RE = re.compile(
    r"\((?:VF|C\d|Tut\.[^)]*|L\d|Extra(?:\s*\d+)?)\)", re.IGNORECASE
)


#: A floor or storey: ``GF`` ground, ``FF`` first, ``3F`` third.
#:
#: One pattern, used everywhere a floor can appear. When ``_is_floor_token`` knew
#: about ``FF`` but the room regex below did not, ``CC-FF`` was rebuilt during
#: stitching and then rejected as a room - so a room that had just been
#: reconstructed disappeared, taking the instructor with it. Two lists of the same
#: idea will drift; one constant cannot.
FLOOR_PATTERN = r"(?:GF|FF|[0-9]{1,2}F)"


def _is_floor_token(token: str) -> bool:
    return bool(re.fullmatch(FLOOR_PATTERN, (token or "").strip().upper()))


#: Building codes that appear on their own in the grid, needing a number beside
#: them: "CC" + "3F" -> "CC-3F".
BUILDING_CODES = ("CR", "CC", "L", "LAB", "NB", "AUD", "AUDI", "HMT", "CPPS", "SH", "TR")


def _is_building_token(token: str) -> bool:
    """A bare building code, which needs its number or floor beside it: ``CC``."""
    return (token or "").strip().upper() in BUILDING_CODES


def _merge_room_fragments(tokens: List[str]) -> List[str]:
    """
    Rejoin a room the extractor split across several tokens.

    The grid writes rooms several ways and the separators are ambiguous, so the
    same room arrives in different pieces: ``CR-208``, ``CR: 104``, ``C R 202``,
    ``CC 3F``, ``CC2- GF``, ``AV-2F-CC``. Each has been a source of a wrong room,
    and each needed its own stitch:

    - ``C`` + ``R`` + ``202``  -> ``CR-202``   (without the C it read as ``R-202``)
    - ``CC`` + ``3F``          -> ``CC-3F``
    - ``CC2`` + ``GF``         -> ``CC2-GF``
    - ``AV`` + ``2F`` + ``CC`` -> ``CC-2F``    (the building is named last, so
      ``AV`` is the instructor and joining it to the floor gave ``AV-2F``)
    """
    merged = list(tokens)

    # Pass 0: "AV-2F" is a building and a floor stuck together. Splitting it lets
    # the floor attach to whichever building is actually the right one.
    split: List[str] = []
    for token in merged:
        piece = token.strip()
        attached = re.fullmatch(r"([A-Z]{1,3})-?([0-9]{1,2}F)", piece.upper())
        if attached and not _is_building_token(attached.group(1)):
            split.extend([attached.group(1), attached.group(2)])
        else:
            split.append(token)
    merged = split

    # Pass 1: two adjacent single letters are one building initial ("C" + "R").
    index = 0
    while index + 1 < len(merged):
        here, following = merged[index].strip(), merged[index + 1].strip()
        if re.fullmatch(r"[A-Z]", here) and re.fullmatch(r"[A-Z]", following):
            merged[index : index + 2] = [here + following]
            index = max(0, index - 1)
            continue
        index += 1

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

    # Pass 3: a floor joins a room. Prefer a room that already looks complete,
    # and fall back to a bare building code *anywhere* in the cell, because the
    # grid sometimes names the building after the floor ("AV-2F-CC" means CC, on
    # the 2nd floor).
    for position, token in enumerate(merged):
        if not _is_floor_token(token):
            continue
        others = [i for i in range(len(merged)) if i != position]
        complete = [i for i in others if _is_room_token(merged[i])]
        bare = [i for i in others if _is_building_token(merged[i].strip())]
        host = complete[-1] if complete else (bare[-1] if bare else None)
        if host is None:
            continue
        merged[host] = f"{merged[host].strip()}-{token.strip()}"
        merged[position] = ""

    return [token for token in merged if token]


def split_slot_cell(cell: str) -> tuple[str, str, str]:
    """
    Pull ``(course_code, instructor, room)`` out of one timetable cell.

    Cells look like ``ME3001-SKC-CR208``, ``CS5031:SKC:CR208`` or
    ``CS5031 | R.K.S | L-202``; the separator is not consistent across the
    document, so every common one is accepted.

    Each token is classified by shape rather than by position, because a cell may
    omit the instructor or the room:

    - a course-shaped token is the course, elective prefix included
    - a room-shaped token is the room
    - whatever is left over is the instructor

    Course codes are recognised first, so the room is never confused with one.
    """
    if not cell:
        return "", "", ""

    # Group and role markers say who the class is for, not where it meets, so
    # they go before parsing rather than after.
    cell = ROLE_MARKER_RE.sub(" ", cell)

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

    for token in tokens:
        compact = token.upper().replace(" ", "")
        if compact in consumed:
            continue
        if not course_code and _is_course(compact):
            course_code = compact
            consumed.add(compact)

    # Pass 2: what is left over is the instructor, unless there is no course.
    leftovers = [t for t in tokens if t.upper().replace(" ", "") not in consumed]
    instructor_parts: List[str] = []
    if course_code:
        instructor_parts = leftovers
    elif len(leftovers) == 1 and _looks_like_course_name(leftovers[0]):
        # A lone unrecognised token can still be a course written out in full,
        # e.g. "Design Engineering". A placeholder is not.
        course_code = leftovers[0].upper()
    else:
        instructor_parts = leftovers

    instructor = _resolve_instructor(instructor_parts, course_code)
    return course_code, instructor, room


#: Words that describe a class, not a person. They appear *after* the instructor in
#: "ME3010L-MZA-Batch A-CPPS Lab" and were enough to fail the whole name check.
CLASS_NOISE_WORDS = {
    "batch", "lab", "labs", "workshop", "studio", "design", "lecture",
    "lectures", "seminar", "tutorial", "tut", "extra", "class", "slot",
}

#: Venue words that can survive the room pass and are still not people.
VENUE_NOISE_WORDS = {"hmt", "cpps", "mc", "amp", "aud", "audi", "auditorium"}

#: A lone trailing letter that is a batch marker, not part of a name: "JKT O".
BATCH_SUFFIXES = {"o", "cc"}

#: Values that are not a person's name.
#:
#: "LAB" is dropped because it describes the *class*, not the teacher - the paper
#: code already carries an "L" for a lab, so storing it would put "LAB" in a
#: report as though it were a lecturer.
#:
#: "VF" is deliberately **kept**. It means visiting faculty, and for those cells
#: it is the only thing the document says: there is no name to find. Blanking it
#: to a dash loses the difference between "taught by someone we do not know" and
#: "taught by visiting faculty", which is a distinction a student and an admin
#: report both need. Reports that group by person must exclude it - see
#: ``instructorFor`` on the frontend, which skips VF and LAB.
NOT_A_PERSON = {"LAB", "STAFF", "TBA", "NONE", "NIL"}

#: A course code with initials welded on, no separator: "ME8016HSN",
#: "EC5C01_MDB". Two to three trailing letters are a teacher; a single "L" is a
#: lab suffix that belongs to the code.
WELDED_RE = re.compile(r"^([A-Z]{2,4}\d{3,4})_?([A-Z]{2,3})$")

#: The same, for codes with a letter inside the number: "EC5C01_MDB".
WELDED_INNER_RE = re.compile(r"^([A-Z]{2,4}\d[A-Z]?\d{2,3})_([A-Z]{2,3})$")


#: Elective codes the PDF extractor drops a character from. It reads
#: "OE2N12-MKP-CR108" correctly on one page and as "E2N12-MKP-CR108" on another,
#: losing the leading O. Every other character survives, so the shape is still
#: unmistakably an elective and the code can be put back.
#:
#: This matters more than it looks: an elective shares one cell with every other
#: elective offered in that slot, so a code that fails to parse simply disappears
#: from the timetable - on that day only, which reads as "the elective is
#: missing on Wednesdays" rather than as a parsing fault.
DROPPED_OE_RE = re.compile(r"^E(\d[A-Z]\d{2})$", re.IGNORECASE)

#: A tutorial paper, written with the suffix welded on: "NS1001T". "T" on its own
#: is never a course code, so it is a suffix rather than part of the code.
TUTORIAL_SUFFIX_RE = re.compile(r"^([A-Z]{2,4}\d{3,4})T$", re.IGNORECASE)


def _repair_course_code(token: str) -> str:
    """
    Put back a character the PDF extractor dropped, and strip a welded suffix.

    Course codes in this college are a fixed shape: two to four letters then
    digits, optionally with an "L" for a lab. A code that does not fit was either
    damaged on the way out of the PDF, or is a code with a marker stuck to it.
    """
    candidate = token.strip()

    dropped = DROPPED_OE_RE.match(candidate)
    if dropped:
        return f"OE{dropped.group(1)}"

    tutorial = TUTORIAL_SUFFIX_RE.match(candidate)
    if tutorial:
        return tutorial.group(1)

    return candidate


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

    if not name:
        return ""

    # One person, one spelling. The grid writes the same teacher as "MA",
    # "T MA" (teaching assistant) and "MA Extra" in different cells, and as
    # "JKT" and "JKT O" where "O" is a batch. Left alone, a search for a lecturer
    # finds three rows for the one person, and the attendance-by-teacher report
    # the admin section will need splits them too.
    parts = name.split()
    if len(parts) > 1 and parts[0].upper() in {"T", "TA"}:
        parts = parts[1:]
    while len(parts) > 1 and parts[-1].lower() in BATCH_SUFFIXES:
        parts = parts[:-1]
    name = " ".join(parts).strip()

    if name.upper() in NOT_A_PERSON:
        return ""
    return name


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


# A semester band marker such as "I Sem", "VII Sem".
SEMESTER_BAND_RE = re.compile(r"^([IVXL]+)\s*Sem$", re.IGNORECASE)

# A time column header such as "8:00-8:55" or "14:00 - 14:55".
TIME_HEADER_RE = re.compile(r"(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})")

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

# Cell text that means "nothing scheduled" rather than a course.
EMPTY_CELL_VALUES = {"", "-", "--", "na", "n/a", "none", "nil", "tba", "tbc", "*"}


def roman_to_int(text: str) -> Optional[int]:
    """``"VII"`` -> 7. Returns None for anything unrecognisable."""
    if not text:
        return None
    total = 0
    previous = 0
    for char in reversed(text.upper()):
        value = ROMAN_VALUES.get(char)
        if value is None:
            return None
        total = total - value if value < previous else total + value
        previous = max(previous, value)
    return total or None


def _day_from_label(text: str) -> Optional[str]:
    """
    ``"Monday"`` -> ``"Mon"``, matching the backend's short weekday form.

    The published grid spells weekdays out in full, while ``DAYS_ORDER`` and the
    stored slots use the short form, so the leading three letters are compared.
    A non-weekday label returns None.
    """
    if not text:
        return None
    candidate = " ".join(text.split())[:3].capitalize()
    return candidate if candidate in DAYS_ORDER else None


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


#: A room token: a building code plus a number or floor, or a named venue.
#: ``L102``, ``CR104``, ``CR-104``, ``CC-GF``, ``CC-3F``, ``AUDITORIUM``.
ROOM_WORD_RE = re.compile(
    r"^(?:[A-Z]{1,4}[-. ]?\d{1,4}[A-Z]?"          # L-102, CR104, CC-3F
    r"|[A-Z]{1,4}[-. ]?(?:GF|\d{1,2}F)"           # CC-GF, CC 3F
    r"|AUDITORIUM|AUDI\b|LAB\b|HMT\b|CPPS\b)$",
    re.IGNORECASE,
)

#: Noise the PDF extractor leaves behind, never a real class.
_NOISE_RE = re.compile(
    r"^\d{4}\("            # "2026(updated" from the page title
    r"|^\(.*\)$"           # "(Tut.)"
    r"|^[/.]$",
)


def _looks_like_entry(chunk: str) -> bool:
    """Is this fragment a class entry rather than a stray word or number?"""
    if not chunk or _NOISE_RE.match(chunk):
        return False
    return chunk.lower() not in EMPTY_CELL_VALUES


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


def _starts_course(chunk: str) -> bool:
    """Does this fragment begin with something shaped like a course code?"""
    token = chunk.strip("()")
    return bool(re.match(r"^(?:OE|OI)?[A-Z]{1,4}[-_. ]?\d", token, re.IGNORECASE))


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

    for table in tables:
        if not table or len(table) < 2:
            continue

        day: Optional[str] = None
        time_columns: List[tuple[int, time, time]] = []
        semester: int = 1
        branch = "Unknown"

        for row_index, row in enumerate(table):
            if not row:
                continue
            first = (row[0] or "").strip()

            # A lone weekday cell opens a section. The document spells the day out
            # in full ("Monday") while DAYS_ORDER is the short form, so match on
            # the first three letters.
            if _day_from_label(first) and not (row[1] if len(row) > 1 else "").strip():
                day = _day_from_label(first)
                time_columns = []
                semester = 1
                branch = "Unknown"
                continue

            # The time header for this day's section.
            header_times = [
                (index, *parsed)
                for index, cell in enumerate(row)
                if (parsed := _parse_header_range(cell))
            ]
            if len(header_times) >= 3:
                time_columns = header_times
                continue

            # A semester band applies to every row until the next one.
            band = SEMESTER_BAND_RE.match(first)
            if band:
                value = roman_to_int(band.group(1))
                if value:
                    semester = value
                    branch = "Unknown"
                    continue
                warnings.append(f"Row {row_index}: unreadable semester '{first}'")
                continue

            # A blank leading cell continues the branch of the row above.
            if first:
                if _is_branch_label(first):
                    branch = " ".join(first.split())
                elif not day:
                    # Before any day marker this is a title, not a branch.
                    continue

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

    if not slots and not warnings:
        warnings.append("No class entries found in the timetable")

    return slots, warnings


def _parse_header_range(cell: str) -> Optional[tuple[time, time]]:
    """``"8:00-8:55"`` -> (08:00, 08:55); None if it is not a time range."""
    if not cell:
        return None
    match = TIME_HEADER_RE.search(" ".join(cell.split()))
    if not match:
        return None
    h1, m1, h2, m2 = (int(value) for value in match.groups())
    if not (0 <= h1 <= 23 and 0 <= h2 <= 23 and 0 <= m1 <= 59 and 0 <= m2 <= 59):
        return None
    return time(h1, m1), time(h2, m2)


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

                # A cell holds course, instructor and room joined by separators,
                # e.g. "ME3001-SKC-CR208".
                course_code, instructor, room = split_slot_cell(cell)
                if not course_code:
                    continue

                # Try to find time slot for this row
                slot_start = time_slots[0] if time_slots else time(COLLEGE_START_HOUR, 0)
                slot_end = time(COLLEGE_START_HOUR + 1, 0)

                slots.append({
                    "day": day,
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "room": room or "TBA",
                    "course_code": course_code,
                    "instructor": instructor,
                    "branch_or_program": branch,
                    "semester": 1,  # Default, will be updated if detectable
                })

    return slots, warnings


def parse_csv_timetable(csv_path: Path) -> tuple[List[Dict], List[str]]:
    """
    Parse a CSV timetable.

    Columns: day,start_time,end_time,room,course_code,branch_or_program,semester
    with an optional ``instructor`` column when the source lists faculty.
    """
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
                    # Optional column: the source CSVs do not always carry one.
                    "instructor": (row.get("instructor") or "").strip() or None,
                    "branch_or_program": row["branch_or_program"].strip(),
                    "semester": int(row["semester"]),
                })
            except Exception as e:  # noqa: BLE001 - a bad row becomes a per-row warning, not a failed upload
                warnings.append(f"Row {i}: {e}")

    return slots, warnings


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
    """
    Main entry: parse PDF or CSV timetable.
    Returns dict with slots, raw_extraction, warnings, stats.
    """
    if is_csv:
        slots, warnings = parse_csv_timetable(file_path)
        raw = {"csv_rows": len(slots)}
    else:
        tables = extract_tables_from_pdf(file_path)
        slots, warnings = parse_day_section_timetable(tables)
        # Post-process: Saturday Sem 1 "Extra" classes come out with branch="Unknown"
        # because the PDF omits branch labels for that section. Duplicate them for
        # every Sem-1 branch that actually appears in the timetable so every
        # first-semester student sees them.
        slots = _expand_unknown_sem1_saturday(slots)
        # Fall back to the older column-per-day shape if the day sections yielded
        # nothing, so a differently laid out timetable is still readable.
        if not slots:
            fallback, fallback_warnings = parse_grid_timetable(tables)
            if fallback:
                logger.info(
                    "Day-section parser found nothing; column-per-day parser found %d slot(s)",
                    len(fallback),
                )
                slots = fallback
                warnings = fallback_warnings
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