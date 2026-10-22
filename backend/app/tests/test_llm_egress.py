"""The egress contract: provider routing, job-kind gating, LLM egress auditing.

The rules under test (docs/MCP_MIGRATION_PLAN.md, Phase 4):

1. The free allowlist is the whole universe: a named provider outside
   {nvidia_nim, openrouter} is refused at resolve time, key or not.
2. Job kinds: telemetry work refuses to start when the egress gate is not
   verified inside `run_tool`; public_data resolves freely.
3. A telemetry job that fails the gate sends nothing - not a request, and
   not an audit row claiming one went out.
4. Every outbound telemetry LLM request writes one audited row with
   sent_to / redactions_applied / bytes_out / redaction_salt - and, most
   importantly, the planted-PII test proves raw rows never reach the model.

The send site under test is `mcp.core.llm.chat`, the one outbound path from
this backend to a model. The legacy Stage 2 client that this file used to
cover is gone: the MCP runtime replaced it, and the gate now lives in one
place instead of two.
"""
import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import ToolCallAudit
from llms import ALLOWED_PROVIDERS, LLMConfigError, resolve, resolve_for_job
from mcp.core.jobs import JobRefused
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


# 3. The send site refuses without building a request ----------------------------


class _NeverClient:
    """If the refusal path is correct, this class is never constructed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("LLM client constructed despite a refused job")


def test_a_refused_provider_never_builds_a_request(monkeypatch, db_session):
    """A provider off the allowlist is refused before a client exists.

    The order matters: the gate runs first, so nothing is built, nothing is
    sent, and no audit row claims a request went out.
    """
    from mcp.core import llm as llm_mod

    monkeypatch.setattr(llm_mod, "get_client", lambda provider: _NeverClient())

    with pytest.raises(JobRefused, match="allowlist"):
        asyncio.run(
            llm_mod.chat(
                db_session,
                job_kind="telemetry",
                provider="groq",
                messages=[{"role": "user", "content": "hello"}],
                scan_id="scan-refused-test",
            )
        )

    rows = db_session.exec(select(ToolCallAudit)).all()
    assert not [r for r in rows if (r.tool or "").startswith("llm.")]


# 4. The send site: egress + audit ----------------------------------------------


class _CapturingClient:
    """Stands in for the provider client; captures what would hit the wire."""

    captured: dict[str, Any] = {}

    def __init__(self) -> None:
        _CapturingClient.captured = {}

    async def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        _CapturingClient.captured["messages"] = messages
        _CapturingClient.captured["temperature"] = temperature
        _CapturingClient.captured["max_tokens"] = max_tokens
        return SimpleNamespace(text='{"summary": "ok"}')


def test_planted_pii_never_reaches_the_llm_request(monkeypatch, db_session):
    """The second lock: the prompt is redacted again before it is sent.

    The tool answers were already redacted on the way out of the registry;
    this is the second pass, on the assembled prompt. Two locks on the same
    door, because the context can contain a student's email.
    """
    planted = {
        "email": "hari.student@campus.edu",
        "phone": "+91 99887 76655",
        "ip": "192.168.4.12",
        "card": "5555 5555 5555 4444",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJsZWFrIn0.cGxhbnRlZF9zdHJpbmdfZm9yX3Rlc3Q",
    }
    body = (
        f"Ping {planted['email']} or call {planted['phone']} - "
        f"from {planted['ip']}, card {planted['card']}, token {planted['jwt']}"
    )

    from mcp.core import llm as llm_mod

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    _ = salt_for("scan-llm-egress-test")  # mint the run's salt before the call

    asyncio.run(
        llm_mod.chat(
            db_session,
            job_kind="telemetry",
            provider="openrouter",
            messages=[{"role": "user", "content": body}],
            scan_id="scan-llm-egress-test",
            client=_CapturingClient(),
        )
    )

    wire = " ".join(
        str(m.get("content", "")) for m in _CapturingClient.captured["messages"]
    )
    for secret in planted.values():
        assert str(secret) not in wire, secret
    for placeholder in ("[email]", "[phone]", "[ip]", "[card]", "[jwt]"):
        assert placeholder in wire

    # The egress audit row: sent_to, redactions, bytes, salt.
    rows = db_session.exec(
        select(ToolCallAudit).where(ToolCallAudit.tool == llm_mod.AUDIT_TOOL)
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.ok is True
    assert row.sent_to == "openrouter"
    assert row.redactions_applied and row.redactions_applied > 0
    assert row.bytes_out and row.bytes_out > 0
    assert row.redaction_salt == salt_for("scan-llm-egress-test")
