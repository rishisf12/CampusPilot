"""Opportunity data schemas for the agent pipeline."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExtractedFields(BaseModel):
    """Fields extracted from a page with evidence."""

    title: Optional[str] = None
    organization_name: Optional[str] = None
    opportunity_type: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    duration: Optional[str] = None
    start_date: Optional[str] = None
    stipend_min: Optional[float] = None
    stipend_max: Optional[float] = None
    stipend_currency: Optional[str] = None
    stipend_period: Optional[str] = None
    registration_deadline: Optional[datetime] = None
    deadline_type: Optional[str] = None
    education_levels: Optional[List[str]] = None
    allowed_branches: Optional[List[str]] = None
    graduation_years: Optional[List[int]] = None
    min_cgpa_or_percentage: Optional[float] = None
    other_criteria: Optional[str] = None
    skills_required: Optional[List[str]] = None
    perks_benefits: Optional[List[str]] = None
    selection_process: Optional[str] = None
    documents_required: Optional[List[str]] = None
    how_to_apply: Optional[str] = None
    apply_url: Optional[str] = None
    contact_email: Optional[str] = None

    # Evidence for each field
    field_evidence: Dict[str, str] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    """Verification result for an opportunity."""

    is_live: bool = False
    deadline_valid: bool = False
    open_to_india: bool = False
    is_duplicate: bool = False
    is_scam: bool = False
    confidence_score: float = 0.0
    checks: Dict[str, bool] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    scam_indicators: List[str] = Field(default_factory=list)


class OpportunityData(BaseModel):
    """Complete opportunity data for saving."""

    title: str
    organization_name: str
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
    registration_deadline: Optional[datetime] = None
    deadline_type: str = "fixed"
    education_levels: List[str] = Field(default_factory=list)
    allowed_branches: List[str] = Field(default_factory=list)
    graduation_years: List[int] = Field(default_factory=list)
    min_cgpa_or_percentage: Optional[float] = None
    other_criteria: Optional[str] = None
    skills_required: List[str] = Field(default_factory=list)
    perks_benefits: List[str] = Field(default_factory=list)
    selection_process: Optional[str] = None
    documents_required: List[str] = Field(default_factory=list)
    how_to_apply: Optional[str] = None
    apply_url: str
    secondary_sources: List[str] = Field(default_factory=list)
    contact_email: Optional[str] = None
    source_domain: Optional[str] = None
    verification_result: Optional[VerificationResult] = None
    confidence_score: float = 0.0
    field_evidence: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
