"""
The sections a message can be filed under, and how one is filed.

The ids are the same ones the student's "Important" navigation uses
(academics, placement, cultural, technical, sports, other), so a section is
one thing in the navigation and one thing in the inbox.

A section sits inside a **group**. The college does not send one notice list
to everybody: the undergraduates and postgraduates have their own mailboxes,
at their own addresses, and each group's students read their group's mail
and nobody else's. So the group is the outer level and the section is the
inner one.
"""
from typing import Any, Dict, List, Optional, Tuple

#: The two mailboxes.
GROUPS: Tuple[Dict[str, str], ...] = (
    {"id": "ug", "label": "Undergraduate"},
    {"id": "pg", "label": "Postgraduate"},
)

#: The group ids, in order.
GROUP_IDS: Tuple[str, ...] = tuple(group["id"] for group in GROUPS)

#: The label for a group id.
GROUP_LABELS: Dict[str, str] = {g["id"]: g["label"] for g in GROUPS}

#: Which mailbox a programme reads. The app routes UG to one bundle and
#: PG + PhD to the other, so the mailboxes follow the bundles.
PROGRAMME_GROUPS: Dict[str, str] = {
    "BTech": "ug",
    "BDes": "ug",
    "MTech": "pg",
    "MDes": "pg",
    "PhD": "pg",
}


def group_for_programme(programme: Optional[str]) -> Optional[str]:
    """The mailbox a programme's students read, or None if unknown."""
    if not programme:
        return None
    wanted = str(programme).strip().upper()
    for name, group in PROGRAMME_GROUPS.items():
        if name.upper() == wanted:
            return group
    return None


def is_group(value: Any) -> bool:
    """Is this a group we know?"""
    return isinstance(value, str) and value in GROUP_LABELS


#: The sections, in the order they are taught out.
SECTIONS: Tuple[Dict[str, str], ...] = (
    {"id": "academics", "label": "Academics"},
    {"id": "placement", "label": "Placement Cell"},
    {"id": "cultural", "label": "Cultural"},
    {"id": "technical", "label": "Technical"},
    {"id": "sports", "label": "Sports"},
    {"id": "other", "label": "Other"},
)

#: The section ids, in order.
SECTION_IDS: Tuple[str, ...] = tuple(section["id"] for section in SECTIONS)

#: The label for a section id, or "Other" for an unknown one.
SECTION_LABELS: Dict[str, str] = {s["id"]: s["label"] for s in SECTIONS}


def is_section(value: Any) -> bool:
    """Is this a section we know?"""
    return isinstance(value, str) and value in SECTION_LABELS


#: Where mail from a sender nobody registered waits.
#:
#: It is not a section the college runs - it is the worklist of "who should
#: I register?". The admin screen lists these senders with their counts, and
#: registering one files its mail properly, so the worklist empties itself.
UNASSIGNED_SECTION = "unassigned"

#: The label for the unassigned state.
UNASSIGNED_LABEL = "Unknown sender"


def is_storable_section(value: Any) -> bool:
    """
    Is this a section a message may be filed under?

    The six sections the college runs, plus the unassigned state.
    """
    return isinstance(value, str) and (
        value in SECTION_LABELS or value == UNASSIGNED_SECTION
    )


#: Which section a message *looks* like it belongs to.
#:
#: This is a hint, not a filing: the college registers who writes to which
#: section, so the words in a mail never move it. The hint is what the admin
#: screen suggests for a sender that is not registered yet.
CLASSIFY_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "placement",
        (
            "placement",
            "tcs",
            "codevita",
            "internship drive",
            "off campus",
            "off-campus",
            "recruitment",
            "hiring",
            "apprentice",
        ),
    ),
    (
        "sports",
        (
            "sports",
            "football",
            "cricket",
            "athletics",
            "basketball",
            "tournament",
            "sports fest",
        ),
    ),
    (
        "technical",
        (
            "technical",
            "hackathon",
            "ideathon",
            "codeathon",
            "project expo",
            "workshop",
            "tech fest",
            "open source",
        ),
    ),
    (
        "cultural",
        (
            "cultural",
            "cultural fest",
            "dance",
            "music",
            "drama",
            "theatre",
            "theater",
            "fine arts",
            "literary",
        ),
    ),
    (
        "academics",
        (
            "academics",
            "academic",
            "exam",
            "timetable",
            "attendance",
            "grades",
            "cgpa",
            "curriculum",
            "class rep",
        ),
    ),
)


def classify(*parts: Any) -> str:
    """
    The section a message *looks* like it belongs to.

    Looks at the sender and the subject - and the first line of the body,
    which is where a college notice puts its heading. The first matching
    rule wins. This is a suggestion for the admin, never a filing: a
    message is filed by the sender's registered cluster or not at all.
    """
    haystack = " ".join(str(part) for part in parts if part).lower()
    for section, needles in CLASSIFY_RULES:
        if any(needle in haystack for needle in needles):
            return section
    return "other"


def section_label(section: str) -> str:
    """The label for a section id, including the unassigned state."""
    if section == UNASSIGNED_SECTION:
        return UNASSIGNED_LABEL
    return SECTION_LABELS.get(section, SECTION_LABELS["other"])
