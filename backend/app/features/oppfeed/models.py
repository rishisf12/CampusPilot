"""OppFeed models — integrated into CampusPilot.

Follows CampusPilot conventions: unqualified tables (land in `core` via search_path),
server-side timestamps, SQLModel + SQLAlchemy enums.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, func, Integer
from sqlmodel import Field, JSON, Relationship, SQLModel
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OpportunityStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class OpportunityType(str, Enum):
    INTERNSHIP = "internship"
    JOB = "job"
    HACKATHON = "hackathon"
    FELLOWSHIP = "fellowship"


class WorkMode(str, Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class DeadlineType(str, Enum):
    FIXED = "fixed"
    ROLLING = "rolling"
    UNSPECIFIED = "unspecified"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FeedbackTag(str, Enum):
    WRONG_DEADLINE = "wrong_deadline"
    MISSING_ELIGIBILITY = "missing_eligibility"
    BAD_SUMMARY = "bad_summary"
    UNOFFICIAL_SOURCE = "unofficial_source"
    DUPLICATE = "duplicate"
    WRONG_STIPEND = "wrong_stipend"
    BAD_LOCATION = "bad_location"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------

class Opportunity(SQLModel, table=True):
    __tablename__ = "oppfeed_opportunity"
    __table_args__ = (
        sa.Index("ix_oppfeed_opportunity_status", "status"),
        sa.Index("ix_oppfeed_opportunity_type", "opportunity_type"),
        sa.Index("ix_oppfeed_opportunity_reg_deadline", "registration_deadline"),
        sa.Index("ix_oppfeed_opportunity_source_domain", "source_domain"),
        sa.Index("ix_oppfeed_opportunity_created_at", "created_at"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=200)
    status: OpportunityStatus = Field(
        default=OpportunityStatus.DRAFT,
        sa_column=Column(sa.Enum(OpportunityStatus, native_enum=False), index=True),
    )

    # Core fields
    title: str = Field(max_length=500)
    organization_name: str = Field(max_length=200, sa_column=Column(sa.String(200), index=True))
    organization_logo_url: Optional[str] = Field(default=None, max_length=1000)
    banner_url: Optional[str] = Field(default=None, max_length=1000)
    opportunity_type: OpportunityType = Field(
        sa_column=Column(sa.Enum(OpportunityType, native_enum=False), index=True),
    )
    short_summary: Optional[str] = Field(default=None, max_length=1000)
    full_description: Optional[str] = Field(default=None)

    # Location & Logistics
    location: Optional[str] = Field(default=None, max_length=200)
    work_mode: Optional[WorkMode] = Field(
        default=None,
        sa_column=Column(sa.Enum(WorkMode, native_enum=False)),
    )
    duration: Optional[str] = Field(default=None, max_length=200)
    start_date: Optional[str] = Field(default=None, max_length=100)

    # Stipend/Salary
    stipend_min: Optional[float] = Field(default=None)
    stipend_max: Optional[float] = Field(default=None)
    stipend_currency: Optional[str] = Field(default="INR", max_length=10)
    stipend_period: Optional[str] = Field(default=None, max_length=50)
    stipend_notes: Optional[str] = Field(default=None, max_length=500)

    # Registration dates
    registration_start_date: Optional[datetime] = Field(default=None)
    registration_deadline: Optional[datetime] = Field(default=None, index=True)
    deadline_type: DeadlineType = Field(
        default=DeadlineType.FIXED,
        sa_column=Column(sa.Enum(DeadlineType, native_enum=False)),
    )

    # Eligibility (JSON)
    education_levels: List[str] = Field(default=[], sa_column=Column(JSON))
    allowed_branches: List[str] = Field(default=[], sa_column=Column(JSON))
    graduation_years: List[int] = Field(default=[], sa_column=Column(JSON))
    min_cgpa_or_percentage: Optional[float] = Field(default=None)
    other_criteria: Optional[str] = Field(default=None, max_length=2000)
    open_to_countries: List[str] = Field(default=[], sa_column=Column(JSON))

    # Details
    skills_required: List[str] = Field(default=[], sa_column=Column(JSON))
    perks_benefits: List[str] = Field(default=[], sa_column=Column(JSON))
    selection_process: Optional[str] = Field(default=None, max_length=2000)
    documents_required: List[str] = Field(default=[], sa_column=Column(JSON))

    # Application
    how_to_apply: Optional[str] = Field(default=None, max_length=2000)
    apply_url: str = Field(max_length=1000)
    secondary_sources: List[str] = Field(default=[], sa_column=Column(JSON))
    attachments: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    contact_email: Optional[str] = Field(default=None, max_length=200)

    # Verification & Audit
    source_domain: Optional[str] = Field(default=None, max_length=200, index=True)
    verified_at: Optional[datetime] = Field(default=None)
    verification_report: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    field_evidence: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # LLM Audit
    llm_provider: Optional[str] = Field(default=None, max_length=50)
    llm_model: Optional[str] = Field(default=None, max_length=200)
    prompt_version: Optional[str] = Field(default=None, max_length=50)

    # Tags
    tags: List[str] = Field(default=[], sa_column=Column(JSON))

    # Versioning
    version: int = Field(default=1)
    created_by_run_id: Optional[str] = Field(default=None, index=True, max_length=100)

    # Relationships
    OppFeedFeedback: List["OppFeedFeedback"] = Relationship(back_populates="opportunity")

    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    published_at: Optional[datetime] = Field(default=None)
    scheduled_publish_at: Optional[datetime] = Field(default=None)

    def is_published(self) -> bool:
        return self.status == OpportunityStatus.PUBLISHED

    def is_expired(self) -> bool:
        if not self.registration_deadline:
            return False
        return self.registration_deadline < datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# AgentRun & RunStep
# ---------------------------------------------------------------------------

class AgentRun(SQLModel, table=True):
    __tablename__ = "oppfeed_agent_run"
    __table_args__ = (
        sa.Index("ix_oppfeed_agent_run_status", "status"),
        sa.Index("ix_oppfeed_agent_run_started_at", "started_at"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True, max_length=100)
    status: RunStatus = Field(
        default=RunStatus.PENDING,
        sa_column=Column(sa.Enum(RunStatus, native_enum=False), index=True),
    )
    mode: str = Field(default="scheduled")  # scheduled, manual, dry_run

    # Timestamps
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    # Results
    opportunities_found: int = Field(default=0)
    opportunities_verified: int = Field(default=0)
    opportunities_rejected: int = Field(default=0)
    opportunities_drafted: int = Field(default=0)
    opportunities_published: int = Field(default=0)
    errors: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # LLM usage
    llm_calls: int = Field(default=0)
    llm_tokens: int = Field(default=0)
    llm_cost_estimate: Optional[float] = Field(default=None)

    # Checkpoint for resumability
    checkpoint: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    current_stage: Optional[str] = Field(default=None, max_length=100)

    # Relationships
    steps: List["RunStep"] = Relationship(back_populates="run")


class RunStep(SQLModel, table=True):
    __tablename__ = "oppfeed_run_step"
    __table_args__ = (
        sa.Index("ix_oppfeed_run_step_run_id", "run_id"),
        sa.Index("ix_oppfeed_run_step_status", "status"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, max_length=100, foreign_key="core.oppfeed_agent_run.run_id")
    step_name: str = Field(max_length=100)
    status: StepStatus = Field(
        default=StepStatus.PENDING,
        sa_column=Column(sa.Enum(StepStatus, native_enum=False)),
    )

    # Timestamps
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # Details
    input_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    output_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    error_message: Optional[str] = Field(default=None, max_length=2000)
    llm_provider: Optional[str] = Field(default=None, max_length=50)
    llm_model: Optional[str] = Field(default=None, max_length=200)
    duration_ms: Optional[int] = Field(default=None)

    # Relationships
    run: Optional[AgentRun] = Relationship(back_populates="steps")


# ---------------------------------------------------------------------------
# The agent's own tables
#
# The agent package declares these on its own registry so it can be imported
# without the web layer. It runs inside this app, though, in this database, so
# the app owns the tables: they are created here, migrated here, and the
# agent finds them through the same search_path as everything else. The
# columns mirror the agent's exactly - the agent's queries are unqualified,
# so the two must agree on the names.
# ---------------------------------------------------------------------------

class OppFeedOpportunityDraft(SQLModel, table=True):
    """The drafts the agent saves before they become opportunities."""

    __tablename__ = "oppfeed_opportunity_draft"
    __table_args__ = ({"schema": "core"},)

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
    stipend_currency: str = Field(default="INR", max_length=10)
    stipend_period: Optional[str] = Field(default=None)
    registration_deadline: Optional[datetime] = Field(default=None)
    deadline_type: str = Field(default="fixed")
    education_levels: List[str] = Field(default=[], sa_column=Column(JSON))
    allowed_branches: List[str] = Field(default=[], sa_column=Column(JSON))
    graduation_years: List[int] = Field(default=[], sa_column=Column(JSON))
    min_cgpa_or_percentage: Optional[float] = Field(default=None)
    other_criteria: Optional[str] = Field(default=None, max_length=2000)
    skills_required: List[str] = Field(default=[], sa_column=Column(JSON))
    perks_benefits: List[str] = Field(default=[], sa_column=Column(JSON))
    selection_process: Optional[str] = Field(default=None, max_length=2000)
    documents_required: List[str] = Field(default=[], sa_column=Column(JSON))
    how_to_apply: Optional[str] = Field(default=None, max_length=2000)
    apply_url: str = Field(max_length=1000)
    secondary_sources: List[str] = Field(default=[], sa_column=Column(JSON))
    contact_email: Optional[str] = Field(default=None, max_length=200)
    source_domain: Optional[str] = Field(default=None, max_length=200)
    verification_report: Optional[dict] = Field(default={}, sa_column=Column(JSON))
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    field_evidence: Optional[dict] = Field(default={}, sa_column=Column(JSON))
    llm_provider: str = Field(default="mock", max_length=50)
    llm_model: str = Field(default="mock", max_length=200)
    prompt_version: str = Field(default="1.0", max_length=50)
    tags: List[str] = Field(default=[], sa_column=Column(JSON))
    version: int = Field(default=1)
    created_by_run_id: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now()))


class OppFeedOpportunityVerify(SQLModel, table=True):
    """What the agent's duplicate check compares against."""

    __tablename__ = "oppfeed_opportunity_verify"
    __table_args__ = ({"schema": "core"},)

    id: Optional[int] = Field(default=None, primary_key=True)
    organization_name: str = Field(max_length=200)
    title: str = Field(max_length=500)
    apply_url: str = Field(max_length=1000)
    status: OpportunityStatus = Field(default=OpportunityStatus.DRAFT)


