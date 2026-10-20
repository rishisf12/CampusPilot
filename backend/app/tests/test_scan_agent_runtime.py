"""Tests for the scan-agent runtime and the reconciler (Phase 5).

The contract under test:

1. **A cited number must come from a tool.** The reconciler checks every
   number a finding cites against the audit trail: a number no tool returned
   fails the scan, and so does a metric no tool ever fetched.
2. **A failed scan is `error`, never `healthy`.** The runtime retries once
   and then reports the failure with the reason, rather than storing a
   verdict nobody verified.
3. **An honest model gets its verdict through**, and the scan is stored.
4. **The runtime acts on nothing.** It reads and it writes audit rows and
   scan results; it never executes a recommendation.
"""
import json

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.api.schemas import ScanResult as ScanResultSchema
from features.monitoring.api.schemas import Status
from features.monitoring.domain.models import ScanResult as ScanResultRow
from features.monitoring.domain.models import StatusTransition, ToolCallAudit
from mcp.agent import reconcile, run_scan
from mcp.agent.reconcile import ReconcileError


@pytest.fixture
def db_session():
    with Session(engine) as session:
        for model in (ToolCallAudit, ScanResultRow, StatusTransition):
            session.exec(delete(model))
        session.commit()
        yield session
        for model in (ToolCallAudit, ScanResultRow, StatusTransition):
            session.exec(delete(model))
        session.commit()


def _first_number(data):
    """A number the tool actually returned (the honest fake cites this)."""
    if isinstance(data, dict):
        for value in data.values():
            found = _first_number(value)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _first_number(item)
            if found is not None:
                return found
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        return float(data)
    return None


