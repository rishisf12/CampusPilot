"""Phase 4 contract: provider routing, job-kind gating, LLM egress auditing.

The rules under test (docs/MCP_MIGRATION_PLAN.md, Phase 4):

1. The free allowlist is the whole universe: a named provider outside
   {nvidia_nim, openrouter} is refused at resolve time, key or not.
2. Job kinds: telemetry work refuses to start when the egress gate is not
   verified inside `run_tool`; public_data resolves freely.
3. Stage 2 config only speaks allowlisted names (or "off"); anything else
   raises before a request is built.
4. Every outbound telemetry LLM request writes one audited row with
   sent_to / redactions_applied / bytes_out / redaction_salt - and, most
   importantly, the planted-PII test proves raw rows never reach the model.
"""
import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from sqlmodel import Session, delete, select

from core.config import get_settings
from core.database import engine
from features.monitoring.api.schemas import ScanNarrative
from features.monitoring.domain.models import ToolCallAudit
from features.monitoring.domain.thresholds import ScanStatus, ScanVerdict
from features.monitoring.services import scan_service
from features.monitoring.services.llm_client import LLMConfig, resolve_llm_config
from llms import ALLOWED_PROVIDERS, LLMConfigError, resolve, resolve_for_job
from mcp.core.registry import assert_redaction_wired, redaction_wired, salt_for


@pytest.fixture
def db_session():
    """A session with `telemetry.tool_call_audit` emptied first."""
    with Session(engine) as session:
        session.exec(delete(ToolCallAudit))
        session.commit()
        yield session
        session.exec(delete(ToolCallAudit))
        session.commit()


# 1. Allowlist -----------------------------------------------------------------


def test_allowlist_is_exactly_the_free_providers():
    assert ALLOWED_PROVIDERS == {"nvidia_nim", "openrouter"}
    for provider in ("openai", "anthropic", "groq", "openai-compatible"):
        with pytest.raises(LLMConfigError, match="allowlist"):
            resolve(provider)


def test_nvidia_key_env_is_unified(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)

    # Neither key: clear refusal naming what it looked for.
    with pytest.raises(LLMConfigError, match="NVIDIA_API_KEY"):
        resolve("nvidia_nim")

    # The OppFeed name alone works...
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "legacy-key")
    assert resolve("nvidia_nim").api_key == "legacy-key"

    # ...and the primary name wins when both are set.
    monkeypatch.setenv("NVIDIA_API_KEY", "primary-key")
    assert resolve("nvidia_nim").api_key == "primary-key"


# 2. Job kinds -----------------------------------------------------------------


def test_resolve_for_job_gating(monkeypatch):
    with pytest.raises(LLMConfigError, match="job_kind"):
        resolve_for_job("unknown_kind")

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    # public_data resolves freely.
    assert resolve_for_job("public_data", "openrouter").provider == "openrouter"

    # telemetry refuses while the egress tripwire is tripped; resolve()'s key
    # path is deliberately never reached - the refusal comes first.
    from mcp.core import registry

    monkeypatch.setattr(registry, "_redaction_verified", False)
    with pytest.raises(registry.ToolError, match="egress gate not wired"):
        resolve_for_job("telemetry", "openrouter")

    monkeypatch.setattr(registry, "_redaction_verified", None)
    assert resolve_for_job("telemetry", "openrouter").provider == "openrouter"


def test_redaction_wired_tripwire_is_instrumented():
    """The contract this protects: `_egress` really sits in run_tool."""
    assert redaction_wired() is True
    assert_redaction_wired()  # does not raise


# 3. Stage 2 config ------------------------------------------------------------


