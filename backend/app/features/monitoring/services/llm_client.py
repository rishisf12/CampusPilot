"""Async LLM client for the scan subsystem.

This module provides a simple async client for calling any LLM endpoint
that speaks the OpenAI-compatible `/v1/chat/completions` shape - hosted
providers (Groq free tier, HuggingFace Inference, NVIDIA NIM, OpenRouter)
or a self-hosted server behind the same protocol.

Key properties:
- API key optional (empty means no Authorization header)
- One code path for every provider: only base URL, model and key change
- Structured output via JSON schema validation (Pydantic)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    """Configuration for the Stage 2 client.

    Provider-agnostic transport: every supported backend speaks the OpenAI
    chat-completions shape, so only base URL, model and key change. But the
    *named* provider is gated by the free allowlist in `llms/` — `resolve()`
    refuses anything else. `api_key` empty means no auth header, which is
    correct for servers that need none.
    """

    #: Which allowlisted provider this config came from. Also what the LLM
    #: egress audit row records as `sent_to`.
    provider: str = ""

    #: Empty by default: the operator's config decides (see resolve_llm_config).
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout: float = 240.0
    temperature: float = 0.1

    #: 512, not 4096.
    #:
    #: A scan verdict is a status, a one-line summary and a few findings that
    #: the rule engine has already fixed - it is not prose, so a large budget
    #: only buys the model room to wander. Measured on CPU with a 4B model and
    #: a 294-token prompt: a 4096 budget ran 509s and burned ~1960 tokens before
    #: emitting a 381-character JSON object, while 512 finished the same object
    #: in 97s. The headroom bought nothing and blew the request timeout, which
    #: is what made every scan look like an LLM outage.
    max_tokens: int = 1536


class LLMError(Exception):
    """LLM-related error."""


def resolve_llm_config(settings) -> Optional["LLMConfig"]:
    """Build the Stage 2 client config from settings — or refuse.

    Rules (Phase 4 of the MCP migration plan):

    - `LLM_PROVIDER=off` (or unset) -> `None`: no LLM, Stage 2 skipped.
    - a provider on the free allowlist (`nvidia_nim`, `openrouter`, `ollama`)
      resolves through `llms.resolve`, which reads the provider's own env key.
      `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` remain plumbing overrides on
      top of the resolved endpoint.
    - any other named provider is refused with `LLMConfigError` — including the
      historic `"openai-compatible"` value, which could point anywhere and is
      exactly what the allowlist exists to prevent. Nothing is sent.
    """
    provider = (getattr(settings, "llm_provider", "") or "").strip().lower()
    if provider in ("", "off"):
        return None

    from llms import ALLOWED_PROVIDERS, LLMConfigError, resolve as resolve_llm

    if provider not in ALLOWED_PROVIDERS:
        raise LLMConfigError(
            f"LLM_PROVIDER {provider!r} is not on the free allowlist "
            f"({sorted(ALLOWED_PROVIDERS)}); Stage 2 refuses to start and no "
            "request is sent. Historic value 'openai-compatible' is no longer "
            "accepted - name nvidia_nim, openrouter or ollama."
        )
    resolved = resolve_llm(provider)
    return LLMConfig(
        provider=resolved.provider,
        base_url=settings.llm_base_url or resolved.base_url,
        model=settings.llm_model or resolved.model or "",
        api_key=settings.llm_api_key or resolved.api_key or "",
        timeout=settings.llm_timeout,
    )


class LLMClient:
    """Async client for an OpenAI-compatible chat-completions endpoint."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig(
            base_url=os.getenv("LLM_BASE_URL", ""),
            model=os.getenv("LLM_MODEL", ""),
            api_key=os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY", ""),
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._headers: dict[str, str] = (
            {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        )

    async def __aenter__(self) -> "LLMClient":
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
        max_tokens: Optional[int] = None,
    ) -> BaseModel:
        """Call chat completion and parse response as Pydantic model.

        Uses JSON schema from the response_model to guide generation.
        """
        if not self.config.base_url:
            raise LLMError("LLM_BASE_URL is not configured; Stage 2 is unavailable")
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
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
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
                headers={"Content-Type": "application/json", **self._headers},
            )
            response.raise_for_status()
            data = response.json()

            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            if not content:
                # Some reasoning models put the whole answer in a `reasoning`
                # field instead of `content`. Recover it rather than failing,
                # so a model's stream shape difference degrades to a working
                # scan rather than to no scan.
                content = message.get("reasoning") or ""
                if not content:
                    # An empty body almost always means the token budget ran
                    # out before the JSON closed. `finish_reason` says which,
                    # and surfacing it matters: "empty response" is otherwise
                    # indistinguishable from a broken model.
                    finish = data["choices"][0].get("finish_reason", "unknown")
                    usage = data.get("usage", {})
                    raise LLMError(
                        f"Empty response from LLM (finish_reason={finish}, "
                        f"completion_tokens={usage.get('completion_tokens')}, "
                        f"max_tokens={max_tokens or self.config.max_tokens}). "
                        "finish_reason=length means the answer was truncated; "
                        "check the model's reasoning output is being disabled."
                    )

            # Parse and validate
            return response_model.model_validate_json(content)

        except httpx.TimeoutException as e:
            raise LLMError(f"LLM request timed out after {self.config.timeout}s") from e
        except httpx.HTTPStatusError as e:
            raise LLMError(f"LLM HTTP error: {e.response.status_code} - {e.response.text}") from e
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse LLM response as JSON: {e}") from e
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}") from e

    async def health_check(self) -> bool:
        """Check that the endpoint is reachable and the model is available.

        Handles both response shapes. The OpenAI-compatible `/v1` surface
        answers `{"object": "list", "data": [{"id": ...}]}`, while a few
        compatible servers answer `{"models": [{"name": ...}]}`. Reading only
        one shape meant the check returned False against a perfectly healthy
        server, so Stage 2 never ran and every scan silently degraded to the
        rule engine.
        """
        if not self.config.base_url:
            return False
        try:
            client = await self._ensure_client()
            response = await client.get("/models", timeout=10.0, headers=self._headers or None)
            response.raise_for_status()
            data = response.json()
            names = [
                m.get("id") or m.get("name") or ""
                for m in (data.get("data") or data.get("models") or [])
            ]
            # Substring both ways: the config may name a tag the server reports
            # without one, or vice versa.
            return any(
                self.config.model == n or self.config.model in n or n in self.config.model
                for n in names
            )
        except Exception:  # noqa: BLE001 - endpoint unreachable means 'stage 2 unavailable'
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
    except Exception:  # noqa: BLE001 - unreadable prompt file falls back to the default
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