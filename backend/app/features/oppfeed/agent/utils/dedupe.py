"""Duplicate detection utilities for opportunity titles and descriptions."""

import difflib
import hashlib
import re
from html import unescape


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    text = unescape(text)
    text = text.lower().strip()
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)
    return text


def fuzzy_match(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """Check if two titles are fuzzy matches.

    Uses SequenceMatcher ratio for similarity comparison.
    """
    ratio = difflib.SequenceMatcher(None, normalize_text(title1), normalize_text(title2)).ratio()
    return ratio >= threshold


def compute_opportunity_hash(
    title: str,
    organization: str,
    date: str,
    url: str,
) -> str:
    """Compute a hash for opportunity deduplication.

    Combines title, organization, date, and URL into a deterministic hash.
    """
    combined = f"{title}|{organization}|{date}|{url}"
    return hashlib.sha256(combined.encode()).hexdigest()


def is_duplicate(title1: str, title2: str, url1: str = None, url2: str = None) -> bool:
    """Check if two opportunities are duplicates.

    Uses fuzzy title matching and URL comparison.
    """
    title_match = fuzzy_match(title1, title2)
    url_match = url1 is not None and url2 is not None and url1 == url2
    return title_match or url_match