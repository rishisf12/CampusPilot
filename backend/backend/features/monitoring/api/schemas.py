"""Pydantic schemas for scan results - matching SCAN-AGENT.md contract.

These models are the contract between the LLM, the reconciliation pass,
and the database. They are deliberately strict: every finding must have
evidence with a metric key that the reconciler can verify.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Status(str, Enum):
    """Scan verdict status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"          # scan itself failed - never faked as healthy


class Metric(BaseModel):
    """A single metric value with provenance.

    The `metric` field must exactly match a `metric_key` returned by a
    tool call in the same scan invocation. The reconciler uses this to
    verify the model didn't hallucinate the number.
    """
    metric: str = Field(min_length=1, max_length=160)
    value: float
    unit: str = Field(max_length=24)
    previous_value: Optional[float] = None
    change_pct: Optional[float] = None
    window: str = Field(max_length=80)
    source: str = Field(max_length=64)      # tool name that produced `value`

    @model_validator(mode="after")
    def change_needs_both_ends(self) -> "Metric":
        if self.change_pct is not None and self.previous_value is None:
            raise ValueError("change_pct requires previous_value")
        return self


class Finding(BaseModel):
    """A single finding with evidence."""
    title: str = Field(min_length=3, max_length=120)
    severity: Literal["info", "warning", "critical"]
    evidence: list[Metric] = Field(min_length=1, max_length=12)


class Action(str, Enum):
    """Closed set of allowed remediation actions.

    The model cannot invent arbitrary actions - it must pick from this
    closed enum. This is a critical guardrail against prompt injection.
    """
    NO_ACTION = "no_action"
    SCALE_WORKER = "scale_worker"
    ROLLBACK_RELEASE = "rollback_release"
    INVESTIGATE_ENDPOINT = "investigate_endpoint"
    TRIAGE_CRASH_CLUSTER = "triage_crash_cluster"
    ROTATE_CREDENTIALS = "rotate_credentials"
    ADD_RATE_LIMIT = "add_rate_limit"
    REVIEW_RECENT_CHANGES = "review_recent_changes"
    FIX_BLOCKING_BUG = "fix_blocking_bug"
    CONTACT_STORE = "contact_store"
    INVESTIGATE_DATA_PIPELINE = "investigate_data_pipeline"


class Recommendation(BaseModel):
    """A prioritized recommended action."""
    action: Action
    priority: Literal[1, 2, 3]              # 1 = do now
    detail: str = Field(max_length=800)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)


class Confidence(BaseModel):
    """Confidence metadata for the scan."""
    level: Literal["low", "medium", "high"]
    missing_data: list[str] = Field(default_factory=list, max_length=20)
    tools_failed: list[str] = Field(default_factory=list, max_length=20)


class ScanResult(BaseModel):
    """Complete scan result - the contract for all eight scans."""
    schema_version: Literal[1] = 1
    scan_id: str
    subsection: Literal[
        "A_W_HEALTH", "B_W_ACTIVITY", "C_W_SECURITY", "D_W_FEEDBACK",
        "A_A_HEALTH", "B_A_ACTIVITY", "C_A_SECURITY", "D_A_FEEDBACK",
    ]
    status: Status
    summary: str = Field(min_length=20, max_length=1200)
    findings: list[Finding] = Field(max_length=8)
    root_causes: list[str] = Field(default_factory=list, max_length=6)
    recommended_actions: list[Recommendation] = Field(default_factory=list, max_length=6)
    confidence: Confidence


class ScanRequest(BaseModel):
    """Request body for triggering a scan."""
    window_days: int = Field(default=7, ge=1, le=90)
    model: Optional[str] = Field(default=None, description="Override model (e.g. 'qwen2.5:7b')")


class ScanResponse(BaseModel):
    """Response from a scan trigger."""
    scan_id: str
    subsection: str
    status: str
    summary: str
    findings: list[dict[str, Any]]
    root_causes: list[str]
    actions: list[dict[str, Any]]
    confidence: dict[str, Any]
    window_start: datetime
    window_end: datetime
    duration_ms: int
    model: str
    created_at: datetime


class SubsectionInfo(BaseModel):
    id: str
    platform: str
    group: str
    title: str


class SubsectionsResponse(BaseModel):
    subsections: list[SubsectionInfo]


class ScanHistoryResponse(BaseModel):
    scans: list[dict[str, Any]]
    incidents: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


class RollupResponse(BaseModel):
    start: str
    end: str
    buckets: int
    rows_written: int
    events_scanned: int