"""Tests for the MCP core contract (Phase 1 of docs/MCP_MIGRATION_PLAN.md).

What the tests are defending:

1. **Refusals leave a trail.** Every refused, timed-out or crashed tool call
   writes a `ok=False` audit row — so "nothing happened" is verifiable, and a
   tool cannot fail silently.
2. **Subsection scoping is server-side.** A scan may not conjure another
   subsection's tool; the registry refuses before the callable runs.
3. **Read-only + credential rules.** The SQL guard refuses writes and
   credential-adjacent tables before any string reaches the engine.
4. **The LLM router stays free.** A paid provider name is refused even when a
   key for it sits in the environment.
"""
import time

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import ToolCallAudit
from mcp.core import queries, registry
from mcp.core.registry import (
    ToolNotPermitted,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    ToolTimeout,
    run_tool,
)
from llms import LLMConfigError, resolve


@pytest.fixture
def db_session():
    """A session with `telemetry.tool_call_audit` emptied first."""
    with Session(engine) as session:
        session.exec(delete(ToolCallAudit))
        session.commit()
        yield session
        session.exec(delete(ToolCallAudit))
        session.commit()


@pytest.fixture
def reg() -> ToolRegistry:
    r = ToolRegistry()
    r.register(
        ToolSpec(name="count_slots", subsections=frozenset({"A_W_HEALTH", "C_W_SECURITY"})),
        lambda session, **kwargs: ToolResult(data=[1, 2, 3], row_count=3, metric_key="slot_count"),
    )
    r.register(
        ToolSpec(name="slow_tool", subsections=frozenset({registry.SUBSECTIONS[0]})),
        lambda session: (time.sleep(2), ToolResult(data=None))[1],
    )
    return r


def _audit_rows(session) -> list[ToolCallAudit]:
    return session.exec(select(ToolCallAudit)).all()


def test_permitted_call_is_audited(db_session, reg):
    result = run_tool(
        db_session,
        reg,
        scan_id="scan-test-1",
        subsection="A_W_HEALTH",
        name="count_slots",
    )
    assert result.data == [1, 2, 3]
    rows = _audit_rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.ok is True
    assert row.scan_id == "scan-test-1"
    assert row.tool == "count_slots"
    assert row.metric_key == "slot_count"
    assert row.row_count == 3
    assert row.duration_ms >= 0


def test_wrong_subsection_refused_but_audited(db_session, reg):
    with pytest.raises(ToolNotPermitted, match="not permitted for subsection"):
        run_tool(
            db_session,
            reg,
            scan_id="scan-test-2",
            subsection="D_W_FEEDBACK",
            name="count_slots",
        )
    row = _audit_rows(db_session)[0]
    assert row.ok is False
    assert row.error is not None
    assert "not permitted" in row.error


def test_timeout_refused_but_audited(db_session, reg):
    with pytest.raises(ToolTimeout):
        run_tool(
            db_session,
            reg,
            subsection="A_W_HEALTH",
            name="slow_tool",
            timeout_s=0.2,
        )
    row = _audit_rows(db_session)[0]
    assert row.ok is False
    assert "exceeded" in (row.error or "")


def test_unregistered_tool_refused_but_audited(db_session, reg):
    with pytest.raises(ToolNotPermitted, match="not registered"):
        run_tool(db_session, reg, subsection="A_W_HEALTH", name="ghost_tool")
    assert len(_audit_rows(db_session)) == 1


def test_row_cap_enforced():
    with pytest.raises(registry.ToolError, match="exceeds cap"):
        ToolResult(data=None, row_count=registry.ROW_CAP + 1)


def test_oversized_sql_refused():
    oversized = "select " + "a" * queries.MAX_SQL_LENGTH
    with pytest.raises(ToolNotPermitted, match="exceeds"):
        queries.assert_read_query(oversized)


def test_multi_statement_sql_refused():
    with pytest.raises(ToolNotPermitted, match="one statement"):
        queries.assert_read_query("select 1; select 2")
    # Even inside a literal: strictness beats cleverness for the tools we own.
    with pytest.raises(ToolNotPermitted, match="one statement"):
        queries.assert_read_query("select 'x;y' from event")


def test_server_side_executors_refused():
    for kw in ("copy event to '/tmp/x'", "call refresh_stats()", "do $$ begin end $$", "lock table event"):
        with pytest.raises(ToolNotPermitted, match="write keyword"):
            queries.assert_read_query(kw)


def test_timeout_does_not_hold_the_worker(db_session, reg):
    """A wedged tool must cost the worker its budget, not its runtime."""
    started = time.monotonic()
    with pytest.raises(ToolTimeout):
        run_tool(db_session, reg, subsection="A_W_HEALTH", name="slow_tool", timeout_s=0.2)
    elapsed = time.monotonic() - started
    assert elapsed < 1.5  # the 2s tool may drain in the background; the worker moved on
    row = _audit_rows(db_session)[0]
    assert row.ok is False
    assert "exceeded" in (row.error or "")


def test_audit_survives_unserializable_args(db_session, reg):
    """A non-JSON arg (datetime) must not crash the mandatory audit trail."""
    from datetime import datetime, timezone

    result = run_tool(
        db_session,
        reg,
        subsection="A_W_HEALTH",
        name="count_slots",
        args={"requested_at": datetime.now(timezone.utc)},
    )
    assert result.data == [1, 2, 3]
    row = _audit_rows(db_session)[0]
    assert row.ok is True
    assert isinstance(row.args, dict)
    assert row.args["requested_at"]  # reduced, but recorded


def test_registry_lists_names_for_the_endpoint(reg):
    names = reg.names()
    assert names == sorted(names)
    assert "count_slots" in names and "slow_tool" in names


def test_write_sql_refused():
    with pytest.raises(ToolNotPermitted, match="write keyword"):
        queries.assert_read_query("DELETE FROM event")
    with pytest.raises(ToolNotPermitted, match="one statement"):
        queries.assert_read_query("select 1; update event set n=1")
    with pytest.raises(ToolNotPermitted, match="protected table fragment"):
        queries.assert_read_query("select * from auth_user")
    with pytest.raises(ToolNotPermitted, match="protected table fragment"):
        queries.assert_read_query("select secret from refresh_token")


def test_read_sql_passes(db_session):
    assert queries.assert_read_query(
        "select course_code from timetable_slot where semester = 3"
    )
    assert queries.assert_read_query("select count(*) from event")


def test_llm_router_refuses_paid_providers(monkeypatch):
    # Even a working key for the paid provider must not make it usable.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-looks-legal")
    with pytest.raises(LLMConfigError, match="not on the free allowlist"):
        resolve("openai")


def test_llm_router_resolves_free_provider(monkeypatch):
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    resolved = resolve(model="meta/test-model")
    assert resolved.provider == "nvidia_nim"
    assert resolved.base_url == "https://integrate.api.nvidia.com/v1"
    assert resolved.api_key == "nvapi-test"
    assert resolved.model == "meta/test-model"


def test_llm_router_no_provider_configured(monkeypatch):
    for var in ("NVIDIA_NIM_API_KEY", "OPENROUTER_API_KEY", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(LLMConfigError, match="no free LLM provider"):
        resolve()
