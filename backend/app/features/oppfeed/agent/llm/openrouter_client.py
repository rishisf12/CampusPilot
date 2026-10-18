"""OpenRouter LLM client - optional fallback provider.

Self-contained: reads config from environment variables, no backend imports.
"""

import os
import time
from typing import Any, Dict, List, Optional

import httpx

from .base import LLMClient, LLMResponse, ProviderHealth


def _get_settings():
    """Get OpenRouter settings from environment variables with defaults.

    Self-contained: no imports from web layer.
    """
    def _str(name: str, default: str = "") -> str:
        return os.environ.get(name, default)

    def _str_required(name: str) -> str:
        val = os.environ.get(name, "")
        if not val:
            raise ValueError(f"Environment variable {name} is required")
        return val

    def _int(name: str, default: int = 30) -> int:
        try:
            return int(os.environ.get(name, default))
        except (ValueError, TypeError):
            return default

    return type("OpenRouterSettings", (), {
        "OPENROUTER_API_KEY": _str_required("OPENROUTER_API_KEY"),
        "OPENROUTER_MODEL": _str("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
        "LLM_TIMEOUT_S": _int("LLM_TIMEOUT_S", 30),
    })()


class OpenRouterClient(LLMClient):
    """OpenRouter client for free-tier models.

    Self-contained: all configuration from environment variables.
    """

    def __init__(self):
        settings = _get_settings()
        self._api_key = settings.OPENROUTER_API_KEY
        self._model = settings.OPENROUTER_MODEL or "meta-llama/llama-3.1-8b-instruct:free"
        self._base_url = "https://openrouter.ai/api/v1"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://oppfeed.local",
                "X-Title": "OppFeed Agent",
            },
            timeout=httpx.Timeout(settings.LLM_TIMEOUT_S),
        )
        self._last_rate_limit_remaining: int | None = None
        self._last_rate_limit_total: int | None = None

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def default_model(self) -> str:
        return self._model

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Send chat completion to OpenRouter."""
        start = time.monotonic()

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            payload["response_format"] = response_format

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        choice = data["choices"][0]
        content = (choice.get("message") or {}).get("content")
        if content is None or not str(content).strip():
            # Empty content must not be cached/returned as success: fail so the
            # router can move to the next provider in the chain.
            raise ValueError(
                f"openrouter returned empty content (finish_reason={choice.get('finish_reason')})"
            )
        usage = data.get("usage", {})

        latency_ms = int((time.monotonic() - start) * 1000)

        # Extract rate limit headers (OpenRouter uses x-ratelimit-*)
        rate_limit_remaining = None
        rate_limit_total = None
        if "x-ratelimit-remaining" in response.headers:
            rate_limit_remaining = int(response.headers["x-ratelimit-remaining"])
        if "x-ratelimit-limit" in response.headers:
            rate_limit_total = int(response.headers["x-ratelimit-limit"])

        self._last_rate_limit_remaining = rate_limit_remaining
        self._last_rate_limit_total = rate_limit_total

        return LLMResponse(
            text=content,
            model=self._model,
            provider=self.name,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            metadata={
                "rate_limit_remaining": rate_limit_remaining,
                "rate_limit_total": rate_limit_total,
                "finish_reason": data["choices"][0].get("finish_reason"),
            },
        )

    async def list_models(self) -> List[str]:
        """List available free models."""
        response = await self._client.get("/models")
        response.raise_for_status()
        data = response.json()
        # Filter for free models only
        free_models = [
            m["id"] for m in data.get("data", [])
            if m.get("pricing", {}).get("prompt") == "0"
        ]
        return free_models

    async def health_check(self) -> ProviderHealth:
        """Check OpenRouter health."""
        start = time.monotonic()
        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
            )
            response.raise_for_status()
            latency_ms = int((time.monotonic() - start) * 1000)

            return ProviderHealth(
                provider=self.name,
                model=self._model,
                status="healthy",
                latency_ms=latency_ms,
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                model=self._model,
                status="unavailable",
                latency_ms=int((time.monotonic() - start) * 1000),
                error=str(e),
            )

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()