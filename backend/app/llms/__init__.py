"""LLM bundle (see `docs/MCP_MIGRATION_PLAN.md`, bundle rule 7).

Exactly one place decides which language model a feature may use. Two rules:

1. **Free only.** The allowlist below is every permitted provider. Anything else
   — including an explicitly configured OpenAI/Anthropic key in the environment —
   is refused: resolved keys do not get past `resolve()`. Free forever or not
   shipped (owner directive 6).

2. **Named per feature.** One thin wrapper file per feature, importing this
   router — never a provider SDK directly. The current map:

   .. code-block:: text

   llms/analyst.py          -> admin bug / security-threat intelligence (mcp.analyst)
   llms/timetable_parser.py -> exam + timetable upload parsing
   llms/feedback_voice.py   -> feedback sentiment summaries

   Adding an LLM-backed feature means adding one file here and one line in that
   map — not touching any provider config elsewhere.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

#: A provider needs either a fixed base URL or one its own env var provides.
_PROVIDERS: dict[str, dict[str, str | None]] = {
    "nvidia_nim": {"base": "https://integrate.api.nvidia.com/v1", "key": "NVIDIA_NIM_API_KEY"},
    "openrouter": {"base": "https://openrouter.ai/api/v1", "key": "OPENROUTER_API_KEY"},
    "ollama": {"base": None, "key": None, "base_env": "OLLAMA_BASE_URL"},
}

#: Resolution order when no provider is named.
_PREFERENCE = ("nvidia_nim", "openrouter", "ollama")


class LLMConfigError(RuntimeError):
    """No usable free provider, or a non-allowlisted provider was requested."""


@dataclass(frozen=True)
class ResolvedLLM:
    """An OpenAI-compatible endpoint, ready to hand to an HTTP client."""

    provider: str
    base_url: str
    api_key: str | None
    model: str | None


def resolve(provider: str | None = None, model: str | None = None) -> ResolvedLLM:
    """
    Resolve a provider to its connection details — or raise `LLMConfigError`.

    `provider=None` falls back through `_PREFERENCE` picking the first one whose
    key (or local URL) is present in the environment. A named provider not on
    the free allowlist is refused even if the environment has a working key for
    it: ban the thing, not the absence of a key.
    """
    if provider is not None and provider not in _PROVIDERS:
        raise LLMConfigError(
            f"provider {provider!r} is not on the free allowlist "
            f"({sorted(_PROVIDERS)}); paid providers are not permitted"
        )
    candidates = [provider] if provider else list(_PREFERENCE)
    for candidate in candidates:
        spec = _PROVIDERS[candidate]
        base = spec["base"] or os.environ.get(spec.get("base_env") or "", "")
        if not base:
            continue
        key_env = spec["key"]
        key = os.environ.get(key_env, "") if key_env else None
        if spec["key"] and not key:
            continue  # configured base, but no credentials: try the next one
        return ResolvedLLM(provider=candidate, base_url=base, api_key=key or None, model=model)
    raise LLMConfigError(
        f"no free LLM provider is configured (looked for {candidates}; "
        "set one of the *_API_KEY / OLLAMA_BASE_URL variables)"
    )
