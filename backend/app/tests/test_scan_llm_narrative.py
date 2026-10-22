"""Tests for the model stage of a scan.

The model is the one part of a scan that talks to someone else's computer,
so it is the one part that has to earn its place:

- it only runs through a **free, allowlisted** provider - a paid provider
  name is refused before a client is built, and a named provider with no key
  says so rather than surprising you;
- the telemetry it sends is redacted first (the tool answers are walked
  through the egress gate, and the assembled prompt is swept again);
- the request is audited - the provider, the size of the payload and the
  number of masks applied all land in `tool_call_audit`.

The provider is stubbed here, because a test must not need a key. What is
real is the gate, the redaction and the audit.

This used to cover a "Stage 2 narrative" layered on top of a rule engine.
There is no Stage 1 any more: the MCP runtime asks the tools, hands the
answers to the model and reconciles every number it cites. The tests below
cover that stage - the prose the model writes, the honest failure when it
cannot be reached, and the audit row the request leaves behind.
"""
import asyncio
import json
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import HealthMetric, ToolCallAudit
from mcp.agent import run_scan
from mcp.agent.runtime import SUBSECTION_TOOLS


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


def _healthy_health_metric(session) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(
        HealthMetric(ts=now, platform="web", response_time_p95_ms=120, http_5xx_pct=0.2)
    )
    session.commit()


def _honest_response(messages) -> dict:
    """The body an honest model returns: a number it was actually given."""
    payload = json.loads(messages[1]["content"])
    output = payload["tool_output"][0]
    value = None
    for value_ in (output.get("data") or {}).values():
        if isinstance(value_, (int, float)) and not isinstance(value_, bool):
            value = float(value_)
            break
    if value is None:
        value = 0.0
    return {
        "status": "healthy",
        "summary": "The measured signals are inside their thresholds for the window.",
        "findings": [
            {
                "title": "Measured signal within budget",
                "severity": "info",
                "evidence": [
                    {
                        "metric": output["metric_key"],
                        "value": value,
                        "unit": "count",
                        "window": "7d",
                        "source": output["tool"],
                    }
                ],
            }
        ],
        "root_causes": [],
        "recommended_actions": [],
        "confidence": {"level": "high"},
    }


def test_the_models_prose_is_kept_alongside_the_measured_facts(db_session):
    """The model writes the sentence; the tools own the numbers."""
    _healthy_health_metric(db_session)
    calls: list = []

    async def chat(messages):
        calls.append(messages)
        return _honest_response(messages)

    result = asyncio.run(
        run_scan(db_session, subsection="A_W_HEALTH", scan_id="scan-narrative-1", chat=chat)
    )

    assert "The measured signals are inside their thresholds" in result.summary
    assert result.status.value == "healthy"
    # The model was handed the tools' answers, not the raw rows.
    payload = json.loads(calls[0][1]["content"])
    assert payload["tool_output"]
    assert payload["tool_output"][0]["tool"] in {name for name, _ in SUBSECTION_TOOLS["A_W_HEALTH"]}


def test_a_model_that_cannot_be_reached_gives_an_honest_error(db_session, monkeypatch):
    """No key, no network, a refusal from the gate: the scan fails honestly.

    The failure is reported as an `error` verdict carrying the reason, not as
    a crashed request and not as a clean bill of health. An installation
    without a model should be visibly broken, not quietly reassuring.
    """
    _healthy_health_metric(db_session)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = asyncio.run(
        run_scan(db_session, subsection="A_W_HEALTH", scan_id="scan-narrative-2")
    )

    assert result.status.value == "error"
    assert "could not be completed" in result.summary
    assert result.findings == []
    assert result.confidence.level == "low"


def test_the_outbound_request_is_audited(db_session, monkeypatch):
    """The provider was called, and the request is on the record."""
    from mcp.core import llm as llm_mod

    _healthy_health_metric(db_session)

    class _StubClient:
        """A provider client that answers without a network."""

        def __init__(self) -> None:
            self.sent: list = []

        async def chat(self, messages, temperature=None, max_tokens=None, response_format=None):
            self.sent.append(messages)
            return type("R", (), {"text": json.dumps(_honest_response(messages))})()

    stub = _StubClient()
    monkeypatch.setattr(llm_mod, "get_client", lambda provider: stub)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    result = asyncio.run(
        run_scan(
            db_session,
            subsection="A_W_HEALTH",
            scan_id="scan-narrative-3",
            provider="openrouter",
        )
    )

    assert result.status.value == "healthy"
    assert stub.sent, "the request did not reach the provider"

    rows = db_session.exec(
        select(ToolCallAudit).where(ToolCallAudit.tool == llm_mod.AUDIT_TOOL)
    ).all()
    assert rows, "the outbound request was not audited"
    assert rows[0].sent_to == "openrouter"
    assert rows[0].bytes_out > 0
    assert rows[0].redaction_salt
