"""OppFeed Agent - Autonomous opportunity discovery and verification."""

from .graph import AgentPipeline
from .llm.router import LLMRouter

__version__ = "0.1.0"

__all__ = [
    "AgentPipeline",
    "LLMRouter",
]