def _settings(**overrides: Any) -> SimpleNamespace:
    base = {
        "llm_provider": "off",
        "llm_base_url": "",
        "llm_api_key": "",
        "llm_model": "",
        "llm_timeout": 240.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_resolve_llm_config_off_is_none():
    assert resolve_llm_config(_settings()) is None
    assert resolve_llm_config(_settings(llm_provider="OFF")) is None


def test_resolve_llm_config_refuses_anything_off_allowlist():
    for provider in ("groq", "openai-compatible", "openai"):
        with pytest.raises(LLMConfigError, match="allowlist"):
            resolve_llm_config(_settings(llm_provider=provider))


def test_resolve_llm_config_named_provider(monkeypatch):
    # A named provider inherits llms.resolve's endpoint; settings remain overrides.
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    cfg = resolve_llm_config(_settings(llm_provider="nvidia_nim", llm_model="nemotron-mini"))
    assert cfg is not None
    assert cfg.base_url == "https://integrate.api.nvidia.com/v1"
    assert cfg.model == "nemotron-mini"
    assert cfg.api_key == "k"


# 4. Stage 2 send-site: refusal e2e --------------------------------------------


class _NeverClient:
    """If the refusal path is correct, this class is never constructed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("LLM client constructed despite a refused job")


def test_stage2_refuses_bad_provider_without_building_a_request(monkeypatch, db_session):
    settings = get_settings()
    monkeypatch.setattr(settings, "scan_enabled", True)
    monkeypatch.setattr(settings, "scan_llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(scan_service, "LLMClient", _NeverClient)

    with pytest.raises(LLMConfigError, match="allowlist"):
        scan_service.run_stage2_scan(db_session, "A_W_HEALTH", 7)
    # Nothing was sent, therefore no llm.* audit row exists either.
    rows = db_session.exec(select(ToolCallAudit)).all()
    assert not [r for r in rows if (r.tool or "").startswith("llm.")]


# 5. Stage 2 send-site: egress + audit -----------------------------------------


class _CapturingClient:
    """Stands in for the HTTP client; captures what would hit the wire."""

    captured: dict[str, Any] = {}

    def __init__(self, config: LLMConfig) -> None:
        _CapturingClient.captured = {"config": config}

    async def __aenter__(self) -> "_CapturingClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def health_check(self) -> bool:
        return True

    async def chat_completion(
        self, system_prompt: str, user_prompt: str, response_model: type, temperature: float, max_tokens: int
    ) -> ScanNarrative:
        _CapturingClient.captured["system"] = system_prompt
        _CapturingClient.captured["user"] = user_prompt
        return ScanNarrative(
            summary="Feedback volume and sentiment are within expected ranges overall.",
            root_causes=[],
            recommended_actions=[],
        )


def test_planted_pii_never_reaches_the_llm_request(monkeypatch, db_session):
    planted = {
        "email": "hari.student@campus.edu",
        "phone": "+91 99887 76655",
        "ip": "192.168.4.12",
        "card": "5555 5555 5555 4444",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJsZWFrIn0.cGxhbnRlZF9zdHJpbmdfZm9yX3Rlc3Q",
        "user_id": 771209,
    }
    collected_data = {
        "rows": [
            {
                "user_id": planted["user_id"],
                "message": (
                    f"Ping {planted['email']} or call {planted['phone']} - "
                    f"from {planted['ip']}, card {planted['card']}, token {planted['jwt']}"
                ),
                "rating": 2,
            }
        ],
        "dau": 410,  # a legit metric that must survive untouched
    }

    settings = get_settings()
    monkeypatch.setattr(settings, "scan_enabled", True)
    monkeypatch.setattr(settings, "scan_llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(scan_service, "LLMClient", _CapturingClient)

    _ = salt_for("scan-llm-egress-test")  # mint the run's salt before the call

    narrative = asyncio.run(
        scan_service._run_llm_stage(
            "D_W_FEEDBACK",
            ScanVerdict(
                status=ScanStatus.HEALTHY,
                findings=[],
                root_causes=[],
                actions=[],
                confidence="high",
                missing_data=[],
            ),
            collected_data,
            start=None,  # unused by prompt construction
            end=None,
            scan_id="scan-llm-egress-test",
        )
    )
    assert narrative.summary

    wire = _CapturingClient.captured["user"]
    for secret in planted.values():
        assert str(secret) not in wire, secret
    for placeholder in ("[email]", "[phone]", "[ip]", "[card]", "[jwt]"):
        assert placeholder in wire
    assert str(planted["user_id"]) not in wire  # pseudonymized via the walker
    assert wire.count("USER_") >= 1
    # A clean metric on the wire stays exact - the gate must not blur numbers.
    assert '"dau": 410' in wire

    # The egress audit row: sent_to, redactions, bytes, salt.
    rows = db_session.exec(
        select(ToolCallAudit).where(ToolCallAudit.tool == "llm.stage2_narrative")
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.ok is True
    assert row.sent_to == "openrouter"
    assert row.redactions_applied and row.redactions_applied > 0
    assert row.bytes_out and row.bytes_out > 0
    assert row.redaction_salt == salt_for("scan-llm-egress-test")
    assert row.args["job_kind"] == "telemetry"
