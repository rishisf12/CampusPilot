"""Tests for the Phase 5 aggregate tools.

These tools are the scan agent's question layer, so the tests defend three
things:

1. **Counts, not rows.** Every tool answers with aggregates; none of them
   returns a message body, a stack trace, an IP or a session id. The
   planted-PII test proves it with data in the database, not with a promise
   in a docstring.
2. **Scoped.** A scan may not call another subsection's tool, and the tools
   refuse nonsense windows instead of answering with an empty result that
   reads like "no data yet".
3. **Audited.** Every call writes its audit row, exactly like the Phase 2
   tools do.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import (
    CrashReport,
    DependencyVulnerability,
    FeedbackAnalysis,
    HealthMetric,
    SecurityEvent,
    SecurityEventKind,
    SecurityLog,
    SlowEndpoint,
    ToolCallAudit,
)
from mcp.core.registry import ToolError, ToolNotPermitted, run_tool
from mcp.monitoring import REGISTRY


@pytest.fixture
def db_session():
    with Session(engine) as session:
        for model in (
            CrashReport,
            DependencyVulnerability,
            FeedbackAnalysis,
            HealthMetric,
            SecurityEvent,
            SecurityLog,
            SlowEndpoint,
            ToolCallAudit,
        ):
            session.exec(delete(model))
        session.commit()
        yield session
        for model in (
            CrashReport,
            DependencyVulnerability,
            FeedbackAnalysis,
            HealthMetric,
            SecurityEvent,
            SecurityLog,
            SlowEndpoint,
            ToolCallAudit,
        ):
            session.exec(delete(model))
        session.commit()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _run(session, name, subsection, **args):
    return run_tool(session, REGISTRY, subsection=subsection, name=name, args=args)


# --- the tools exist and are scoped ------------------------------------------


def test_all_six_aggregates_are_registered_and_scoped():
    names = REGISTRY.names()
    for name in (
        "failed_logins_by_hour",
        "feedback_themes_top5",
        "p95_latency_window",
        "crash_clusters",
        "telemetry_health",
        "security_signals",
    ):
        assert name in names
    # Scoping is server-side: a scan may not conjure another subsection's tool.
    with pytest.raises(ToolNotPermitted):
        REGISTRY.permitted("failed_logins_by_hour", "A_W_HEALTH")
    with pytest.raises(ToolNotPermitted):
        REGISTRY.permitted("feedback_themes_top5", "C_W_SECURITY")
    assert REGISTRY.permitted("security_signals", "C_W_SECURITY")
    assert REGISTRY.permitted("crash_clusters", "A_A_HEALTH")


def test_nonsense_windows_are_refused_not_answered(db_session):
    with pytest.raises(ToolError, match="hours"):
        _run(db_session, "failed_logins_by_hour", "C_W_SECURITY", hours=0)
    with pytest.raises(ToolError, match="hours"):
        _run(db_session, "failed_logins_by_hour", "C_W_SECURITY", hours=10_000)
    with pytest.raises(ToolError, match="platform"):
        _run(db_session, "crash_clusters", "A_A_HEALTH", platform="toaster")
    with pytest.raises(ToolError, match="max_n"):
        _run(db_session, "crash_clusters", "A_A_HEALTH", max_n=0)


# --- the answers -------------------------------------------------------------


def test_failed_logins_by_hour_counts_without_naming(db_session):
    now = _now()
    for i in range(3):
        db_session.add(
            SecurityEvent(
                ts=now - timedelta(hours=1),
                platform="web",
                kind=SecurityEventKind.FAILED_LOGIN,
                ip_hash="ip-abc",
                user_hash="user-1",
            )
        )
    db_session.add(
        SecurityEvent(
            ts=now - timedelta(hours=1),
            platform="web",
            kind=SecurityEventKind.BRUTE_FORCE,
            ip_hash="ip-abc",
        )
    )
    db_session.commit()

    out = _run(db_session, "failed_logins_by_hour", "C_W_SECURITY", hours=24)
    data = out.data
    assert len(data) == 1
    assert data[0]["failed_logins"] == 3
    assert data[0]["distinct_sources"] == 1
    # The hash values themselves never leave the tool.
    assert "ip-abc" not in repr(data)
    assert "user-1" not in repr(data)

    audits = db_session.exec(select(ToolCallAudit)).all()
    assert len(audits) == 1
    assert audits[0].ok is True
    assert audits[0].metric_key.startswith("failed_logins_by_hour")


def test_feedback_themes_returns_labels_and_counts_only(db_session):
    now = _now()
    db_session.add(
        FeedbackAnalysis(
            ts=now,
            window_start=now - timedelta(days=1),
            window_end=now,
            total_count=10,
            sentiment_positive=4,
            sentiment_neutral=4,
            sentiment_negative=2,
            sentiment_mean=0.2,
            topics=[
                {"topic": "timetable", "count": 6, "pct": 60.0},
                {"topic": "exams", "count": 3, "pct": 30.0},
            ],
            top_complaints=[
                {"message": "my email is a.b@campus.edu and my phone is +91 98765 43210", "count": 2}
            ],
        )
    )
    db_session.commit()

    out = _run(db_session, "feedback_themes_top5", "D_W_FEEDBACK", days=7)
    blob = repr(out.data)
    assert out.data["topics"][0] == {"topic": "timetable", "count": 6}
    assert out.data["sentiment"]["positive"] == 4
    assert out.data["sentiment"]["mean"] == 0.2
    # The complaint body (and the PII inside it) never comes back.
    assert "a.b@campus.edu" not in blob
    assert "98765 43210" not in blob
    assert "top_complaints" not in blob


def test_crash_clusters_never_returns_messages_or_stacks(db_session):
    now = _now()
    for _ in range(3):
        db_session.add(
            CrashReport(
                ts=now,
                platform="android",
                kind="crash",
                session_id="sess-1",
                fingerprint="fp-1",
                exception_type="NullPointerException",
                message="user@example.edu crashed",
                stack_trace="at com.campus.Foo.bar(Foo.kt:42) user@example.edu",
                app_version="1.2.3",
            )
        )
    db_session.add(
        CrashReport(
            ts=now,
            platform="android",
            kind="crash",
            session_id="sess-2",
            fingerprint="fp-2",
            exception_type="IllegalStateException",
            app_version="1.2.4",
        )
    )
    db_session.commit()

    out = _run(db_session, "crash_clusters", "A_A_HEALTH", days=7, platform="android")
    blob = repr(out.data)
    assert out.data[0]["fingerprint"] == "fp-1"
    assert out.data[0]["count"] == 3
    assert out.data[0]["app_versions"] == ["1.2.3"]
    assert out.data[0]["exception_type"] == "NullPointerException"
    # Nothing that can carry user data.
    assert "user@example.edu" not in blob
    assert "Foo.kt" not in blob
    assert "sess-1" not in blob
    assert "message" not in blob
    assert "stack_trace" not in blob


def test_p95_latency_window_lists_slow_endpoints(db_session):
    now = _now()
    db_session.add(
        SlowEndpoint(
            ts=now,
            platform="web",
            endpoint="/api/feedback",
            method="POST",
            p50_ms=100,
            p95_ms=900,
            p99_ms=1200,
            request_count=40,
            error_count=2,
        )
    )
    db_session.add(
        SlowEndpoint(
            ts=now,
            platform="web",
            endpoint="/api/timetable",
            p50_ms=10,
            p95_ms=50,
            request_count=400,
        )
    )
    db_session.commit()

    out = _run(db_session, "p95_latency_window", "A_W_HEALTH", hours=6)
    assert out.data["worst_p95_ms"] == 900
    assert out.data["endpoints"][0]["endpoint"] == "/api/feedback"
    assert out.data["endpoints"][0]["error_count"] == 2


def test_telemetry_health_aggregates_samples(db_session):
    now = _now()
    for i in range(2):
        db_session.add(
            HealthMetric(
                ts=now - timedelta(minutes=i),
                platform="web",
                response_time_p95_ms=400 + i * 100,
                http_5xx_pct=1.0 + i,
                db_query_p95_ms=50,
                cpu_pct=20.0,
                ram_pct=40.0,
            )
        )
    db_session.commit()

    out = _run(db_session, "telemetry_health", "A_W_HEALTH", days=7)
    data = out.data
    assert data["samples"] == 2
    assert data["response_p95_ms_max"] == 500
    assert data["response_p95_ms_avg"] == 450
    assert data["http_5xx_pct_avg"] == 1.5
    assert isinstance(data["uptime_pct"], (int, float, type(None)))


def test_security_signals_counts_kinds_and_cves(db_session):
    now = _now()
    db_session.add(
        SecurityEvent(
            ts=now,
            platform="web",
            kind=SecurityEventKind.FAILED_LOGIN,
            ip_hash="ip-1",
            blocked=False,
        )
    )
    db_session.add(
        SecurityEvent(
            ts=now,
            platform="web",
            kind=SecurityEventKind.ROOT_DETECTED,
            ip_hash="ip-2",
            blocked=True,
        )
    )
    db_session.add(
        SecurityLog(
            ts=now,
            platform="web",
            category="auth",
            severity="high",
            action="blocked",
            ip_hash="ip-3",
            user_agent="Mozilla/5.0 (secret-device)",
            description="root attempt from 10.0.0.9",
            root_detected=True,
        )
    )
    db_session.add(
        DependencyVulnerability(
            ts=now,
            ecosystem="pypi",
            package_name="requests",
            installed_version="2.0.0",
            vuln_id="CVE-2024-0001",
            severity="critical",
            status="open",
        )
    )
    db_session.commit()

    out = _run(db_session, "security_signals", "C_W_SECURITY", days=7)
    blob = repr(out.data)
    data = out.data
    assert data["events_total"] == 2
    assert data["events_blocked"] == 1
    assert data["blocked_pct"] == 50.0
    assert data["root_signals"] == 1
    assert data["open_cves_by_severity"] == {"critical": 1}
    assert data["logs_by_severity"] == {"high": 1}
    # No IPs, no user agents, no rule descriptions.
    assert "10.0.0.9" not in blob
    assert "Mozilla/5.0" not in blob
    assert "ip-1" not in blob
