"""Quota check module - tests providers on startup and before each run."""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base import LLMClient, ProviderHealth


@dataclass
class QuotaStatus:
    """Quota status for a provider."""

    provider: str
    available: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    warning: Optional[str] = None


class QuotaChecker:
    """Checks provider health and quota before runs."""

    def __init__(self, clients: Dict[str, LLMClient]):
        self.clients = clients
        self._last_status: Dict[str, QuotaStatus] = {}

    async def check_provider(self, provider_name: str) -> QuotaStatus:
        """Test a single provider with a tiny call."""
        client = self.clients.get(provider_name)
        if not client:
            return QuotaStatus(
                provider=provider_name,
                available=False,
                error="Client not configured",
            )

        start = time.monotonic()
        try:
            health = await client.health_check()
            latency_ms = int((time.monotonic() - start) * 1000)

            status = QuotaStatus(
                provider=provider_name,
                available=health.status == "healthy",
                latency_ms=latency_ms,
                error=health.error,
                rate_limit_remaining=health.rate_limit_remaining,
            )

            # Warn if rate limit is low
            if health.rate_limit_remaining is not None:
                if health.rate_limit_remaining < 10:
                    status.warning = f"Low quota: {health.rate_limit_remaining} requests remaining"
                elif health.rate_limit_remaining < 50:
                    status.warning = f"Quota getting low: {health.rate_limit_remaining} remaining"

            self._last_status[provider_name] = status
            return status

        except Exception as e:
            status = QuotaStatus(
                provider=provider_name,
                available=False,
                error=str(e),
                latency_ms=int((time.monotonic() - start) * 1000),
            )
            self._last_status[provider_name] = status
            return status

    async def check_all(self, provider_chain: List[str]) -> List[QuotaStatus]:
        """Check all providers in the chain."""
        results = []
        for provider in provider_chain:
            status = await self.check_provider(provider)
            results.append(status)
        return results

    def get_last_status(self, provider: str) -> Optional[QuotaStatus]:
        """Get last known status for a provider."""
        return self._last_status.get(provider)

    def get_available_providers(self) -> List[str]:
        """Get list of providers that passed last health check."""
        return [
            name for name, status in self._last_status.items()
            if status.available
        ]
