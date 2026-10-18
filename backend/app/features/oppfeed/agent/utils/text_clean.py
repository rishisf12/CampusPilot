"""Text cleaning utilities for scraped content."""

import re
from html import unescape


def clean_text(text: str) -> str:
    """Clean and normalize scraped text content."""
    if not text:
        return ""

    # Unescape HTML entities
    text = unescape(text)

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove special characters but keep essential punctuation
    text = re.sub(r"[^\w\s.,;:!?()\-–—&/]", "", text)

    # Normalize quotes - replace smart quotes with straight quotes
    text = re.sub(r'["\u201c\u201d]', '"', text)
    text = re.sub(r"['\u2018\u2019]'", "'", text)

    # Normalize dashes
    text = re.sub(r"[–—]", "-", text)

    return text.strip()


def truncate(text: str, max_chars: int = 5000) -> str:
    """Truncate text to maximum characters, at word boundary."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Find last space to avoid cutting mid-word
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."


def extract_relevant_section(text: str, keywords: list[str], context_chars: int = 2000) -> str:
    """
    Extract relevant section of text based on keywords.
    Returns text around keyword matches.
    """
    if not text or not keywords:
        return text

    text_lower = text.lower()
    sections = []

    for keyword in keywords:
        keyword_lower = keyword.lower()
        start = 0
        while True:
            idx = text_lower.find(keyword_lower, start)
            if idx == -1:
                break

            # Get context around the keyword
            section_start = max(0, idx - context_chars // 2)
            section_end = min(len(text), idx + len(keyword) + context_chars // 2)
            sections.append(text[section_start:section_end])
            start = idx + len(keyword)

    if sections:
        return "\n\n---\n\n".join(sections)

    return text
