"""Guideline builder - aggregate feedback into agent guidelines.

Self-contained: defines its own Feedback model, no backend imports needed.
"""

from typing import Dict, List, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, select

from ..base import AgentBase


class Feedback(AgentBase, table=True):
    """Minimal feedback model for guideline building.

    Self-contained model - no backend imports needed.
    """

    __tablename__ = "oppfeed_feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    opportunity_id: int = Field(index=True)
    version: int = Field(default=1)
    thumbs_up: bool = Field(default=False)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default=[], sa_column=Column(JSON))
    comment: Optional[str] = Field(default=None, max_length=2000)


# Map feedback tags to actionable guidelines
TAG_GUIDELINES = {
    "wrong_deadline": "Pay extra attention to deadline extraction. Verify dates against the original source.",
    "missing_eligibility": "Ensure all eligibility criteria are captured. Do not skip any requirements.",
    "bad_summary": "Write clear, factual summaries. Avoid hype and marketing language.",
    "unofficial_source": "Prioritize official company websites and government portals over aggregators.",
    "duplicate": "Check for duplicates before creating new entries. Verify company + title + deadline.",
    "wrong_stipend": "Double-check stipend amounts and currency. Verify against the original posting.",
    "bad_location": "Verify work mode (onsite/remote/hybrid) and location carefully.",
    "other": "Review the feedback comment for specific guidance.",
}


class GuidelineBuilder:
    """Builds agent guidelines from aggregated feedback."""

    def __init__(self):
        self._guidelines: List[str] = []

    async def build_from_db(self, db) -> str:
        """Build guidelines from all feedback in the database."""
        stmt = select(Feedback)
        feedback_items = (await db.exec(stmt)).all()

        tag_counts: Dict[str, int] = {}
        for fb in feedback_items:
            for tag in fb.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return self.build_guidelines(tag_counts)

    def build_guidelines(self, tag_counts: Dict[str, int]) -> str:
        """
        Build a guideline summary from tag counts.
        Returns a string suitable for injection into prompts.
        """
        if not tag_counts:
            return ""

        lines = [
            "## Agent Guidelines (Auto-generated from Reviewer Feedback)",
            "",
            "The following issues have been reported by reviewers. Pay extra attention to these areas:",
            "",
        ]

        # Sort by frequency (most common issues first)
        sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])

        for tag, count in sorted_tags:
            guideline = TAG_GUIDELINES.get(tag, f"Issue '{tag}' reported {count} times.")
            lines.append(f"- **{tag}** ({count} reports): {guideline}")

        lines.append("")
        lines.append("Always prioritize accuracy and completeness in these areas.")

        return "\n".join(lines)

    def get_tag_counts(self, feedback_items: List[Feedback]) -> Dict[str, int]:
        """Count occurrences of each tag."""
        tag_counts: Dict[str, int] = {}
        for fb in feedback_items:
            for tag in fb.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return tag_counts