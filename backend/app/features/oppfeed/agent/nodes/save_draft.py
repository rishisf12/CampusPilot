"""Node 8: Save Draft - persist verified opportunities to the review queue.

Self-contained: defines its own enums and Opportunity model, no backend imports needed.
"""

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

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


class DeadlineType(str, Enum):
    """Type of deadline."""

    FIXED = "fixed"
    ROLLING = "rolling"
    UNSPECIFIED = "unspecified"


class Opportunity(AgentBase, table=True):
    """Minimal opportunity model for draft saving.

    Self-contained model - no backend imports needed.
    """

    __tablename__ = "oppfeed_opportunity_draft"

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
    deadline_type: DeadlineType = Field(default=DeadlineType.FIXED)
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


def _generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title."""
    import re
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:100]


def _text(value: Any) -> str:
    """Coerce an LLM-supplied field to a plain string.

    Extractors sometimes return objects (``{"en": "..."}``) or lists for
    title/organisation fields; string methods like ``.lower()`` would crash
    the stage. Dicts prefer common text keys, then the first string value.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("en", "text", "value", "name", "title"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return ""
    if isinstance(value, (list, tuple)):
        parts = [v for v in (_text(v) for v in value) if v]
        return " ".join(parts)
    return str(value)


def _as_list(value: Any) -> list:
    """Coerce a field to a list (extractors often emit a single string)."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return _as_list(_text(value))
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    return [value]


def _as_int(value: Any) -> Optional[int]:
    """Coerce a field to int; numeric strings are common in LLM output."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return None


def _as_float(value: Any) -> Optional[float]:
    """Coerce a field to float (Postgres rejects bare strings in float columns)."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        return None


def _as_datetime(value: Any) -> Optional[datetime]:
    """Coerce a field to an aware datetime, accepting ISO strings."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _confidence(value: Any) -> float:
    """Clamp confidence into [0, 1]; extractors sometimes emit percentages."""
    score = _as_float(value)
    if score is None:
        return 0.0
    if 1.0 < score <= 100.0:
        score /= 100.0
    return max(0.0, min(1.0, score))


def _clip(value: Any, limit: int) -> Optional[str]:
    """Coerce to string and cap at the column's max length (Postgres enforces it)."""
    text = _text(value).strip()
    if not text:
        return None
    return text[:limit]


async def save_draft(
    state: "PipelineState",
    db,
    llm=None,
) -> "PipelineState":
    """Save verified opportunities as drafts in the review queue.

    ``llm`` (the pipeline's router) is optional so direct calls keep working;
    when present, its last-served provider/model is stamped as provenance.
    """
    saved_count = 0

    for template in state.template_data or []:
        # Coerce LLM-supplied strings: the extractor occasionally returns
        # objects for title/organisation, which would crash slug generation.
        title = _text(template.get("title")).strip()
        organization_name = _text(template.get("organization_name")).strip()
        if not title:
            state.errors.append({"stage": "save_draft", "error": "skipped draft with no title"})
            continue

        # Check for duplicates by slug
        slug = _generate_slug(title)
        existing = await db.exec(
            select(Opportunity).where(Opportunity.slug == slug)
        )
        if existing.first():
            continue

        # Map opportunity type (dict/odd values would raise TypeError, not ValueError)
        try:
            opp_type = OpportunityType(_text(template.get("opportunity_type")) or "Internship")
        except (ValueError, TypeError):
            opp_type = OpportunityType.INTERNSHIP

        # Map work mode
        work_mode = None
        if template.get("work_mode"):
            try:
                work_mode = WorkMode(_text(template.get("work_mode")))
            except (ValueError, TypeError):
                pass

        # Map deadline type
        deadline_type = DeadlineType.FIXED
        if template.get("deadline_type"):
            try:
                deadline_type = DeadlineType(_text(template.get("deadline_type")))
            except (ValueError, TypeError):
                pass

        # Parse deadline
        deadline = _as_datetime(template.get("registration_deadline"))
        start_date = _as_datetime(template.get("start_date"))

        opp = Opportunity(
            slug=slug,
            status=OpportunityStatus.DRAFT,
            title=title[:500],
            organization_name=organization_name[:200],
            opportunity_type=opp_type,
            short_summary=_clip(template.get("short_summary"), 2000),
            full_description=_clip(template.get("full_description"), 5000),
            location=_clip(template.get("location"), 200),
            work_mode=work_mode,
            duration=_text(template.get("duration")) or None,
            start_date=start_date,
            stipend_min=_as_int(template.get("stipend_min")),
            stipend_max=_as_int(template.get("stipend_max")),
            stipend_currency=(_text(template.get("stipend_currency")) or "INR")[:10],
            stipend_period=_text(template.get("stipend_period")) or None,
            registration_deadline=deadline,
            deadline_type=deadline_type,
            education_levels=_as_list(template.get("education_levels")),
            allowed_branches=_as_list(template.get("allowed_branches")),
            graduation_years=[y for y in (_as_int(v) for v in _as_list(template.get("graduation_years"))) if y],
            min_cgpa_or_percentage=_as_float(template.get("min_cgpa_or_percentage")),
            other_criteria=_clip(template.get("other_criteria"), 2000),
            skills_required=_as_list(template.get("skills_required")),
            perks_benefits=_as_list(template.get("perks_benefits")),
            selection_process=_clip(template.get("selection_process"), 2000),
            documents_required=_as_list(template.get("documents_required")),
            how_to_apply=_clip(template.get("how_to_apply"), 2000),
            apply_url=_text(template.get("apply_url")).strip()[:1000],
            secondary_sources=_as_list(template.get("secondary_sources")),
            contact_email=_clip(template.get("contact_email"), 200),
            source_domain=_clip(template.get("source_domain"), 200),
            verification_report=template.get("verification_report") if isinstance(template.get("verification_report"), dict) else {},
            confidence_score=_confidence(template.get("confidence_score")),
            field_evidence=template.get("field_evidence") if isinstance(template.get("field_evidence"), dict) else {},
            llm_provider=getattr(llm, "last_provider", None) or "unknown",
            llm_model=getattr(llm, "last_model", None) or "unknown",
            prompt_version="1.0",
            tags=_as_list(template.get("tags")),
            version=1,
            created_by_run_id=state.run_id,
        )

        db.add(opp)
        saved_count += 1

    await db.commit()

    state.draft_saved = True
    state.opportunities_drafted = saved_count
    state.stages_completed.append("save_draft")
    state.current_stage = "completed"

    return state