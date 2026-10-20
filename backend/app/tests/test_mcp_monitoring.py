"""Tests for the Monitoring MCP tools (Phase 2 of the MCP plan).

These tools are what Phase 6's parity gate will hold against the containers
they replace, so the tests pin the same three things the dashboards used to
read from Prometheus:

1. `health_latest` answers with exactly the row's measured numbers - and
   writes the audit row that proves the read happened (the reconciler's
   contract).
2. `health_uptime_pct` hands out reader-derived coverage with pinned values.
3. `daily_active_users` uses the same privacy-preserving session count every
   other dashboard number is computed from.

Subsection scoping is asserted server-side: a scan may not call another
subsection's tool.
"""
import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import HealthMetric, Session as MonitorSession, ToolCallAudit
from mcp.core.registry import ToolNotPermitted, run_tool
from mcp.monitoring import REGISTRY


@pytest.fixture
def db_session():
    """A session with the tables these tools read emptied first."""
    with Session(engine) as session:
        for model in (HealthMetric, MonitorSession, ToolCallAudit):
            session.exec(delete(model))
        session.commit()
        yield session
        for model in (HealthMetric, MonitorSession, ToolCallAudit):
            session.exec(delete(model))
        session.commit()


def _hm(**over):
    from datetime import datetime, timezone

    fields = {"ts": datetime.now(timezone.utc).replace(tzinfo=None), "platform": "web"}
    fields.update(over)
    return HealthMetric(**fields)


def _run(session, name, subsection, **args):
    return run_tool(session, REGISTRY, subsection=subsection, name=name, args=args)


def test_registry_scopes_tools_to_their_subsections():
    assert REGISTRY.permitted("health_latest", "A_W_HEALTH")
    assert REGISTRY.permitted("health_uptime_pct", "A_W_HEALTH")
    assert REGISTRY.permitted("daily_active_users", "B_W_ACTIVITY")
    assert REGISTRY.permitted("daily_active_users", "B_A_ACTIVITY")
    with pytest.raises(ToolNotPermitted):
        REGISTRY.permitted("health_latest", "B_W_ACTIVITY")
    with pytest.raises(ToolNotPermitted):
        REGISTRY.permitted("daily_active_users", "C_W_SECURITY")


def test_invalid_inputs_are_refused_and_audited(db_session):
    """A typo'd platform or a zero/negative window must not read like 'no data'."""
    from mcp.core.registry import ToolError

    for kwargs in (
        {"platform": "galaxy"},
        {"platform": "web", "window_hours": 0},
        {"platform": "web", "window_hours": -5},
        {"platform": "web", "window_hours": 24 * 90 + 1},
    ):
        with pytest.raises(ToolError):
            _run(db_session, "health_uptime_pct", "A_W_HEALTH", **kwargs)
    refusals = db_session.exec(select(ToolCallAudit)).all()
    assert len(refusals) == 4
    assert all(r.ok is False for r in refusals)
    assert all("not in" in (r.error or "") or "window_hours" in (r.error or "") for r in refusals)

    with pytest.raises(ToolError, match="window_days"):
        _run(db_session, "daily_active_users", "B_W_ACTIVITY", window_days=0)

    with pytest.raises(ToolError, match="platform"):
        _run(db_session, "health_latest", "A_W_HEALTH", platform="browser")


def test_health_latest_returns_the_pinned_row(db_session):
    row = db_session.exec(select(HealthMetric)).first()  # empty table confirmed
    assert row is None

    db_session.add(_hm(response_time_p95_ms=321, http_5xx_pct=0.4, cpu_pct=33.3))
    db_session.commit()

    result = _run(db_session, "health_latest", "A_W_HEALTH", platform="web")

    assert result.data["response_time_p95_ms"] == 321
    assert result.data["http_5xx_pct"] == 0.4
    assert result.data["cpu_pct"] == 33.3
    assert result.row_count == 1

    audit = db_session.exec(select(ToolCallAudit)).one()
    assert audit.ok is True
    assert audit.tool == "health_latest"
    assert audit.metric_key == "web_health_latest"


def test_health_latest_returns_none_before_first_sample(db_session):
    result = _run(db_session, "health_latest", "A_W_HEALTH")
    assert result.data is None
    assert result.row_count == 0


def test_uptime_tool_pinned_by_row_layout(db_session, monkeypatch):
    from core.config import settings

    db_session.add(_hm(response_time_p95_ms=10))
    db_session.commit()

    # An hour-long window anchored by the one row: every expected interval
    # holds a sample, so coverage reads a clean 100.0.
    monkeypatch.setattr(settings, "health_sample_interval_s", 3600)
    result = _run(db_session, "health_uptime_pct", "A_W_HEALTH", platform="web", window_hours=1)
    assert result.data == 100.0
    audit = db_session.exec(select(ToolCallAudit)).one()
    assert audit.metric_key == "web_uptime_pct"
    assert audit.ok is True


def test_uptime_tool_is_none_without_data(db_session):
    result = _run(db_session, "health_uptime_pct", "A_W_HEALTH", window_hours=24)
    assert result.data is None
    assert result.row_count == 0


def test_daily_active_users_counts_distinct_hashed_users(db_session):
    from datetime import datetime, timedelta, timezone

    ts = datetime.now(timezone.utc).replace(tzinfo=None)
    # Three hashes plus one anonymous session, spread over 3 days so the
    # 1-day window cannot accidentally pull later rows in.
    for i, (sid, uh) in enumerate(
        [("s1", "h1"), ("s2", "h1"), ("s3", "h2"), ("s4", None)]
    ):
        db_session.add(
            MonitorSession(
                session_id=sid,
                platform="web",
                user_hash=uh,
                started_at=ts - timedelta(days=i + 1) + timedelta(minutes=5),
                last_seen_at=ts - timedelta(days=i + 1) + timedelta(minutes=35),
            )
        )
    db_session.commit()

    result = _run(db_session, "daily_active_users", "B_W_ACTIVITY", platform="web", window_days=1)
    # s1 (h1) started minutes before insert-time; everything else is a day+
    # behind. One distinct hash in the window.
    assert result.data == 1
