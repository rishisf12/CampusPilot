"""Admin settings: agent settings, source rules, LLM status endpoints.
Verified by Phase 3 ingestion; extended in Phase 8 for hardening."""
from typing import Optional

from pydantic import BaseModel


class AdminMailSettingsCreate(BaseModel):
    provider: Optional[str] = None
    poll_interval_seconds: Optional[int] = None
    require_auth_for_routing: Optional[bool] = None