class OppFeedOpportunityFewshot(SQLModel, table=True):
    """The approved examples the agent prompts with."""

    __tablename__ = "oppfeed_opportunity_fewshot"
    __table_args__ = ({"schema": "core"},)

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
    stipend_currency: str = Field(default="INR", max_length=10)
    stipend_period: Optional[str] = Field(default=None)
    registration_deadline: Optional[datetime] = Field(default=None)
    deadline_type: str = Field(default="fixed")
    education_levels: List[str] = Field(default=[], sa_column=Column(JSON))
    allowed_branches: List[str] = Field(default=[], sa_column=Column(JSON))
    graduation_years: List[int] = Field(default=[], sa_column=Column(JSON))
    min_cgpa_or_percentage: Optional[float] = Field(default=None)
    other_criteria: Optional[str] = Field(default=None, max_length=2000)
    skills_required: List[str] = Field(default=[], sa_column=Column(JSON))
    perks_benefits: List[str] = Field(default=[], sa_column=Column(JSON))
    selection_process: Optional[str] = Field(default=None, max_length=2000)
    documents_required: List[str] = Field(default=[], sa_column=Column(JSON))
    how_to_apply: Optional[str] = Field(default=None, max_length=2000)
    apply_url: str = Field(max_length=1000)
    secondary_sources: List[str] = Field(default=[], sa_column=Column(JSON))
    contact_email: Optional[str] = Field(default=None, max_length=200)
    source_domain: Optional[str] = Field(default=None, max_length=200)
    verification_report: Optional[dict] = Field(default={}, sa_column=Column(JSON))
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    field_evidence: Optional[dict] = Field(default={}, sa_column=Column(JSON))
    llm_provider: str = Field(default="mock", max_length=50)
    llm_model: str = Field(default="mock", max_length=200)
    prompt_version: str = Field(default="1.0", max_length=50)
    tags: List[str] = Field(default=[], sa_column=Column(JSON))
    version: int = Field(default=1)
    created_by_run_id: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now()))


