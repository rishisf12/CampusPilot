"""LLM usage rows - one row per call attempt, health signal for the admin UI.

Self-contained model - no backend imports needed. Mirrors the backend's
``oppfeed_llm_usage`` table (see ``backend/app/models/llm_cache.py``) on the
agent's private registry, the same shared-table pattern ``LLMCache`` uses:
without these rows the admin status endpoint could only report ``idle`` for
every provider, because nothing else ever wrote to that table.
"""

from datetime import datetime, timezone

from sqlmodel import Field

from ..base import AgentBase


class LLMUsage(AgentBase, table=True):
    """A single LLM call attempt (successful or failed)."""

    __tablename__ = "oppfeed_llm_usage"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, max_length=100)
    provider: str = Field(max_length=50)
    model: str = Field(max_length=200)
    step_name: str = Field(max_length=100)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    latency_ms: int | None = Field(default=None)
    success: bool = Field(default=True)
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    rate_limit_remaining: int | None = Field(default=None)
    rate_limit_total: int | None = Field(default=None)
