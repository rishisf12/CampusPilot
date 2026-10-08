"""Ollama client for local LLM inference.

This module provides a simple async client for calling a local Ollama
server. It uses the OpenAI-compatible /v1/chat/completions endpoint
that Ollama exposes.

Key properties:
- No API keys required
- No egress - runs on localhost or in the same Docker network
- CPU-only inference (models loaded on demand with keep_alive=0)
- Structured output via JSON schema validation (Pydantic)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from features.monitoring.schemas import ScanResult

logger = logging.getLogger(__name__)


class OllamaConfig(BaseModel):
    """Configuration for Ollama client."""
    base_url: str = "http://ollama:11434/v1"
    model: str = "qwen3:8b"
    timeout: float = 240.0
    temperature: float = 0.1
    max_tokens: int = 4096


class LLMError(Exception):
    """LLM-related error."""
    pass


class OllamaClient:
    """Async client for Ollama's OpenAI-compatible API."""

    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1"),
            model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OllamaClient":
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=httpx.Timeout(self.config.timeout),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout),
            )
        return self._client

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: Optional[float] = None,
    ) -> BaseModel:
        """Call Ollama chat completion and parse response as Pydantic model.

        Uses JSON schema from the response_model to guide generation.
        """
        client = await self._ensure_client()

        # Build JSON schema from Pydantic model
        schema = response_model.model_json_schema()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
        }

        try:
            response = await client.post(
                "/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            if not content:
                raise LLMError("Empty response from LLM")

            # Parse and validate
            return response_model.model_validate_json(content)

        except httpx.TimeoutException:
            raise LLMError(f"LLM request timed out after {self.config.timeout}s")
        except httpx.HTTPStatusError as e:
            raise LLMError(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse LLM response as JSON: {e}")
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}")

    async def health_check(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            client = await self._ensure_client()
            response = await client.get("/models", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(self.config.model in m for m in models)
        except Exception:
            return False


# System prompt template - loaded from SCAN-AGENT.md
def load_system_prompt() -> str:
    """Load the system prompt from SCAN-AGENT.md."""
    try:
        import pathlib
        prompt_path = pathlib.Path(__file__).parent.parent.parent.parent / "docs" / "observability" / "SCAN-AGENT.md"
        content = prompt_path.read_text(encoding="utf-8")
        # Extract the system prompt section (between "## 1. System prompt" and "## 2.")
        import re
        match = re.search(r"## 1\. System prompt\s*\n```text\n(.*?)\n```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    # Fallback - minimal prompt
    return """You are a monitoring analyst for CampusPilot. Produce a structured status report per invocation.
You are given a subsection id and time window. Use the tools to gather data, compare current vs previous vs baseline, and return JSON matching the ScanResult schema.
NEVER invent numbers. Every finding must have evidence from a tool you actually called.
Output only valid JSON matching the schema."""


# Subsection-specific prompt suffixes
SUBSECTION_PROMPTS = {
    "A_W_HEALTH": "Focus on: uptime, response time p95, 4xx/5xx rates, CPU/RAM/disk, SSL expiry, DB performance, slow endpoints.",
    "B_W_ACTIVITY": "Focus on: DAU/WAU/MAU, new vs returning, sessions, retention, top pages, funnels, geography, devices, traffic sources, revenue, ARPU, ad metrics.",
    "C_W_SECURITY": "Focus on: failed logins, brute force, suspicious IPs, WAF blocking, dependency CVEs, security headers, audit logs.",
    "D_W_FEEDBACK": "Focus on: sentiment, topic clustering, rating trends, volume, top complaints, correlation with crashes/releases.",
    "A_A_HEALTH": "Focus on: crash-free rate, crashes/ANRs with stack traces, startup time, slow frames, API failure rate, battery/memory, breakdown by app version/OS/device.",
    "B_A_ACTIVITY": "Focus on: DAU/WAU/MAU, new vs returning, sessions, retention, top screens, funnels, geography, devices, IAP revenue, ad events.",
    "C_A_SECURITY": "Focus on: root/emulator/tamper signals, API abuse, token misuse, APK tampering, dependency CVEs.",
    "D_A_FEEDBACK": "Focus on: in-app feedback sentiment, topics, ratings, correlation with crashes and releases.",
}


def build_user_prompt(subsection: str, stage1_verdict: dict, collected_data: dict) -> str:
    """Build the user prompt for the LLM with Stage 1 verdict and collected data."""
    from features.monitoring.thresholds import ScanVerdict

    # The LLM receives the Stage 1 verdict and collected data
    # It should produce the final ScanResult with summary, root_causes, actions
    prompt_parts = [
        f"Subsection: {subsection}",
        f"Stage 1 rule-based verdict: {stage1_verdict['status']}",
        f"Stage 1 findings: {stage1_verdict.get('findings', [])}",
        "",
        "Collected metrics:",
        json.dumps(collected_data, indent=2, default=str),
        "",
        f"Focus area: {SUBSECTION_PROMPTS.get(subsection, '')}",
        "",
        "Return a complete ScanResult JSON object. The status should be one of: healthy, warning, critical, error.",
        "Every finding must have evidence with metric keys that match tool calls.",
        "Actions must be from the closed enum.",
    ]
    return "\n".join(prompt_parts)