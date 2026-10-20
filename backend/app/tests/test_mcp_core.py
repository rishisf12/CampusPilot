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


# --- Phase 3: the egress gate ------------------------------------------------


def test_redact_masks_each_pii_shape():
    from mcp.core.redact import CARD_MASK, EMAIL_MASK, IP_MASK, JWT_MASK, PHONE_MASK, redact

    cases = [
        ("write to dean.office@campus.edu.in today", EMAIL_MASK),
        ("Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnX3RalG9rZW5fdmFsdWU", JWT_MASK),
        ("paid via 4111 1111 1111 1111 thanks", CARD_MASK),
        ("connect from 10.24.9.173 failed", IP_MASK),
        ("call +91 98765 43210 or 080-2345-6789", "[phone] or [phone]"),
        # Case/unicode/locale edges
        ("A.B+filter@X-II.co.uk", EMAIL_MASK),
        # Non-PII passthrough: versions, dates-ish words, plain text
        ("v1.2.3 released", None),  # unchanged
        ("no digits here", None),
        ("", None),
    ]
    for text, placeholder in cases:
        out = redact(text)
        if placeholder is None:
            assert out == text, text
        else:
            assert placeholder in out, text

    # A Luhn-failing 16-digit run survives the card check but is still caught
    # by the phone catch-all - strictness over cleverness.
    assert "1234567890123456" not in redact("id 1234567890123456")
    # An invalid-octet IP-shaped string is also caught by the catch-all.
    assert "999.12.1.1" not in redact("host 999.12.1.1")


def test_pseudonymize_id_salt_binds_stability():
    from mcp.core.redact import ID_PREFIX, pseudonymize_id

    same_run = pseudonymize_id(981274, "salt-a") == pseudonymize_id("981274", "salt-a")
    assert same_run  # int/str canonicalization identical
    other_salt = pseudonymize_id(981274, "salt-b")
    assert pseudonymize_id(981274, "salt-a") != other_salt
    token = pseudonymize_id(981274, "salt-a")
    assert token.startswith(ID_PREFIX) and len(token) == len(ID_PREFIX) + 8


def test_redact_value_blanks_secrets_and_pseudonymizes_ids():
    from mcp.core.redact import ID_PREFIX, SECRET_MASK, pseudonymize_id, redact_value

    row = {
        "user_id": 42,
        "student_id": [101, 102],
        "password_hash": "$2b$12$whatever",
        "secret": "hunter2",
        "note": "email a@b.edu from 1.2.3.4",
        "count": 7,
        "flag": True,
        "empty": None,
    }
    data, count = redact_value(row, "s1")
    assert data["password_hash"] == SECRET_MASK
    assert data["secret"] == SECRET_MASK
    assert data["user_id"].startswith(ID_PREFIX)
    assert data["student_id"] == [
        pseudonymize_id(101, "s1"),
        pseudonymize_id(102, "s1"),
    ]
    assert "[email]" in data["note"] and "[ip]" in data["note"]
    assert data["count"] == 7 and data["flag"] is True and data["empty"] is None
    assert count > 0
    # Input not mutated: the raw row still holds its secrets.
    assert row["password_hash"] == "$2b$12$whatever"


def test_egress_metadata_lands_in_audit(db_session, reg):
    run_tool(db_session, reg, scan_id="scan-egress", subsection="A_W_HEALTH", name="count_slots")
    row = _audit_rows(db_session)[0]
    meta = row.args["egress"]
    assert meta["redactions"] == 0
    assert meta["truncated"] is False
    assert len(meta["salt"]) == 32


def test_egress_row_cap_50(db_session, reg):
    reg.register(
        ToolSpec(name="flooder", subsections=frozenset({"A_W_HEALTH"})),
        lambda session: ToolResult(
            data=[{"n": i, "user_id": i} for i in range(120)],
            row_count=120,
            metric_key="flood",
        ),
    )
    out = run_tool(db_session, reg, scan_id="scan-flood", subsection="A_W_HEALTH", name="flooder")
    assert len(out.data) == registry.EGRESS_ROW_CAP == 50
    row = _audit_rows(db_session)[0]
    assert row.row_count == 120  # the tool's own count, for reconciliation
    assert row.args["egress"]["truncated"] is True


def test_planted_pii_never_leaves_through_run_tool(db_session, reg):
    """The egress gate's headline guarantee, end to end.

    Planted PII rows are read back through the real read path (SQL guard +
    session + registry) and nothing raw may appear in what `run_tool` returns.
    """
    from sqlalchemy import text as sql

    planted = {
        "email": "student.confidential@campus.edu",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwbGFudCJ9.c2hvdWxkX25ldmVyX2xlYXZlX2RlYXI",
        "phone": "+91 98765 43210",
        "ip": "10.24.9.173",
        "card": "4111 1111 1111 1111",
        "hash": "$2b$12$plantedbcrypthashplantedbcrypthashxx",
        "user_id": 981274,
    }
    note = (
        f"Contact {planted['email']} or {planted['phone']}, from {planted['ip']}, "
        f"card {planted['card']}, bearer {planted['jwt']}"
    )
    db_session.exec(
        sql(
            "create table planted_pii (id int primary key, user_id bigint, "
            "note text, password_hash text)"
        )
    )
    try:
        db_session.exec(
            sql(
                "insert into planted_pii values "
                f"(1, {planted['user_id']}, '{note}', '{planted['hash']}'), "
                f"(2, {planted['user_id']}, 'second complaint', NULL), "
                "(3, 550011, 'third complainant', NULL)"
            )
        )
        db_session.commit()

        def leaky_tool(session):
            rows = session.exec(
                sql("select id, user_id, note, password_hash from planted_pii order by id")
            ).mappings().all()
            return ToolResult(
                data=[dict(r) for r in rows], row_count=len(rows), metric_key="leak"
            )

        reg.register(
            ToolSpec(name="leaky_tool", subsections=frozenset({"A_W_HEALTH"})), leaky_tool
        )
        first = run_tool(
            db_session, reg, scan_id="scan-pii-a", subsection="A_W_HEALTH", name="leaky_tool"
        )
        blob = repr(first.data)

        # 1. Nothing planted survives - not raw, not as a substring.
        for secret in planted.values():
            assert str(secret) not in blob

        # 2. The masks did fire.
        for placeholder in ("[email]", "[jwt]", "[phone]", "[ip]", "[card]", "[masked]"):
            assert placeholder in blob

        # 3. Recurrences countable within the run: two rows share user_id 981274,
        #    so exactly two distinct pseudonyms across three rows.
        tokens = {row["user_id"] for row in first.data}
        assert len(tokens) == 2
        assert all(t.startswith("USER_") for t in tokens)
        assert first.data[0]["user_id"] == first.data[1]["user_id"]

        # 4. Same scan_id -> same salt -> same pseudonyms on the next tool call.
        second = run_tool(
            db_session, reg, scan_id="scan-pii-a", subsection="A_W_HEALTH", name="leaky_tool"
        )
        assert second.data[0]["user_id"] == first.data[0]["user_id"]

        # 5. A different scan run is unlinkable (fresh salt).
        third = run_tool(
            db_session, reg, scan_id="scan-pii-b", subsection="A_W_HEALTH", name="leaky_tool"
        )
        assert third.data[0]["user_id"] != first.data[0]["user_id"]

        # 6. The audit row carries the egress record.
        audits = [r for r in _audit_rows(db_session) if r.ok]
        assert audits[0].args["egress"]["redactions"] > 0
        assert audits[0].args["egress"]["salt"]
    finally:
        db_session.exec(sql("drop table planted_pii"))
        db_session.commit()



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
