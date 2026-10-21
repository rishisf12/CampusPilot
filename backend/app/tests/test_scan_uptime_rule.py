"""Tests for the uptime rule and the coverage that feeds it.

The number is the coverage of the health-sample table; what matters is that
the scan can say *why* it is low:

- the process was not running for part of the window (the host was off) —
  an availability fact about the deployment; or
- the process was running and the sampler stopped reporting — a real defect,
  and the one that deserves an incident.

A reader runs inside the API, so it can tell the two apart: if the newest
sample is several intervals old while the scan is being served, the sampler
stalled.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import HealthMetric
from features.monitoring.domain.thresholds import evaluate_a_w_health
from observability.uptime import coverage_detail


@pytest.fixture
def db_session():
    with Session(engine) as session:
        session.exec(delete(HealthMetric))
        session.commit()
        yield session
        session.exec(delete(HealthMetric))
        session.commit()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


#: A platform label of this test's own, so another test's leftover sample
#: cannot make "the newest sample" a different one.
_PLATFORM = "test-uptime-rule"


def _evaluate(**over):
    """The A_W_HEALTH evaluator with everything present unless overridden."""
    data = {
        "http_p95_ms": 120.0,
        "http_5xx_pct": 0.1,
        "uptime_pct": 99.95,
        "cpu_pct": 30.0,
        "ram_pct": 40.0,
        "disk_pct": 50.0,
        "db_query_p95_ms": 20.0,
        "ssl_expiry_days": 60,
    }
    data.update(over)
    return evaluate_a_w_health(**data)


# --- the rule ----------------------------------------------------------------


def test_downtime_is_named_as_downtime_not_as_a_service_fault():
    verdict = _evaluate(
        uptime_pct=40.35,
        uptime_downtime_s=19 * 3600,
        uptime_window_hours=24,
    )
    assert verdict.status.value == "critical"
    titles = [f.title for f in verdict.findings]
    assert any("not running" in t for t in titles), titles
    assert not any(t == "Uptime critical" for t in titles), titles
    # The root cause says the process was down, not that the service failed.
    assert any("not running" in cause for cause in verdict.root_causes), verdict.root_causes
    # The evidence carries the window and the downtime.
    finding = next(f for f in verdict.findings if "not running" in f.title)
    assert "19.0h down" in finding.window
    assert finding.value == 40.35


def test_a_stalled_sampler_is_its_own_critical():
    verdict = _evaluate(
        uptime_pct=88.0,
        uptime_sampler_stalled=True,
        uptime_downtime_s=0,
    )
    assert verdict.status.value == "critical"
    titles = [f.title for f in verdict.findings]
    assert "Health sampling stalled while the API was serving" in titles, titles
    assert any("sampler stopped reporting" in c for c in verdict.root_causes), verdict.root_causes
    # It is a pipeline problem, not an endpoint to investigate.
    assert "investigate_data_pipeline" in verdict.actions


def test_the_floor_is_the_operators_to_set():
    """A development box that is only up during work hours says so."""
    verdict = _evaluate(
        uptime_pct=40.35,
        uptime_downtime_s=19 * 3600,
        uptime_floor_pct=0.0,
    )
    assert verdict.status.value != "critical"
    # The number is still reported - just not as an incident.
    assert any("Uptime below target" == f.title for f in verdict.findings)


def test_healthy_uptime_says_nothing():
    verdict = _evaluate(uptime_pct=99.99)
    assert verdict.status.value == "healthy"
    assert verdict.findings == []


# --- the coverage ------------------------------------------------------------


def test_coverage_reports_a_stalled_sampler(db_session):
    """The app is serving (the reader is running) but the samples stopped."""
    now = _now()
    db_session.add(
        HealthMetric(
            ts=now - timedelta(hours=6), platform=_PLATFORM, response_time_p95_ms=10
        )
    )
    db_session.commit()
    detail = coverage_detail(
        db_session, platform=_PLATFORM, start=now - timedelta(hours=24), end=now
    )
    assert detail.sampler_stalled is True
    assert detail.newest_sample_age_s is not None
    assert detail.newest_sample_age_s > 3600


def test_coverage_reports_no_stall_when_the_samples_are_current(db_session):
    now = _now()
    db_session.add(
        HealthMetric(
            ts=now - timedelta(seconds=20), platform=_PLATFORM, response_time_p95_ms=10
        )
    )
    db_session.commit()
    detail = coverage_detail(
        db_session, platform=_PLATFORM, start=now - timedelta(hours=24), end=now
    )
    assert detail.sampler_stalled is False
    assert detail.coverage_pct is not None


def test_coverage_reports_the_downtime_it_cannot_explain_away(db_session):
    """Samples for part of the window: the rest is the process not running."""
    now = _now()
    # Strictly inside the window: the coverage query reads `ts < end`, so a
    # sample at exactly `now` is not one of them.
    for offset_minutes in range(1, 61, 5):
        db_session.add(
            HealthMetric(
                ts=now - timedelta(minutes=offset_minutes),
                platform=_PLATFORM,
                response_time_p95_ms=10,
            )
        )
    db_session.commit()
    detail = coverage_detail(
        db_session, platform=_PLATFORM, start=now - timedelta(hours=24), end=now
    )
    assert detail.rows == 12
    assert detail.downtime_s > 0
    assert detail.sampler_stalled is False
