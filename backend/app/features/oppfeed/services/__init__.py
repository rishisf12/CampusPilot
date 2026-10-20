"""OppFeed services package.

``sections`` exposes plain functions (see ``classify_sections``), not a class.
"""
from .opportunity_service import OpportunityService
from .publishing_service import PublishingService
from .feedback_service import FeedbackService
from .sections import (
    SECTIONS,
    SECTION_TOKENS,
    classify_sections,
    normalize_level,
    section_tokens,
)

__all__ = [
    "OpportunityService",
    "PublishingService",
    "FeedbackService",
    "SECTIONS",
    "SECTION_TOKENS",
    "classify_sections",
    "normalize_level",
    "section_tokens",
]