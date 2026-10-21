"""LLM Router - failover chain across providers."""

import asyncio
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Sequence

from sqlmodel.ext.asyncio.session import AsyncSession

from .base import LLMClient, LLMResponse, ProviderHealth
from .cache import LLMCacheManager
from .rate_limiter import RateLimiter
from .quota_check import QuotaChecker, QuotaStatus
from .nvidia_nim_client import NVIDIAClient
from .opencode_cli_client import OpenCodeCLIClient
from .openrouter_client import OpenRouterClient
from .mock_client import MockLLMClient
from .json_repair import strip_thinking_blocks
from .usage import LLMUsage

logger = logging.getLogger(__name__)

# Transport-level failures worth one same-provider retry (the request never
# reached the model, so a retry is cheap). Timeouts are excluded: a retry
# would double a 60s wait with a poor success chance.
_TRANSIENT_MARKERS = (
    "disconnected",
    "connection reset",
    "connection aborted",
    "connection refused",
    "all connection attempts failed",
    "remote protocol error",
    " 502",
    " 503",
    " 504",
)


def _is_transient(error: str) -> bool:
    """True when the error looks like a flaky transport failure, not a bad request."""
    low = error.lower()
    return any(marker in low for marker in _TRANSIENT_MARKERS)


#: The providers the router can actually talk to: the two hosted free ones
#: (NVIDIA NIM, OpenRouter) plus the local development ones. A chain naming
#: anything else cannot work, so the seed drops those names from a chain
#: written before the provider was removed.
KNOWN_PROVIDERS: tuple[str, ...] = (
    "nvidia_nim",
    "opencode_cli",
    "openrouter",
    "mock",
)


def _get_settings():
    """Get LLM settings from environment variables with defaults.

    Makes the LLMRouter self-contained - no imports from web layer.
    """
    def _str(name: str, default: str = "") -> str:
        return os.environ.get(name, default)

    def _int(name: str, default: int = 30) -> int:
        try:
            return int(os.environ.get(name, default))
        except (ValueError, TypeError):
            return default

    def _float(name: str, default: float = 0.1) -> float:
        try:
            return float(os.environ.get(name, default))
        except (ValueError, TypeError):
            return default

    def _bool(name: str, default: bool = True) -> bool:
        val = os.environ.get(name, "")
        return val.lower() in ("true", "1", "yes", "y") if val else default

    return type("LLMSettings", (), {
        "llm_provider_chain": os.environ.get("LLM_PROVIDER_CHAIN", "mock,nvidia_nim,opencode_cli,openrouter").split(","),
        "LLM_MAX_RPM": _int("LLM_MAX_RPM", 30),
        "LLM_CACHE_TTL_HOURS": _int("LLM_CACHE_TTL_HOURS", 24),
        "MOCK_LATENCY_MS": _int("MOCK_LATENCY_MS", 10),
        "NVIDIA_MODEL": _str("NVIDIA_MODEL", "nemotron"),
        "OPENROUTER_MODEL": _str("OPENROUTER_MODEL", ""),
        "OPENCODE_MODELS": [m.strip() for m in _str("OPENCODE_MODELS", "").split(",") if m.strip()],
        "NVIDIA_API_KEY": _str("NVIDIA_API_KEY", ""),
        "OPENROUTER_API_KEY": _str("OPENROUTER_API_KEY", ""),
    })()


