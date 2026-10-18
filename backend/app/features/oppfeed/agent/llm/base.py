"""Base LLM client interface - provider-agnostic contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Standardized LLM response across all providers."""

    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    """Health status for a provider."""

    provider: str
    model: str
    status: str  # "healthy", "degraded", "unavailable"
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_total: Optional[int] = None


class LLMClient(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check provider health."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model for this provider."""
        ...