def _honest_response(messages):
    """The body an honest model returns: a number it was actually given."""
    payload = json.loads(messages[1]["content"])
    output = payload["tool_output"][0]
    value = _first_number(output["data"])
    return {
        "status": "healthy",
        "summary": "Every measured signal is inside its threshold for the window.",
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


def _honest_chat(calls):
    """A model that cites a number it was actually given."""

    async def chat(messages):
        calls.append(messages)
        return _honest_response(messages)

    return chat


def _fabricating_chat(calls):
    """A model that cites a number no tool returned."""

    async def chat(messages):
        calls.append(messages)
        payload = json.loads(messages[1]["content"])
        output = payload["tool_output"][0]
        return {
            "status": "healthy",
            "summary": "Everything looks fine, according to the numbers below.",
            "findings": [
                {
                    "title": "Invented latency",
                    "severity": "info",
                    "evidence": [
                        {
                            "metric": output["metric_key"],
                            "value": 999999.0,
                            "unit": "ms",
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

    return chat


# --- the reconciler ----------------------------------------------------------


def test_reconcile_accepts_a_number_a_tool_returned(db_session):
    from mcp.core.registry import run_tool
    from mcp.monitoring import REGISTRY

    run_tool(
        db_session,
        REGISTRY,
        scan_id="scan-recon-ok",
        subsection="A_W_HEALTH",
        name="telemetry_health",
        args={"days": 7, "platform": "web"},
    )
    verdict = ScanResultSchema(
        scan_id="scan-recon-ok",
        subsection="A_W_HEALTH",
        status=Status.HEALTHY,
        summary="A verdict whose number came from the tool that ran.",
        findings=[
            {
                "title": "Latency within budget",
                "severity": "info",
                "evidence": [
                    {
                        "metric": "telemetry_health_7d_web",
                        "value": 0.0,
                        "unit": "ms",
                        "window": "7d",
                        "source": "telemetry_health",
                    }
                ],
            }
        ],
        confidence={"level": "high"},
    )
    assert reconcile(db_session, verdict, scan_id="scan-recon-ok") is verdict


def test_reconcile_catches_a_number_no_tool_returned(db_session):
    from mcp.core.registry import run_tool
    from mcp.monitoring import REGISTRY

    run_tool(
        db_session,
        REGISTRY,
        scan_id="scan-recon-bad",
        subsection="A_W_HEALTH",
        name="telemetry_health",
        args={"days": 7, "platform": "web"},
    )
    verdict = ScanResultSchema(
        scan_id="scan-recon-bad",
        subsection="A_W_HEALTH",
        status=Status.HEALTHY,
        summary="A verdict that cites a number nobody measured.",
        findings=[
            {
                "title": "Invented latency",
                "severity": "info",
                "evidence": [
                    {
                        "metric": "telemetry_health_7d_web",
                        "value": 999999.0,
                        "unit": "ms",
                        "window": "7d",
                        "source": "telemetry_health",
                    }
                ],
            }
        ],
        confidence={"level": "high"},
    )
    with pytest.raises(ReconcileError, match="the model said"):
        reconcile(db_session, verdict, scan_id="scan-recon-bad")


def test_reconcile_catches_a_metric_that_was_never_fetched(db_session):
    verdict = ScanResultSchema(
        scan_id="scan-recon-missing",
        subsection="A_W_HEALTH",
        status=Status.HEALTHY,
        summary="A verdict that cites a tool that never ran.",
        findings=[
            {
                "title": "Invented source",
                "severity": "info",
                "evidence": [
                    {
                        "metric": "a_tool_that_never_ran",
                        "value": 1.0,
                        "unit": "count",
                        "window": "7d",
                        "source": "ghost",
                    }
                ],
            }
        ],
        confidence={"level": "high"},
    )
    with pytest.raises(ReconcileError, match="never fetched"):
        reconcile(db_session, verdict, scan_id="scan-recon-missing")


def test_reconcile_catches_a_change_pct_that_does_not_match_its_endpoints(db_session):
    from mcp.core.registry import run_tool
    from mcp.monitoring import REGISTRY

    run_tool(
        db_session,
        REGISTRY,
        scan_id="scan-recon-change",
        subsection="A_W_HEALTH",
        name="telemetry_health",
        args={"days": 7, "platform": "web"},
    )
    verdict = ScanResultSchema(
        scan_id="scan-recon-change",
        subsection="A_W_HEALTH",
        status=Status.WARNING,
        summary="A verdict whose percentage change does not follow from its numbers.",
        findings=[
            {
                "title": "Change claimed",
                "severity": "warning",
                "evidence": [
                    {
                        "metric": "telemetry_health_7d_web",
                        "value": 0.0,
                        "previous_value": 100.0,
                        "change_pct": -42.0,
                        "unit": "ms",
                        "window": "7d",
                        "source": "telemetry_health",
                    }
                ],
            }
        ],
        confidence={"level": "high"},
    )
    with pytest.raises(ReconcileError, match="does not match its endpoints"):
        reconcile(db_session, verdict, scan_id="scan-recon-change")


# --- the runtime -------------------------------------------------------------


def test_runtime_returns_and_stores_an_honest_verdict(db_session):
    calls: list = []
    result = asyncio_run(
        run_scan(
            db_session,
            subsection="A_W_HEALTH",
            scan_id="scan-agent-ok",
            chat=_honest_chat(calls),
        )
    )
    assert result.status == Status.HEALTHY
    assert len(result.findings) == 1
    assert len(calls) == 1  # no retry needed

    stored = db_session.exec(select(ScanResultRow)).all()
    assert len(stored) == 1
    assert stored[0].status == "healthy"
    assert stored[0].scan_id == "scan-agent-ok"


def test_runtime_stores_error_not_healthy_when_the_model_fabricates(db_session):
    calls: list = []
    result = asyncio_run(
        run_scan(
            db_session,
            subsection="A_W_HEALTH",
            scan_id="scan-agent-liar",
            chat=_fabricating_chat(calls),
        )
    )
    # Retried once, then failed honestly.
    assert len(calls) == 2
    assert result.status == Status.ERROR
    assert result.findings == []
    assert result.confidence.level == "low"
    assert "the model said" in result.summary

    stored = db_session.exec(select(ScanResultRow)).all()
    assert len(stored) == 1
    assert stored[0].status == "error"


def test_runtime_retries_once_and_accepts_the_second_answer(db_session):
    calls: list = []

    async def flaky(messages):
        calls.append(messages)
        if len(calls) == 1:
            return "not json at all"
        return _honest_response(messages)

    result = asyncio_run(
        run_scan(
            db_session,
            subsection="A_W_HEALTH",
            scan_id="scan-agent-retry",
            chat=flaky,
        )
    )
    assert len(calls) == 2
    assert result.status == Status.HEALTHY
    assert result.findings


def test_runtime_writes_audit_rows_for_every_tool_it_ran(db_session):
    calls: list = []
    asyncio_run(
        run_scan(
            db_session,
            subsection="C_W_SECURITY",
            scan_id="scan-agent-audit",
            chat=_honest_chat(calls),
        )
    )
    rows = db_session.exec(select(ToolCallAudit)).all()
    tools = {row.tool for row in rows}
    assert "security_signals" in tools
    assert "failed_logins_by_hour" in tools
    assert all(row.scan_id == "scan-agent-audit" for row in rows)


def test_runtime_turns_recommendations_into_proposals_not_actions(db_session):
    """The reactor records the suggestion; nothing acts on it."""
    from features.monitoring.domain.models import ReactorProposal

    async def recommending(messages):
        payload = json.loads(messages[1]["content"])
        output = payload["tool_output"][0]
        value = _first_number(output["data"])
        return {
            "status": "warning",
            "summary": "One endpoint is slower than the healthy band allows.",
            "findings": [
                {
                    "title": "Slow endpoint",
                    "severity": "warning",
                    "evidence": [
                        {
                            "metric": output["metric_key"],
                            "value": value,
                            "unit": "ms",
                            "window": "7d",
                            "source": output["tool"],
                        }
                    ],
                }
            ],
            "root_causes": ["The feedback endpoint runs an unbounded query."],
            "recommended_actions": [
                {
                    "action": "investigate_endpoint",
                    "priority": 1,
                    "detail": "p95 is 900 ms on /api/feedback",
                    "evidence_refs": ["/api/feedback"],
                }
            ],
            "confidence": {"level": "medium"},
        }

    result = asyncio_run(
        run_scan(
            db_session,
            subsection="A_W_HEALTH",
            scan_id="scan-agent-proposal",
            chat=recommending,
        )
    )
    assert result.status == Status.WARNING

    proposals = db_session.exec(select(ReactorProposal)).all()
    assert len(proposals) == 1
    assert proposals[0].action == "investigate_endpoint"
    assert proposals[0].state == "proposed"
    # Advisory: the procedure tells a human what to do, and it does not do it.
    assert proposals[0].procedure["requires_operator"] is True
    assert proposals[0].procedure["steps"]


def asyncio_run(coro):
    """`asyncio.run` without an event loop of our own."""
    import asyncio

    return asyncio.run(coro)
