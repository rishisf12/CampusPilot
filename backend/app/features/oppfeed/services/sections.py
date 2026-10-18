"""OppFeed Feed Sections classification — CampusPilot integration.

Classify opportunities into PG / UG / BDes sections based on education_levels.
Pure functions, no DB dependencies.
"""
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

#: Section identifiers in display order.
SECTIONS: Tuple[str, str, str] = ("pg", "ug", "bdes")

#: Level values that mean "everyone may apply" regardless of degree.
OPEN_TOKENS: FrozenSet[str] = frozenset({"any", "all", "opentoall"})

#: Normalised degree token -> section. Keys are lowercase with dots, spaces,
#: hyphens and underscores stripped so "B.Tech" == "BTech" == "B-Tech".
_DEGREE_SECTIONS: Dict[str, str] = {
    # UG - bachelor's degrees (BDes is deliberately not here).
    "btech": "ug",
    "be": "ug",
    "bsc": "ug",
    "bca": "ug",
    "bba": "ug",
    "bcom": "ug",
    "ba": "ug",
    "barch": "ug",
    "bpharm": "ug",
    "llb": "ug",
    "bed": "ug",
    "bvsc": "ug",
    "mbbs": "ug",
    "bacheloroftechnology": "ug",
    "bachelorofengineering": "ug",
    # PG - master's degrees and above.
    "mtech": "pg",
    "mba": "pg",
    "msc": "pg",
    "mca": "pg",
    "ma": "pg",
    "mcom": "pg",
    "mpharm": "pg",
    "march": "pg",
    "llm": "pg",
    "phd": "pg",
    "md": "pg",
    "ms": "pg",
    "med": "pg",
    "mdes": "pg",
    "masteroftechnology": "pg",
    "masterofdesign": "pg",
    # BDes - design section.
    "bdes": "bdes",
    "bachelorofdesign": "bdes",
}

#: section -> the normalised degree tokens that qualify for it.
SECTION_TOKENS: Dict[str, Tuple[str, ...]] = {
    section: tuple(
        sorted(token for token, mapped in _DEGREE_SECTIONS.items() if mapped == section)
    )
    for section in SECTIONS
}


def normalize_level(value: str) -> str:
    """Lowercase a degree name and drop separators so ``B.Tech`` == ``btech``."""
    cleaned = str(value).strip().lower()
    for char in (".", " ", "-", "_"):
        cleaned = cleaned.replace(char, "")
    return cleaned


def classify_sections(education_levels: Optional[Iterable[str]]) -> List[str]:
    """Return the feed sections an opportunity belongs to.

    ``[]`` means the item stays in the main feed only (unclassified data);
    an empty/``Any`` input means open-to-all and returns every section.
    """
    tokens = [
        token
        for token in (normalize_level(level) for level in (education_levels or []))
        if token
    ]
    if not tokens or any(token in OPEN_TOKENS for token in tokens):
        return list(SECTIONS)
    matched = {
        _DEGREE_SECTIONS[token] for token in tokens if token in _DEGREE_SECTIONS
    }
    return [section for section in SECTIONS if section in matched]


def section_tokens(section: str) -> Sequence[str]:
    """Return the normalised degree tokens that qualify for ``section``."""
    return SECTION_TOKENS[section]