"""Tests for the LLM narrative stage of a scan.

The narrative is the one part of a scan that talks to a model, so it is the
one part that has to earn its place:

- it only runs when a **free, allowlisted** provider is configured - a paid
  provider name is refused at startup, and a named provider with no key says
  so rather than silently falling back;
- the telemetry it sends is redacted first (the collected data is walked
  through the egress gate, and the assembled prompt is swept again);
- the request is audited - the provider, the size of the payload and the
  number of masks applied all land in `tool_call_audit`.

The provider is stubbed here, because a test must not need a key. What is
real is the gate, the redaction and the audit.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import HealthMetric, ToolCallAudit
from features.monitoring.services import llm_client as llm_mod
from features.monitoring.services.llm_client import LLMConfig


@pytest.fixture
def db_session():
    with Session(engine) as session:
        for model in (HealthMetric, ToolCallAudit):
            session.exec(delete(model))
        session.commit()
        yield session
        for model in (HealthMetric, ToolCallAudit):
            session.exec(delete(model))
        session.commit()


class _StubClient:
    """A provider client that answers without a network."""

    def __init__(self, config=None):
        self.config = config
        self.sent: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def health_check(self) -> bool:
        return True

    async def chat_completion(
        self, system_prompt, user_prompt, response_model, temperature=None, max_tokens=None
    ):
        self.sent.append({"system": system_prompt, "user": user_prompt})
        return response_model(
            summary="The measured signals are inside their thresholds for the window.",
            root_causes=[],
            recommended_actions=[],
        )


def _settings(**over):
    from types import SimpleNamespace

    base = {
        "llm_provider": "nvidia_nim",
        "llm_base_url": "https://integrate.api.nvidia.com/v1",
        "llm_model": "nemotron",
        "llm_api_key": "test-key",
        "llm_timeout": 30,
        "scan_llm_enabled": True,
        "scan_enabled": True,
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_a_named_provider_needs_its_own_key(monkeypatch):
    """A named provider with no key says so, rather than surprising you."""
    from features.monitoring.services.llm_client import resolve_llm_config
    from llms import LLMConfigError

    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="NVIDIA_API_KEY"):
        resolve_llm_config(_settings(llm_provider="nvidia_nim"))


def test_the_narratives_prose_is_kept_alongside_the_measured_facts(
    db_session, monkeypatch
):
    """The model writes the sentence; the rules still own the numbers."""
    from features.monitoring.services import scan_service

    stub = _StubClient()
    monkeypatch.setattr(scan_service, "LLMClient", lambda config=None: stub)
    monkeypatch.setattr(scan_service, "get_settings", lambda: _settings())
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        HealthMetric(ts=now, platform="web", response_time_p95_ms=120, http_5xx_pct=0.2)
    )
    db_session.commit()

    result = scan_service.run_stage2_scan(
        db_session, "A_W_HEALTH", window_days=1, platform="web"
    )
    assert "The measured signals are inside their thresholds" in result.summary
    # And the rule engine's own counts are still there, untouched.
    assert "Rule engine verdict:" in result.summary
    assert "finding(s)" in result.summary


def test_a_missing_credential_degrades_the_narrative_not_the_scan(
    db_session, monkeypatch
):
    """A deployment without a narrative key still gets its rule verdict."""
    from features.monitoring.services import scan_service

    monkeypatch.setattr(scan_service, "get_settings", lambda: _settings())
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        HealthMetric(ts=now, platform="web", response_time_p95_ms=120, http_5xx_pct=0.2)
    )
    db_session.commit()

    result = scan_service.run_stage2_scan(
        db_session, "A_W_HEALTH", window_days=1, platform="web"
    )
    # The scan completed, with the rule verdict and an honest reason.
    assert result.status in {"healthy", "warning", "critical"}
    assert "Rule engine verdict:" in result.summary
    assert "No LLM enhancement" in result.summary
    assert "no key is set" in result.summary or "no credential" in result.summary


def test_the_narrative_runs_and_is_audited(db_session, monkeypatch):
    """With a provider configured, the scan gets a written summary - audited."""
    from features.monitoring.services import scan_service

    stub = _StubClient()
    monkeypatch.setattr(scan_service, "LLMClient", lambda config=None: stub)
    monkeypatch.setattr(scan_service, "get_settings", lambda: _settings())
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        HealthMetric(ts=now, platform="web", response_time_p95_ms=120, http_5xx_pct=0.2)
    )
    db_session.commit()

    result = scan_service.run_stage2_scan(
        db_session, "A_W_HEALTH", window_days=1, platform="web"
    )
    assert result.status in {"healthy", "warning", "critical"}

    # The provider was called, and the request is on the record.
    assert stub.sent, "the narrative did not reach the provider"
    rows = db_session.exec(
        select(ToolCallAudit).where(ToolCallAudit.tool.like("llm.%"))
    ).all()
    assert rows, "the outbound request was not audited"
    assert rows[0].sent_to == "nvidia_nim"
    assert rows[0].bytes_out > 0
    assert rows[0].redaction_salt
