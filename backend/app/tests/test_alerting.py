"""Tests for the alerting replacement (parity row 9).

Alertmanager did three things: it evaluated rules, it silenced the noisy
ones, and it routed the result to channels. All three are here now, against
the in-app stores:

- the evaluator reads the metric, compares it with the rule, and opens an
  incident;
- the cooldown is the silencing: a rule that stays breached does not open a
  second incident;
- the delivery routes to the channels, and a channel's secrets never leave
  the database.

And the scan agent can see the result through the MCP tools, without ever
seeing a channel's configuration.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.alerts.models import AlertChannel, AlertIncident, AlertRule
from features.alerts.evaluator import evaluate_rules, metric_value
from mcp.core.registry import run_tool
from mcp.monitoring import REGISTRY


@pytest.fixture
def db_session():
    with Session(engine) as session:
        for model in (AlertIncident, AlertRule, AlertChannel):
            session.exec(delete(model))
        session.commit()
        yield session
        for model in (AlertIncident, AlertRule, AlertChannel):
            session.exec(delete(model))
        session.commit()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _rule(session, **over):
    fields = {
        "name": "p95 too high",
        "description": "the feedback endpoint is slow",
        "metric": "p95_latency",
        "condition": "gt",
        "threshold": 0.0,
        "window_minutes": 60,
        "severity": "warning",
        "channels": [],
        "cooldown_minutes": 15,
        "enabled": True,
    }
    fields.update(over)
    rule = AlertRule(**fields)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def _channel(session, **over):
    fields = {
        "name": "ops email",
        "channel_type": "email",
        "config_json": {"to": ["ops@example.edu"], "smtp_password": "secret"},
        "enabled": True,
    }
    fields.update(over)
    channel = AlertChannel(**fields)
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


# --- the evaluator -----------------------------------------------------------


def test_a_breached_rule_opens_an_incident(db_session):
    _rule(db_session, threshold=0.0, metric="http_5xx_pct")
    # No health samples yet: the honest answer is "no data", not zero.
    assert evaluate_rules(db_session) == []

    from features.monitoring.domain.models import HealthMetric

    now = _now()
    db_session.add(
        HealthMetric(ts=now, platform="web", response_time_p95_ms=900, http_5xx_pct=4.0)
    )
    db_session.commit()

    opened = evaluate_rules(db_session)
    assert len(opened) == 1
    assert opened[0].status == "firing"
    assert opened[0].value == 4.0
    assert db_session.exec(select(AlertIncident)).all()


def test_the_cooldown_silences_a_repeated_breach(db_session):
    from features.monitoring.domain.models import HealthMetric

    now = _now()
    db_session.add(
        HealthMetric(ts=now, platform="web", response_time_p95_ms=900, http_5xx_pct=4.0)
    )
    db_session.commit()
    _rule(db_session, threshold=1.0, metric="http_5xx_pct", cooldown_minutes=30)

    assert len(evaluate_rules(db_session)) == 1
    # Still breached, still inside the cooldown: silence, not a second alert.
    assert len(evaluate_rules(db_session)) == 0
    assert len(db_session.exec(select(AlertIncident)).all()) == 1


def test_a_rule_that_is_not_breached_opens_nothing(db_session):
    from features.monitoring.domain.models import HealthMetric

    now = _now()
    db_session.add(
        HealthMetric(ts=now, platform="web", response_time_p95_ms=10, http_5xx_pct=0.0)
    )
    db_session.commit()
    _rule(db_session, threshold=50.0, metric="http_5xx_pct")
    assert evaluate_rules(db_session) == []


def test_an_unknown_metric_reads_as_no_data(db_session):
    _rule(db_session, metric="a_metric_nobody_measures")
    assert metric_value(db_session, "a_metric_nobody_measures", 60) is None
    assert evaluate_rules(db_session) == []


# --- the MCP tools -----------------------------------------------------------


def test_open_alerts_reports_the_incidents(db_session):
    rule = _rule(db_session, threshold=1.0, metric="http_5xx_pct", severity="critical")
    incident = AlertIncident(
        rule_id=rule.id, status="firing", value=9.0, threshold=1.0, started_at=_now()
    )
    db_session.add(incident)
    db_session.commit()

    out = run_tool(
        db_session,
        REGISTRY,
        scan_id="scan-alerts",
        subsection="A_W_HEALTH",
        name="open_alerts",
        args={"days": 7},
    )
    assert out.data["by_severity"] == {"critical": 1}
    assert out.data["incidents"][0]["severity"] == "critical"
    assert out.data["incidents"][0]["age_minutes"] is not None


def test_a_channel_secret_never_leaves_the_database(db_session):
    channel = _channel(db_session)
    out = run_tool(
        db_session,
        REGISTRY,
        scan_id="scan-channels",
        subsection="C_W_SECURITY",
        name="alert_channels",
    )
    blob = repr(out.data)
    assert "ops email" in blob
    assert "secret" not in blob
    assert "ops@example.edu" not in blob
    assert channel.config_json["smtp_password"] == "secret"  # still in the database


def test_the_alerting_tools_are_scoped(db_session):
    from mcp.core.registry import ToolNotPermitted

    with pytest.raises(ToolNotPermitted):
        REGISTRY.permitted("open_alerts", "D_W_FEEDBACK")
    assert REGISTRY.permitted("open_alerts", "A_W_HEALTH")
    assert REGISTRY.permitted("alert_channels", "C_W_SECURITY")


def test_alert_summary_counts_by_status_and_severity(db_session):
    rule = _rule(db_session, severity="warning")
    for status, value in (("firing", 5.0), ("resolved", 2.0)):
        db_session.add(
            AlertIncident(
                rule_id=rule.id, status=status, value=value, threshold=1.0, started_at=_now()
            )
        )
    db_session.commit()

    out = run_tool(
        db_session,
        REGISTRY,
        scan_id="scan-summary",
        subsection="A_W_HEALTH",
        name="alert_summary",
        args={"days": 7},
    )
    assert out.data["incidents"] == 2
    assert out.data["by_status"] == {"firing": 1, "resolved": 1}
    assert out.data["by_severity"] == {"warning": 2}
    assert out.data["noisiest_rules"][0]["rule"] == "p95 too high"


# --- the delivery ------------------------------------------------------------


def test_delivery_routes_to_the_channels_and_never_leaks_the_config(db_session):
    import asyncio

    from features.alerts.delivery import deliver

    channel = _channel(db_session)
    rule = _rule(db_session, channels=[channel.id])
    incident = AlertIncident(
        rule_id=rule.id, status="firing", value=9.0, threshold=1.0, started_at=_now()
    )
    db_session.add(incident)
    db_session.commit()

    results = asyncio.run(deliver(db_session, incident, rule))
    assert len(results) == 1
    assert results[0]["channel"] == "ops email"
    # No SMTP configured in the test environment: the delivery is attempted
    # and honestly reported as not delivered.
    assert results[0]["delivered"] is False
    assert "secret" not in repr(results)
