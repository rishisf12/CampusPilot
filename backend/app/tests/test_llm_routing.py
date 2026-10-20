"""Tests for the LLM routing, job-kind gating and egress auditing (Phase 4).

What these defend:

1. **Free only.** A paid provider is refused at four levels - the allowlist
   resolver, the client factory, the job gate and the settings validator -
   even when a working key for it sits in the environment.
2. **One credential.** `NVIDIA_API_KEY` and `NVIDIA_NIM_API_KEY` are the same
   key; either one configures the reused client and the resolver.
3. **A telemetry job with a broken egress gate sends nothing.** The refusal
   happens before a client is built, so there is no request to be audited
   because there was no request.
4. **Every outbound request leaves a row** with the provider it went to, the
   size of the payload, how much was masked, and the run's salt.
"""
import asyncio

import pytest
from pydantic import ValidationError
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import ToolCallAudit
from llms import ALLOWED_PROVIDERS, LLMConfigError, get_client, resolve
from mcp.core import llm as llm_gateway
from mcp.core.jobs import JOB_KINDS, JobRefused, validate_job


@pytest.fixture
def db_session():
    with Session(engine) as session:
        session.exec(delete(ToolCallAudit))
        session.commit()
        yield session
        session.exec(delete(ToolCallAudit))
        session.commit()


class _FakeClient:
    """A provider client that records what it was asked to send."""

    name = "nvidia_nim"

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent: list = []
        self.default_model = "fake-model"

    async def chat(self, messages, temperature=0.1, max_tokens=4096, response_format=None):
        self.sent.append(messages)
        if self.fail:
            raise RuntimeError("provider is down")
        return type("R", (), {"text": "ok", "provider": self.name, "model": "fake-model"})()


# --- the allowlist -----------------------------------------------------------


def test_allowlist_refuses_a_paid_provider_even_with_a_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-allowed")
    with pytest.raises(LLMConfigError, match="free allowlist"):
        resolve("openai")
    with pytest.raises(LLMConfigError, match="free allowlist"):
        get_client("openai")
    assert set(ALLOWED_PROVIDERS) == {"nvidia_nim", "openrouter"}


def test_off_is_a_valid_no_llm_configuration():
    with pytest.raises(LLMConfigError, match="disabled"):
        resolve("off")


def test_settings_reject_a_non_allowlisted_provider():
    from core.config import Settings

    assert Settings(LLM_PROVIDER="off").llm_provider == "off"
    assert Settings(LLM_PROVIDER="nvidia_nim").llm_provider == "nvidia_nim"
    with pytest.raises(ValidationError, match="not permitted"):
        Settings(LLM_PROVIDER="openai")


def test_nvidia_key_is_accepted_under_either_name(monkeypatch):
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nim-alias-key")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert resolve("nvidia_nim").api_key == "nim-alias-key"

    monkeypatch.setenv("NVIDIA_API_KEY", "canonical-key")
    assert resolve("nvidia_nim").api_key == "canonical-key"

    # The reused client reads the same two names.
    client = get_client("nvidia_nim")
    assert client is not None


# --- the job gate ------------------------------------------------------------


def test_job_gate_refuses_unknown_kind_and_provider(db_session):
    salt = "s"
    with pytest.raises(JobRefused, match="job kind"):
        validate_job(
            job_kind="marketing",
            provider="nvidia_nim",
            scan_id="scan-x",
            salt=salt,
            session=db_session,
        )
    with pytest.raises(JobRefused, match="free allowlist"):
        validate_job(
            job_kind="telemetry",
            provider="openai",
            scan_id="scan-x",
            salt=salt,
            session=db_session,
        )


def test_telemetry_job_refuses_when_the_egress_gate_is_unwired(db_session, monkeypatch):
    """The refusal happens before a client exists - so nothing is sent."""
    monkeypatch.setattr("mcp.core.jobs.egress_selfcheck", lambda *a, **k: False)

    client = _FakeClient()
    with pytest.raises(JobRefused, match="egress gate"):
        asyncio.run(
            llm_gateway.chat(
                db_session,
                job_kind="telemetry",
                provider="nvidia_nim",
                messages=[{"role": "user", "content": "hello"}],
                scan_id="scan-unwired",
                client=client,
            )
        )
    assert client.sent == []  # no request was attempted
    rows = db_session.exec(select(ToolCallAudit)).all()
    assert [r for r in rows if r.tool == llm_gateway.AUDIT_TOOL] == []


def test_public_data_job_does_not_need_the_egress_selfcheck(db_session, monkeypatch):
    monkeypatch.setattr("mcp.core.jobs.egress_selfcheck", lambda *a, **k: False)
    ctx = validate_job(
        job_kind="public_data",
        provider="nvidia_nim",
        scan_id="scan-public",
        salt="s",
        session=db_session,
    )
    assert ctx.job_kind in JOB_KINDS


# --- the outbound path -------------------------------------------------------


def test_outbound_request_is_audited_and_carries_no_raw_pii(db_session):
    client = _FakeClient()
    planted = "student.confidential@campus.edu"
    response = asyncio.run(
        llm_gateway.chat(
            db_session,
            job_kind="telemetry",
            provider="nvidia_nim",
            messages=[{"role": "user", "content": f"complaint from {planted}"}],
            scan_id="scan-audit",
            client=client,
        )
    )
    assert response.text == "ok"

    # 1. The provider saw a masked prompt.
    sent = repr(client.sent)
    assert planted not in sent
    assert "[email]" in sent

    # 2. The request left a row.
    rows = db_session.exec(select(ToolCallAudit)).all()
    outbound = [r for r in rows if r.tool == llm_gateway.AUDIT_TOOL]
    assert len(outbound) == 1
    row = outbound[0]
    assert row.ok is True
    assert row.sent_to == "nvidia_nim"
    assert row.bytes_out > 0
    assert row.redactions_applied >= 1
    assert row.redaction_salt
    assert row.scan_id == "scan-audit"


def test_failover_audits_the_failed_attempt_too(db_session):
    failing = _FakeClient(fail=True)
    with pytest.raises(llm_gateway.LLMRequestError):
        asyncio.run(
            llm_gateway.chat(
                db_session,
                job_kind="public_data",
                provider="nvidia_nim",
                messages=[{"role": "user", "content": "hi"}],
                scan_id="scan-failover",
                client=failing,
            )
        )
    rows = db_session.exec(select(ToolCallAudit)).all()
    outbound = [r for r in rows if r.tool == llm_gateway.AUDIT_TOOL]
    # One row per outbound attempt: the named provider, then the fallback.
    assert len(outbound) == 2
    assert all(r.ok is False for r in outbound)
    assert {r.sent_to for r in outbound} == {"nvidia_nim", "openrouter"}
    assert all(r.bytes_out > 0 for r in outbound)  # the payload was measured too


def test_two_runs_are_unlinkable_across_salts(db_session):
    client = _FakeClient()
    for scan_id in ("scan-run-1", "scan-run-2"):
        asyncio.run(
            llm_gateway.chat(
                db_session,
                job_kind="telemetry",
                provider="nvidia_nim",
                messages=[{"role": "user", "content": "user_id 42"}],
                scan_id=scan_id,
                client=client,
            )
        )
    salts = {
        r.redaction_salt
        for r in db_session.exec(select(ToolCallAudit)).all()
        if r.tool == llm_gateway.AUDIT_TOOL
    }
    assert len(salts) == 2  # one salt per run, never shared
