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

#: Provider -> connection template. Free/open-source providers only (owner
#: directive 6); this mapping IS the allowlist, re-used everywhere via
#: `ALLOWED_PROVIDERS`.
_PROVIDERS: dict[str, dict[str, str | None]] = {
    "nvidia_nim": {"base": "https://integrate.api.nvidia.com/v1", "key_envs": ("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY")},
    "openrouter": {"base": "https://openrouter.ai/api/v1", "key_envs": ("OPENROUTER_API_KEY",)},
    "ollama": {"base_env": "OLLAMA_BASE_URL", "key_envs": ()},
}

#: Auto-generated view for error messages and checks.
ALLOWED_PROVIDERS = frozenset(_PROVIDERS)

#: Resolution order when no provider is named.
_PREFERENCE = ("nvidia_nim", "openrouter", "ollama")

#: What a job may be. `telemetry` jobs carry monitoring-derived data and are
#: only allowed out after the egress gate has verified itself (see
#: `resolve_for_job`); `public_data` jobs (OppFeed) touch public pages only.
JOB_KINDS = frozenset({"telemetry", "public_data"})


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

    Key env unification (Phase 0 re-run finding): NVIDIA's key may be set as
    either `NVIDIA_API_KEY` (what the reusable OppFeed clients read) or
    `NVIDIA_NIM_API_KEY` (this module's historic name); `NVIDIA_API_KEY` wins.
    """
    if provider is not None and provider not in _PROVIDERS:
        raise LLMConfigError(
            f"provider {provider!r} is not on the free allowlist "
            f"({sorted(_PROVIDERS)}); paid providers are not permitted"
        )
    candidates = [provider] if provider else list(_PREFERENCE)
    for candidate in candidates:
        spec = _PROVIDERS[candidate]
        base = spec.get("base") or os.environ.get(spec.get("base_env") or "", "")
        if not base:
            continue
        key_envs = spec.get("key_envs") or ()
        key = next((os.environ[e] for e in key_envs if os.environ.get(e)), "")
        if key_envs and not key:
            if provider is not None:
                # Explicitly named provider, but its credentials are absent:
                # say so plainly instead of falling back to a surprise provider.
                raise LLMConfigError(
                    f"provider {candidate!r} is named but no key is set "
                    f"(looked for {list(key_envs)})"
                )
            continue  # configured base, but no credentials: try the next one
        return ResolvedLLM(provider=candidate, base_url=base, api_key=key or None, model=model)
    raise LLMConfigError(
        f"no free LLM provider is configured (looked for {candidates}; "
        "set one of the *_API_KEY / OLLAMA_BASE_URL variables)"
    )


def resolve_for_job(
    job_kind: str, provider: str | None = None, model: str | None = None
) -> ResolvedLLM:
    """`resolve()` gated by what the job is allowed to do.

    `job_kind` must be one of `JOB_KINDS`. A `telemetry` job additionally
    refuses to resolve unless the egress gate has verified itself inside
    `run_tool` — a job carrying monitoring data must never be able to send
    while the redaction wiring is missing (fail before any request is built).
    """
    if job_kind not in JOB_KINDS:
        raise LLMConfigError(
            f"job_kind {job_kind!r} not in {sorted(JOB_KINDS)}"
        )
    if job_kind == "telemetry":
        from mcp.core.registry import assert_redaction_wired  # late: avoid cycle

        assert_redaction_wired()
    return resolve(provider, model)


def __getattr__(name: str):
    """Lazy re-exports of the reusable OppFeed provider clients (Phase 4).

    Features that need a provider client import through `llms/`, never from a
    provider SDK or from the OppFeed package directly - that is the
    "no second LLM stack" rule. Late-bound via PEP 562 so merely importing
    `llms` (which `scan_service`, tests and the config do at import time)
    does not drag the OppFeed model chain along.
    """
    lazy = {
        "NVIDIAClient": "features.oppfeed.agent.llm.nvidia_nim_client",
        "OpenRouterClient": "features.oppfeed.agent.llm.openrouter_client",
        "MockLLMClient": "features.oppfeed.agent.llm.mock_client",
    }
    if name in lazy:
        import importlib

        module = importlib.import_module(lazy[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
