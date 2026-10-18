"""Few-shot store - library of approved templates for few-shot examples.

Self-contained: defines its own Opportunity/OpportunityStatus models, no backend imports needed.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, select

from ..base import AgentBase


class OpportunityStatus(str, Enum):
    """Opportunity lifecycle status."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class OpportunityType(str, Enum):
    """Type of opportunity."""

    INTERNSHIP = "Internship"
    JOB = "Job"
    HACKATHON = "Hackathon"
    FELLOWSHIP = "Fellowship"


class WorkMode(str, Enum):
    """Work location mode."""

    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class Opportunity(AgentBase, table=True):
    """Minimal opportunity model for few-shot store.

    Self-contained model - no backend imports needed.
    """

    __tablename__ = "oppfeed_opportunity_fewshot"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=100)
    status: OpportunityStatus = Field(default=OpportunityStatus.DRAFT)
    title: str = Field(max_length=500)
    organization_name: str = Field(max_length=200)
    opportunity_type: OpportunityType = Field(default=OpportunityType.INTERNSHIP)
    short_summary: Optional[str] = Field(default=None, max_length=2000)
    full_description: Optional[str] = Field(default=None, max_length=5000)
    location: Optional[str] = Field(default=None, max_length=200)
    work_mode: Optional[WorkMode] = Field(default=None)
    duration: Optional[str] = Field(default=None)
    start_date: Optional[datetime] = Field(default=None)
    stipend_min: Optional[int] = Field(default=None)
    stipend_max: Optional[int] = Field(default=None)
    stipend_currency: Optional[str] = Field(default="INR", max_length=10)
    stipend_period: Optional[str] = Field(default=None)
    registration_deadline: Optional[datetime] = Field(default=None)
    deadline_type: str = Field(default="fixed")
    education_levels: list[str] = Field(default=[], sa_column=Column(JSON))
    allowed_branches: list[str] = Field(default=[], sa_column=Column(JSON))
    graduation_years: list[int] = Field(default=[], sa_column=Column(JSON))
    min_cgpa_or_percentage: Optional[float] = Field(default=None)
    other_criteria: Optional[str] = Field(default=None, max_length=2000)
    skills_required: list[str] = Field(default=[], sa_column=Column(JSON))
    perks_benefits: list[str] = Field(default=[], sa_column=Column(JSON))
    selection_process: Optional[str] = Field(default=None, max_length=2000)
    documents_required: list[str] = Field(default=[], sa_column=Column(JSON))
    how_to_apply: Optional[str] = Field(default=None, max_length=2000)
    apply_url: str = Field(max_length=1000)
    secondary_sources: list[str] = Field(default=[], sa_column=Column(JSON))
    contact_email: Optional[str] = Field(default=None, max_length=200)
    source_domain: Optional[str] = Field(default=None, max_length=200)
    verification_report: Optional[dict] = Field(default={}, sa_column=Column(JSON))
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    field_evidence: Optional[dict] = Field(default={}, sa_column=Column(JSON))
    llm_provider: str = Field(default="mock", max_length=50)
    llm_model: str = Field(default="mock", max_length=200)
    prompt_version: str = Field(default="1.0", max_length=50)
    tags: list[str] = Field(default=[], sa_column=Column(JSON))
    version: int = Field(default=1)
    created_by_run_id: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FewShotStore:
    """Manages a library of approved templates for few-shot prompting.

    Self-contained: defines its own models, no backend imports needed.
    """

    def __init__(self, max_examples: int = 3):
        self.max_examples = max_examples

    async def get_examples(self, db, opportunity_type: Optional[str] = None) -> List[dict]:
        """Get approved examples for few-shot prompting."""
        stmt = select(Opportunity).where(
            Opportunity.status == OpportunityStatus.APPROVED,
        )

        if opportunity_type:
            try:
                ot = OpportunityType(opportunity_type)
                stmt = stmt.where(Opportunity.opportunity_type == ot)
            except ValueError:
                pass

        stmt = stmt.order_by(Opportunity.confidence_score.desc()).limit(self.max_examples)
        results = (await db.exec(stmt)).all()

        return [
            {
                "title": o.title,
                "organization_name": o.organization_name,
                "opportunity_type": o.opportunity_type.value,
                "location": o.location,
                "work_mode": o.work_mode.value if o.work_mode else None,
                "stipend_min": o.stipend_min,
                "stipend_max": o.stipend_max,
                "stipend_currency": o.stipend_currency,
                "stipend_period": o.stipend_period,
                "short_summary": o.short_summary,
                "skills_required": o.skills_required,
                "how_to_apply": o.how_to_apply,
                "apply_url": o.apply_url,
            }
            for o in results
        ]

    def format_examples(self, examples: List[dict]) -> str:
        """Format examples for injection into prompts."""
        if not examples:
            return ""

        lines = [
            "## Approved Examples",
            "",
            "Here are examples of well-formatted opportunities for reference:",
            "",
        ]

        for i, ex in enumerate(examples, 1):
            lines.append(f"### Example {i}")
            lines.append(f"Title: {ex['title']}")
            lines.append(f"Organization: {ex['organization_name']}")
            lines.append(f"Type: {ex['opportunity_type']}")
            lines.append(f"Location: {ex['location']}")
            if ex.get("work_mode"):
                lines.append(f"Work Mode: {ex['work_mode']}")
            if ex.get("stipend_min"):
                lines.append(f"Stipend: {ex['stipend_min']}-{ex['stipend_max']} {ex['stipend_currency']}/{ex['stipend_period']}")
            if ex.get("short_summary"):
                lines.append(f"Summary: {ex['short_summary']}")
            lines.append("")

        return "\n".join(lines)