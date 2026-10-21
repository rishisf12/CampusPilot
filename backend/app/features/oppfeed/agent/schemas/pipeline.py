"""Pipeline state schema for LangGraph."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineState(BaseModel):
    """State passed between pipeline nodes."""

    # Run identification
    run_id: str = ""
    mode: str = "scheduled"  # scheduled, manual, dry_run

    # Current stage
    current_stage: str = "init"
    stages_completed: List[str] = Field(default_factory=list)

    # Query planning
    queries: List[str] = Field(default_factory=list)

    # Search results
    search_results: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)

    # Source tracing
    primary_source_url: Optional[str] = None
    secondary_sources: List[str] = Field(default_factory=list)

    # Extraction - the extracted field list, one entry per fetched page
    extracted_fields: Optional[List[Dict[str, Any]]] = None
    field_evidence: Dict[str, str] = Field(default_factory=dict)

    # Verification - the candidates that passed every check (verify node output)
    verification_result: Optional[List[Dict[str, Any]]] = None
    # Items checked/passed plus per-check rejection counts, e.g.
    # {"checked": 8, "passed": 6, "rejected_deadline_future": 2}
    verification_summary: Dict[str, int] = Field(default_factory=dict)
    confidence_score: float = 0.0

    # Template - generated opportunity templates awaiting a draft
    template_data: Optional[List[Dict[str, Any]]] = None

    # How many drafts this run may write. The app's setting travels here;
    # the default is a bound, not a limit on what may be published.
    max_drafts: int = 100

    # Output
    opportunity_id: Optional[int] = None
    draft_saved: bool = False
    opportunities_drafted: int = 0

    # Errors and tracking
    errors: List[Dict[str, str]] = Field(default_factory=list)
    llm_calls: int = 0
    llm_tokens: int = 0
    pages_fetched: int = 0

    # Checkpoint
    checkpoint: Dict[str, Any] = Field(default_factory=dict)

    def to_checkpoint(self) -> Dict[str, Any]:
        """Convert state to checkpoint dict."""
        return self.model_dump()

    @classmethod
    def from_checkpoint(cls, data: Dict[str, Any]) -> "PipelineState":
        """Restore state from checkpoint."""
        return cls(**data)
