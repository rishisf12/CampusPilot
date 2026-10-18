"""NVIDIA NIM LLM client - primary provider using OpenAI-compatible API.

Self-contained: reads config from environment variables, no backend imports.
"""

import os
import time
from typing import Any, Dict, List, Optional

import httpx

from .base import LLMClient, LLMResponse, ProviderHealth


def _get_settings():
    """Get NVIDIA NIM settings from environment variables with defaults.

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

    def _float(name: str, default: float = 60.0) -> float:
        try:
            return float(os.environ.get(name, default))
        except (ValueError, TypeError):
            return default

    return type("NVIDIASettings", (), {
        "NVIDIA_API_KEY": _str_required("NVIDIA_API_KEY"),
        "NVIDIA_MODEL": _str("NVIDIA_MODEL", "nemotron"),
        "NVIDIA_FAST_MODEL": _str("NVIDIA_FAST_MODEL", "nemotron"),
        "LLM_TIMEOUT_S": _int("LLM_TIMEOUT_S", 60),
    })()


class NVIDIAClient(LLMClient):
    """NVIDIA Nemotron via NVIDIA NIM OpenAI-compatible endpoint.

    Self-contained: all configuration from environment variables.
    """

    def __init__(self):
        settings = _get_settings()
        self._api_key = settings.NVIDIA_API_KEY
        self._base_url = "https://integrate.api.nvidia.com/v1"
        self._model = settings.NVIDIA_MODEL
        self._fast_model = settings.NVIDIA_FAST_MODEL
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(settings.LLM_TIMEOUT_S),
        )
        self._last_rate_limit_remaining: int | None = None
        self._last_rate_limit_total: int | None = None

    @property
    def name(self) -> str:
        return "nvidia_nim"

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
        """Send chat completion to NVIDIA NIM."""
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
        message = choice.get("message") or {}
        content = message.get("content")
        usage = data.get("usage", {})

        if content is None or not str(content).strip():
            # Reasoning models emit `reasoning_content` and can return null
            # `content` when the token budget is consumed by reasoning. Treating
            # that as success would poison the LLM cache with empty text, so
            # fail the call and let the router fail over to the next provider.
            finish_reason = choice.get("finish_reason")
            raise ValueError(
                f"nvidia_nim returned empty content (finish_reason={finish_reason})"
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        # Extract rate limit headers
        rate_limit_remaining = None
        rate_limit_total = None
        if "x-ratelimit-remaining" in response.headers:
            rate_limit_remaining = int(response.headers["x-ratelimit-remaining"])
        if "x-ratelimit-limit" in response.headers:
            rate_limit_total = int(response.headers["x-ratelimit-limit"])

        # Store for failed-attempt recording on subsequent calls
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
        """List available models from NVIDIA NIM."""
        response = await self._client.get("/models")
        response.raise_for_status()
        data = response.json()
        return [m["id"] for m in data.get("data", [])]

    async def health_check(self) -> ProviderHealth:
        """Check NVIDIA NIM health with a tiny call."""
        start = time.monotonic()
        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._fast_model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
            )
            response.raise_for_status()
            latency_ms = int((time.monotonic() - start) * 1000)

            rate_limit_remaining = None
            rate_limit_total = None
            if "x-ratelimit-remaining" in response.headers:
                rate_limit_remaining = int(response.headers["x-ratelimit-remaining"])
            if "x-ratelimit-limit" in response.headers:
                rate_limit_total = int(response.headers["x-ratelimit-limit"])

            return ProviderHealth(
                provider=self.name,
                model=self._model,
                status="healthy",
                latency_ms=latency_ms,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_total=rate_limit_total,
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