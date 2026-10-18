"""Utility functions for the agent."""

from .dates import parse_deadline, is_future_deadline, days_until_deadline
from .dedupe import compute_opportunity_hash, fuzzy_match, is_duplicate
from .text_clean import clean_text, truncate

__all__ = [
    "parse_deadline",
    "is_future_deadline",
    "days_until_deadline",
    "compute_opportunity_hash",
    "fuzzy_match",
    "is_duplicate",
    "clean_text",
    "truncate",
]
