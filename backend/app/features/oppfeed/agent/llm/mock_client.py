"""Mock LLM client - deterministic responses for offline testing."""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .base import LLMClient, LLMResponse, ProviderHealth


class MockLLMClient(LLMClient):
    """Deterministic mock client for testing and offline development."""

    def __init__(self, latency_ms: int = 100):
        self._latency_ms = latency_ms
        self._models = ["mock-model-1", "mock-model-2"]
        self._call_count = 0

    @property
    def name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-model-1"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Return deterministic mock response."""
        start = time.monotonic()
        await asyncio.sleep(self._latency_ms / 1000.0)
        self._call_count += 1

        # Return appropriate mock based on prompt content. Nodes build their own
        # prompts (prompt_version never reaches the client), so match the wording
        # each node actually sends, most specific first.
        prompt = messages[-1].get("content", "") if messages else ""
        prompt_lower = prompt.lower()

        if "search queries" in prompt_lower or ("quer" in prompt_lower and "generat" in prompt_lower):
            response_text = self._mock_query_plan()
        elif "extract" in prompt_lower or "field_evidence" in prompt_lower:
            response_text = self._mock_extraction()
        elif "verify" in prompt_lower or "scam" in prompt_lower:
            response_text = self._mock_verification()
        elif "summary" in prompt_lower:
            response_text = self._mock_summary()
        else:
            response_text = json.dumps({"status": "ok", "mock": True})

        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            text=response_text,
            model=self.default_model,
            provider=self.name,
            input_tokens=len(prompt.split()),
            output_tokens=len(response_text.split()),
            latency_ms=latency_ms,
        )

    async def list_models(self) -> List[str]:
        return self._models

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            model=self.default_model,
            status="healthy",
            latency_ms=self._latency_ms,
        )

    def _mock_query_plan(self) -> str:
        """Mock query planner response."""
        return json.dumps({
            "queries": [
                "summer internship 2026 engineering students India",
                "off campus drive freshers 2026",
                "women in tech fellowship India 2026",
                "government internship scheme India 2026",
                "hackathon India 2026 students",
            ]
        })

    def _mock_extraction(self) -> str:
        """Mock extraction response.

        The deadline is relative to now: the verify stage rejects past deadlines,
        so a hard-coded date would eventually age into one and fail every run.
        """
        deadline = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
        return json.dumps({
            "title": "Software Engineering Intern",
            "organization_name": "TechCorp India",
            "opportunity_type": "Internship",
            "location": "Bangalore",
            "work_mode": "Hybrid",
            "duration": "3 months",
            "stipend_min": 15000,
            "stipend_max": 20000,
            "stipend_currency": "INR",
            "stipend_period": "month",
            "registration_deadline": deadline,
            "deadline_type": "fixed",
            "education_levels": ["BTech", "BE"],
            "allowed_branches": ["Computer Science", "IT"],
            "graduation_years": [2026, 2027],
            "skills_required": ["Python", "JavaScript", "SQL"],
            "how_to_apply": "Apply through the company portal",
            "apply_url": "https://example.com/apply",
            "field_evidence": {
                "title": "Software Engineering Intern - TechCorp",
                "stipend_min": "Stipend: Rs. 15,000 - 20,000 per month",
            }
        })

    def _mock_verification(self) -> str:
        """Mock verification response."""
        return json.dumps({
            "is_live": True,
            "deadline_valid": True,
            "open_to_india": True,
            "is_duplicate": False,
            "is_scam": False,
            "confidence_score": 0.92,
            "checks": {
                "url_live": True,
                "deadline_future": True,
                "india_eligible": True,
                "not_duplicate": True,
                "not_scam": True,
            }
        })

    def _mock_summary(self) -> str:
        """Mock summary response."""
        return json.dumps({
            "short_summary": "TechCorp India is hiring Software Engineering Interns for a 3-month internship in Bangalore. Stipend: Rs. 15,000-20,000/month. Open to BTech/BE students in CS/IT."
        })