# ---------------------------------------------------------------------------
# Settings, SourceRule, SearchQuery
# ---------------------------------------------------------------------------

class AgentSettings(SQLModel, table=True):
    __tablename__ = "oppfeed_agent_settings"
    __table_args__ = ({"schema": "core"},)

    id: Optional[int] = Field(default=None, primary_key=True)

    # Run window
    run_window_start: str = Field(default="02:00")
    run_window_end: str = Field(default="04:00")

    # Auto-publish
    auto_publish_enabled: bool = Field(default=False)
    auto_publish_threshold: float = Field(default=0.85)

    # LLM Provider Chain
    llm_provider_chain: str = Field(default="nvidia_nim,opencode_cli,openrouter,mock")
    llm_max_rpm: int = Field(default=30)
    #: How many drafts one run may write. A cap is a cost guard, not a
    #: limit on what may be published: a run that verified fifty-three
    #: opportunities and wrote ten of them has thrown away forty-three, and
    #: the run says so.
    max_drafts_per_run: int = Field(default=100)

    # Feature flags
    enable_agent: bool = Field(default=True)
    enable_scheduler: bool = Field(default=False)
    enable_vision: bool = Field(default=False)
    enable_banner_gen: bool = Field(default=False)
    enable_audio_summary: bool = Field(default=False)

    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )


