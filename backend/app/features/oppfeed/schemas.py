"""Pydantic schemas for OppFeed API — CampusPilot integration.

Follows CampusPilot conventions: BaseModel for request/response,
enums as strings, ISO datetime strings, optional fields = None.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Public Feed (Faculty)
# ---------------------------------------------------------------------------

class OpportunityCard(BaseModel):
    """Simplified opportunity for card display in faculty feed."""

    slug: str
    title: str
    organization_name: str
    organization_logo_url: Optional[str] = None
    opportunity_type: str
    location: Optional[str] = None
    work_mode: Optional[str] = None
    stipend_min: Optional[float] = None
    stipend_max: Optional[float] = None
    stipend_currency: str = "INR"
    stipend_period: Optional[str] = None
    registration_deadline: Optional[datetime] = None
    deadline_type: str = "fixed"
    short_summary: Optional[str] = None
    eligibility_summary: Optional[str] = None
    skills_required: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    apply_url: str
    days_until_deadline: Optional[int] = None


class OpportunityDetail(BaseModel):
    """Full opportunity detail for drawer/page view."""

    slug: str
    title: str
    organization_name: str
    organization_logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    opportunity_type: str
    short_summary: Optional[str] = None
    full_description: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    duration: Optional[str] = None
    start_date: Optional[str] = None
    stipend_min: Optional[float] = None
    stipend_max: Optional[float] = None
    stipend_currency: str = "INR"
    stipend_period: Optional[str] = None
    stipend_notes: Optional[str] = None
    registration_start_date: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    deadline_type: str = "fixed"
    education_levels: List[str] = Field(default_factory=list)
    allowed_branches: List[str] = Field(default_factory=list)
    graduation_years: List[int] = Field(default_factory=list)
    min_cgpa_or_percentage: Optional[float] = None
    other_criteria: Optional[str] = None
    open_to_countries: List[str] = Field(default_factory=list)
    skills_required: List[str] = Field(default_factory=list)
    perks_benefits: List[str] = Field(default_factory=list)
    selection_process: Optional[str] = None
    documents_required: List[str] = Field(default_factory=list)
    how_to_apply: Optional[str] = None
    apply_url: str
    secondary_sources: List[str] = Field(default_factory=list)
    contact_email: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    published_at: Optional[datetime] = None
    days_until_deadline: Optional[int] = None


class FeedFilters(BaseModel):
    """Available filter values for the feed."""

    opportunity_types: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    work_modes: List[str] = Field(default_factory=list)
    education_levels: List[str] = Field(default_factory=list)
    allowed_branches: List[str] = Field(default_factory=list)
    graduation_years: List[int] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)


class PaginatedOpportunities(BaseModel):
    """Paginated response for feed listing."""

    items: List[OpportunityCard]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---------------------------------------------------------------------------
# Admin: Opportunities Management
# ---------------------------------------------------------------------------

class OpportunityListItem(BaseModel):
    """List item for admin opportunities table."""

    id: int
    slug: str
    title: str
    organization_name: str
    opportunity_type: str
    status: str
    confidence_score: Optional[float] = None
    source_domain: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OpportunityDetailAdmin(BaseModel):
    """Full opportunity detail for admin edit/view."""

    id: int
    slug: str
    title: str
    organization_name: str
    organization_logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    opportunity_type: str
    status: str
    short_summary: Optional[str] = None
    full_description: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    duration: Optional[str] = None
    start_date: Optional[str] = None
    stipend_min: Optional[float] = None
    stipend_max: Optional[float] = None
    stipend_currency: str = "INR"
    stipend_period: Optional[str] = None
    stipend_notes: Optional[str] = None
    registration_start_date: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    deadline_type: str = "fixed"
    education_levels: List[str] = Field(default_factory=list)
    allowed_branches: List[str] = Field(default_factory=list)
    graduation_years: List[int] = Field(default_factory=list)
    min_cgpa_or_percentage: Optional[float] = None
    other_criteria: Optional[str] = None
    open_to_countries: List[str] = Field(default_factory=list)
    skills_required: List[str] = Field(default_factory=list)
    perks_benefits: List[str] = Field(default_factory=list)
    selection_process: Optional[str] = None
    documents_required: List[str] = Field(default_factory=list)
    how_to_apply: Optional[str] = None
    apply_url: str
    secondary_sources: List[str] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    contact_email: Optional[str] = None
    source_domain: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_report: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    field_evidence: Optional[Dict[str, Any]] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_version: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    version: int
    created_by_run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    scheduled_publish_at: Optional[datetime] = None


class OpportunityUpdateRequest(BaseModel):
    """Request to update an opportunity (admin)."""

    title: Optional[str] = Field(default=None, max_length=500)
    short_summary: Optional[str] = Field(default=None, max_length=1000)
    full_description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=200)
    work_mode: Optional[str] = None
    duration: Optional[str] = Field(default=None, max_length=200)
    stipend_min: Optional[float] = None
    stipend_max: Optional[float] = None
    stipend_currency: Optional[str] = Field(default=None, max_length=10)
    stipend_period: Optional[str] = Field(default=None, max_length=50)
    registration_deadline: Optional[datetime] = None
    deadline_type: Optional[str] = None
    education_levels: Optional[List[str]] = None
    allowed_branches: Optional[List[str]] = None
    graduation_years: Optional[List[int]] = None
    skills_required: Optional[List[str]] = None
    perks_benefits: Optional[List[str]] = None
    how_to_apply: Optional[str] = Field(default=None, max_length=2000)
    apply_url: Optional[str] = Field(default=None, max_length=1000)
    tags: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    scheduled_publish_at: Optional[datetime] = None


class BulkActionRequest(BaseModel):
    """Bulk action request for opportunities."""

    ids: List[int] = Field(min_length=1)
    action: str  # approve, reject, publish, schedule, archive, delete
    scheduled_publish_at: Optional[datetime] = None


class StateTransitionRequest(BaseModel):
    """Request to transition opportunity state."""

    action: str  # approve, reject, publish, schedule, archive
    scheduled_publish_at: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Admin: Agent Runs
# ---------------------------------------------------------------------------

class RunStepResponse(BaseModel):
    """Run step detail."""

    step_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class RunResponse(BaseModel):
    """Full run detail with steps."""

    run_id: str
    status: str
    mode: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    opportunities_found: int = 0
    opportunities_verified: int = 0
    opportunities_rejected: int = 0
    opportunities_drafted: int = 0
    opportunities_published: int = 0
    errors: Optional[List[str]] = None
    llm_calls: int = 0
    llm_tokens: int = 0
    current_stage: Optional[str] = None
    steps: List[RunStepResponse] = Field(default_factory=list)


class RunListItem(BaseModel):
    """Run summary for list view."""

    run_id: str
    status: str
    mode: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    opportunities_found: int = 0
    opportunities_published: int = 0


class RunCreateRequest(BaseModel):
    """Create a new agent run."""

    mode: str = Field(default="manual", pattern="^(manual|dry_run)$")


# ---------------------------------------------------------------------------
# Admin: Agent Settings
# ---------------------------------------------------------------------------

class AgentSettingsResponse(BaseModel):
    """Current agent settings."""

    run_window_start: str
    run_window_end: str
    auto_publish_enabled: bool
    auto_publish_threshold: float
    llm_provider_chain: str
    llm_max_rpm: int
    enable_agent: bool
    enable_scheduler: bool
    enable_vision: bool
    enable_banner_gen: bool
    enable_audio_summary: bool


class AgentSettingsUpdateRequest(BaseModel):
    """Update agent settings."""

    run_window_start: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    run_window_end: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    auto_publish_enabled: Optional[bool] = None
    auto_publish_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    llm_provider_chain: Optional[str] = None
    llm_max_rpm: Optional[int] = Field(default=None, ge=1, le=1000)
    enable_agent: Optional[bool] = None
    enable_scheduler: Optional[bool] = None
    enable_vision: Optional[bool] = None
    enable_banner_gen: Optional[bool] = None
    enable_audio_summary: Optional[bool] = None


# ---------------------------------------------------------------------------
# Source Rules
# ---------------------------------------------------------------------------

class SourceRuleResponse(BaseModel):
    """Source rule detail."""

    id: int
    domain: str
    rule_type: str  # "allow" or "deny"
    enabled: bool
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class SourceRuleCreateRequest(BaseModel):
    """Create a source rule."""

    domain: str = Field(max_length=200)
    rule_type: str = Field(pattern="^(allow|deny)$")
    description: Optional[str] = Field(default=None, max_length=500)


class SourceRuleUpdateRequest(BaseModel):
    """Update a source rule."""

    enabled: Optional[bool] = None
    description: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Search Queries
# ---------------------------------------------------------------------------

class SearchQueryResponse(BaseModel):
    """Search query detail."""

    id: int
    query: str
    category: Optional[str] = None
    enabled: bool
    is_seed: bool
    priority: int
    created_at: Optional[datetime] = None


class SearchQueryCreateRequest(BaseModel):
    """Create a search query."""

    query: str = Field(max_length=500)
    category: Optional[str] = Field(default=None, max_length=50)
    enabled: bool = True
    is_seed: bool = False
    priority: int = Field(default=5, ge=1, le=10)


class SearchQueryUpdateRequest(BaseModel):
    """Update a search query."""

    query: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=50)
    enabled: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=10)


# ---------------------------------------------------------------------------
# LLM Status
# ---------------------------------------------------------------------------

class ProviderHealth(BaseModel):
    """Health status for a single LLM provider."""

    provider: str
    status: str  # healthy, degraded, unavailable
    model: str
    latency_ms: Optional[int] = None
    last_checked: Optional[str] = None
    error: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_total: Optional[int] = None


class LLMStatusResponse(BaseModel):
    """Overall LLM status."""

    providers: List[ProviderHealth] = Field(default_factory=list)
    active_provider: str
    cache_hit_rate: float = 0.0
    total_calls_today: int = 0


class LLMTestRequest(BaseModel):
    """Test an LLM provider."""

    provider: Optional[str] = None  # None = test all
    prompt: str = "Say hello in one word."


class LLMTestResponse(BaseModel):
    """LLM test result."""

    provider: str
    model: str
    success: bool
    response: Optional[str] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackResponse(BaseModel):
    """Reviewer feedback on an opportunity."""

    id: int
    opportunity_id: int
    version: int
    thumbs_up: Optional[bool] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    comment: Optional[str] = None
    applied_as_instruction: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FeedbackCreateRequest(BaseModel):
    """Create reviewer feedback on an opportunity."""

    thumbs_up: Optional[bool] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    comment: Optional[str] = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Query Parameters
# ---------------------------------------------------------------------------

class PaginationParams(BaseModel):
    """Standard pagination parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class OpportunityFilterParams(PaginationParams):
    """Filter parameters for opportunity listings."""

    status: Optional[str] = None
    opportunity_type: Optional[str] = None
    search: Optional[str] = None
    source_domain: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class RunFilterParams(PaginationParams):
    """Filter parameters for run listings."""

    status: Optional[str] = None
    mode: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