class LLMRouter:
    """Routes LLM requests through a failover chain of providers.

    Handles rate limiting, caching, backoff, and quota checks.
    Self-contained: no imports from web layer; all config from env vars.
    """

    def __init__(self):
        self.clients: Dict[str, LLMClient] = {}
        self.settings = _get_settings()
        # Provider/model that served the most recent response (live or cached).
        # Nodes like save_draft stamp this onto rows as provenance metadata.
        self.last_provider: str | None = None
        self.last_model: str | None = None
        # Run/stage context stamped onto oppfeed_llm_usage rows. The pipeline
        # graph sets both before each stage so every call is attributed to the
        # run that made it; direct calls (tests, scripts) keep the defaults.
        self.current_run_id: str = "adhoc"
        self.current_step: str | None = None
        self.rate_limiter = RateLimiter(
            max_rpm=self.settings.LLM_MAX_RPM,
            max_concurrency=5,
        )
        self.cache = LLMCacheManager(ttl_hours=self.settings.LLM_CACHE_TTL_HOURS)
        self.quota_checker = QuotaChecker(self.clients)
        self._setup_clients(self.settings)

    def set_chain(self, chain: Sequence[str]) -> None:
        """
        Use a provider chain from the settings rather than the environment.

        The chain the admin sets in the app is the chain the run should use -
        the environment is for the agent on its own, where there is no
        settings table to read.
        """
        self.settings.llm_provider_chain = [name for name in chain if name]
        self.clients = {}
        self.quota_checker = QuotaChecker(self.clients)
        self._setup_clients(self.settings)

    def _setup_clients(self, settings=None):
        """Initialize all provider clients."""
        if settings is None:
            settings = self.settings
        for provider in self.settings.llm_provider_chain:
            if provider == "nvidia_nim" and settings.NVIDIA_API_KEY:
                self.clients[provider] = NVIDIAClient()
            elif provider == "opencode_cli":
                self.clients[provider] = OpenCodeCLIClient()
            elif provider == "openrouter" and settings.OPENROUTER_API_KEY:
                self.clients[provider] = OpenRouterClient()
            elif provider == "mock":
                self.clients[provider] = MockLLMClient(latency_ms=settings.MOCK_LATENCY_MS)

    async def _record_usage(
        self,
        db: AsyncSession | None,
        *,
        provider: str,
        model: str,
        step_name: str,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int | None = None,
        error_message: str | None = None,
        rate_limit_remaining: int | None = None,
        rate_limit_total: int | None = None,
    ) -> None:
        """Write one row to ``oppfeed_llm_usage`` (the admin status panel's source).

        The provider health shown on /agent/llm is derived exclusively from
        these rows, so every live call attempt - success or failure - writes
        one. Bookkeeping must never break the call it describes: a failed write
        is logged and swallowed, the run row still carries llm_calls as the
        fallback counter.
        """
        if db is None:
            return
        try:
            db.add(
                LLMUsage(
                    run_id=self.current_run_id,
                    provider=provider,
                    model=model,
                    step_name=(step_name or "chat")[:100],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message[:500] if error_message else None,
                    rate_limit_remaining=rate_limit_remaining,
                    rate_limit_total=rate_limit_total,
                )
            )
            await db.commit()
        except Exception:
            logger.debug("failed to record LLM usage row for %s", provider, exc_info=True)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        prompt_version: str = "1.0",
        db: Optional[AsyncSession] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> LLMResponse:
        """Send chat request through failover chain.

        Tries each provider in order until one succeeds.
        """
        input_data = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
        }

        # Check cache first
        if use_cache and db:
            cached = await self.cache.get(db, prompt_version, input_data)
            if cached and (cached.response_text or "").strip():
                self.last_provider = cached.provider
                self.last_model = cached.model
                return LLMResponse(
                    text=cached.response_text,
                    model=cached.model,
                    provider=cached.provider,
                    input_tokens=cached.input_tokens,
                    output_tokens=cached.output_tokens,
                    cached=True,
                )
            # An empty cached entry is poisoned data from an earlier run:
            # ignore it so a live call replaces it.

        # Try each provider in chain
        last_error = None
        for provider_name in self.settings.llm_provider_chain:
            client = self.clients.get(provider_name)
            if not client:
                continue

            for attempt in range(2):
                try:
                    response = await self.rate_limiter.execute_with_limit(
                        provider_name,
                        client.chat,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                    )

                    # Strip thinking blocks from response
                    response.text = strip_thinking_blocks(response.text)
                    if not (response.text or "").strip():
                        # Never cache/return empty text: fail over instead.
                        raise ValueError(f"{provider_name} returned empty response")

                    # Cache successful response
                    if use_cache and db:
                        await self.cache.set(
                            db=db,
                            prompt_version=prompt_version,
                            input_data=input_data,
                            response_text=response.text,
                            provider=response.provider,
                            model=response.model,
                            input_tokens=response.input_tokens,
                            output_tokens=response.output_tokens,
                        )

                    self.last_provider = response.provider
                    self.last_model = response.model

                    # Live provider traffic -> health signal for the status panel.
                    # Cache hits are skipped: the original call was already recorded
                    # and a hit means no provider was contacted this time.
                    await self._record_usage(
                        db,
                        provider=response.provider,
                        model=response.model,
                        step_name=self.current_step or prompt_version,
                        success=True,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        latency_ms=response.latency_ms or None,
                        rate_limit_remaining=response.metadata.get("rate_limit_remaining"),
                        rate_limit_total=response.metadata.get("rate_limit_total"),
                    )

                    return response

                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    # Record the failed attempt so the panel can show `degraded`
                    # (with the error) instead of silently claiming health.
                    try:
                        model_name = str(client.default_model or provider_name)
                    except Exception:
                        model_name = provider_name
                    await self._record_usage(
                        db,
                        provider=provider_name,
                        model=model_name,
                        step_name=self.current_step or prompt_version,
                        success=False,
                        error_message=error_str,
                        rate_limit_remaining=getattr(client, "_last_rate_limit_remaining", None),
                        rate_limit_total=getattr(client, "_last_rate_limit_total", None),
                    )
                    # Auth errors are permanent: move to the next provider.
                    if "401" in error_str or "403" in error_str:
                        break
                    # Empty content / rate limits will not improve on a retry
                    # with the same provider: fail over.
                    if "empty" in error_str.lower() or "429" in error_str:
                        break
                    # Transient transport errors (e.g. "Server disconnected
                    # without sending a response"): retry the same provider once.
                    if attempt == 0 and _is_transient(error_str):
                        await asyncio.sleep(random.uniform(1.0, 2.5))
                        continue
                    # Backoff with jitter before trying the next provider.
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                    break

        raise Exception(f"All providers failed. Last error: {last_error}")

    async def check_all_providers(self) -> List[QuotaStatus]:
        """Check health of all providers in chain."""
        return await self.quota_checker.check_all(self.settings.llm_provider_chain)

    async def get_provider_health(self, provider: str) -> Optional[ProviderHealth]:
        """Get health for a specific provider."""
        client = self.clients.get(provider)
        if not client:
            return None
        return await client.health_check()

    def get_available_providers(self) -> List[str]:
        """Get list of configured providers."""
        return list(self.clients.keys())

    def get_active_provider(self) -> str:
        """Get first available provider in chain."""
        for provider in self.settings.llm_provider_chain:
            if provider in self.clients:
                return provider
        return "mock"