class SourceRule(SQLModel, table=True):
    __tablename__ = "oppfeed_source_rule"
    __table_args__ = (
        sa.Index("ix_oppfeed_source_rule_domain", "domain", unique=True),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field(index=True, unique=True, max_length=200)
    rule_type: str = Field(max_length=10)  # "allow" or "deny"
    enabled: bool = Field(default=True)
    description: Optional[str] = Field(default=None, max_length=500)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


class SearchQuery(SQLModel, table=True):
    __tablename__ = "oppfeed_search_query"
    __table_args__ = (
        sa.Index("ix_oppfeed_search_query_enabled", "enabled"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    query: str = Field(max_length=500)
    category: Optional[str] = Field(default=None, max_length=50)
    enabled: bool = Field(default=True)
    is_seed: bool = Field(default=False)
    priority: int = Field(default=5)  # 1-10, higher = more important
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class OppFeedFeedback(SQLModel, table=True):
    __tablename__ = "oppfeed_feedback"
    __table_args__ = (
        sa.Index("ix_oppfeed_feedback_opportunity_id", "opportunity_id"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["core.oppfeed_opportunity.id"], ondelete="CASCADE"
        ),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    opportunity_id: int = Field(index=True)
    version: int = Field(default=1)

    # Rating
    thumbs_up: Optional[bool] = Field(default=None)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default=[], sa_column=Column(JSON))
    comment: Optional[str] = Field(default=None, max_length=2000)

    # Agent regeneration
    applied_as_instruction: bool = Field(default=False)

    # Relationships
    opportunity: Optional[Opportunity] = Relationship(back_populates="OppFeedFeedback")

    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )


# ---------------------------------------------------------------------------
# LLM Cache & Usage
# ---------------------------------------------------------------------------

class LLMCache(SQLModel, table=True):
    __tablename__ = "oppfeed_llm_cache"
    __table_args__ = (
        sa.Index("ix_oppfeed_llm_cache_key", "cache_key", unique=True),
        sa.Index("ix_oppfeed_llm_cache_expires", "expires_at"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    cache_key: str = Field(index=True, unique=True, max_length=64)
    prompt_version: str = Field(max_length=50)
    provider: str = Field(max_length=50)
    model: str = Field(max_length=200)
    response_text: str = Field(max_length=50000)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    expires_at: Optional[datetime] = Field(default=None, index=True)


class LLMUsage(SQLModel, table=True):
    __tablename__ = "oppfeed_llm_usage"
    __table_args__ = (
        sa.Index("ix_oppfeed_llm_usage_run_id", "run_id"),
        sa.Index("ix_oppfeed_llm_usage_created", "created_at"),
        {"schema": "core"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, max_length=100)
    provider: str = Field(max_length=50)
    model: str = Field(max_length=200)
    step_name: str = Field(max_length=100)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    latency_ms: Optional[int] = Field(default=None)
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None, max_length=500)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    rate_limit_remaining: Optional[int] = Field(default=None)
    rate_limit_total: Optional[int] = Field(default=None)


# ---------------------------------------------------------------------------
# Export for Alembic autogenerate
# ---------------------------------------------------------------------------
__all__ = [
    "Opportunity",
    "AgentRun",
    "RunStep",
    "AgentSettings",
    "SourceRule",
    "SearchQuery",
    "OppFeedFeedback",
    "LLMCache",
    "LLMUsage",
    "OpportunityStatus",
    "OpportunityType",
    "WorkMode",
    "DeadlineType",
    "RunStatus",
    "StepStatus",
    "FeedbackTag",
]
