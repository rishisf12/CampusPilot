"""Evaluate the alert rules against the in-app telemetry stores.

This is the part Alertmanager used to do for us, done against the stores the
app already keeps:

- a rule names a metric, a condition, a threshold and a window;
- the metric is read from the in-app telemetry (the same numbers the
  dashboards show);
- when the condition is breached, a **firing incident** is created - unless
  the same rule fired within its **cooldown**, which is the silencing: a
  flapping metric must not become a hundred notifications;
- the incident is handed to `delivery`, which routes it to the rule's
  channels (email, Slack, Discord, Telegram).

No Prometheus, no rules file, no separate evaluator to run: the rules live
in the same database as the data and the same database as the incidents.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from features.alerts.models import AlertIncident, AlertRule
from features.monitoring.services import queries as mqueries

logger = logging.getLogger(__name__)

#: The metrics a rule may name, and how to read them. The names are the ones
#: the admin UI offers, plus the aliases people type.
METRIC_ALIASES = {
    "http_5xx_pct": "http_5xx_pct",
    "error_rate": "http_5xx_pct",
    "5xx_rate": "http_5xx_pct",
    "response_time_p95_ms": "response_time_p95_ms",
    "p95_latency": "response_time_p95_ms",
    "latency_p95_ms": "response_time_p95_ms",
    "crash_free_rate": "crash_free_rate_pct",
    "crash_free_rate_pct": "crash_free_rate_pct",
    "uptime_pct": "uptime_pct",
    "cpu_pct": "cpu_pct",
    "ram_pct": "ram_pct",
    "active_users": "active_users",
    "dau": "active_users",
}

#: How a condition reads.
CONDITIONS = {
    "gt": lambda value, threshold: value > threshold,
    "gte": lambda value, threshold: value >= threshold,
    "lt": lambda value, threshold: value < threshold,
    "lte": lambda value, threshold: value <= threshold,
    "eq": lambda value, threshold: value == threshold,
}


def _now_utc() -> datetime:
    """Now, timezone-aware.

    The incident columns are `TIMESTAMP WITH TIME ZONE`, so the values that
    come back are aware; comparing them with a naive "now" raises rather
    than answers.
    """
    return datetime.now(timezone.utc)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """A datetime in UTC, whatever it came in as."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def metric_value(
    session: Session,
    metric: str,
    window_minutes: int,
    *,
    now: Optional[datetime] = None,
) -> Optional[float]:
    """The current value of a metric, or None when there is no data yet.

    None is not zero: "no samples" is the honest answer, and a rule that
    fires on a metric nobody measures is worse than one that stays quiet.
    """
    now = now or _now_utc()
    start = now - timedelta(minutes=max(1, window_minutes))
    name = METRIC_ALIASES.get((metric or "").strip().lower())
    if name is None:
        return None

    if name in {"http_5xx_pct", "response_time_p95_ms", "uptime_pct", "cpu_pct", "ram_pct"}:
        overview = mqueries.health_overview(session, start, end=now)
        if not overview.get("has_data"):
            return None
        value = overview.get(name)
        return float(value) if value is not None else None

    if name == "crash_free_rate_pct":
        result = mqueries.crash_free_rate(session, start, now)
        value = result.get("crash_free_rate_pct")
        return float(value) if value is not None else None

    if name == "active_users":
        return float(mqueries.active_users(session, start, now, None))

    return None


def _breached(value: float, condition: str, threshold: float) -> bool:
    test = CONDITIONS.get((condition or "gt").strip().lower())
    if test is None:
        return False
    return test(value, threshold)


def _in_cooldown(
    session: Session, rule: AlertRule, now: datetime
) -> Optional[AlertIncident]:
    """The incident that is still cooling down, if there is one.

    The cooldown is the silencing: while it lasts, the same rule does not
    open a new incident, so a metric that stays breached produces one
    notification and then quiet.
    """
    recent = session.exec(
        select(AlertIncident)
        .where(
            AlertIncident.rule_id == rule.id,
            AlertIncident.status.in_(["firing", "acknowledged"]),
        )
        .order_by(AlertIncident.started_at.desc())
        .limit(1)
    ).first()
    if recent is None:
        return None
    started = _as_utc(recent.started_at)
    if started is None:
        return None
    if (now - started) < timedelta(minutes=max(0, rule.cooldown_minutes)):
        return recent
    return None


def evaluate_rules(
    session: Session,
    *,
    now: Optional[datetime] = None,
) -> list[AlertIncident]:
    """Evaluate every enabled rule. Returns the incidents that opened."""
    now = now or _now_utc()
    rules = session.exec(select(AlertRule).where(AlertRule.enabled.is_(True))).all()
    opened: list[AlertIncident] = []
    for rule in rules:
        value = metric_value(session, rule.metric, rule.window_minutes, now=now)
        if value is None:
            continue
        if not _breached(value, rule.condition, rule.threshold):
            continue
        if _in_cooldown(session, rule, now) is not None:
            continue
        incident = AlertIncident(
            rule_id=rule.id,
            status="firing",
            value=value,
            threshold=rule.threshold,
            started_at=now,
        )
        session.add(incident)
        opened.append(incident)
    if opened:
        session.commit()
        for incident in opened:
            session.refresh(incident)
        logger.info("opened %d alert incident(s)", len(opened))
    return opened


def incidents_to_deliver(session: Session, incidents: list[AlertIncident]) -> list[tuple]:
    """Pair each new incident with the channels its rule routes to."""
    pairs: list[tuple] = []
    for incident in incidents:
        rule = session.exec(
            select(AlertRule).where(AlertRule.id == incident.rule_id)
        ).first()
        if rule is None:
            continue
        pairs.append((incident, rule))
    return pairs
