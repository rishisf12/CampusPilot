"""The default alert rules, seeded idempotently.

These are the rules the Prometheus alert file expressed, translated into the
app's own rule model: the metric is read from the in-app telemetry stores,
the condition is compared in Python, and the cooldown is the silencing.

The seed is idempotent — a rule is created only when no rule with the same
name exists — so it can run on every boot without duplicating anything, and
an operator's own rules are never overwritten.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from features.alerts.models import AlertRule

logger = logging.getLogger(__name__)

#: name, metric, condition, threshold, window minutes, severity, cooldown
DEFAULT_RULES: tuple[dict[str, Any], ...] = (
    {
        "name": "Web high latency",
        "description": "The web p95 response time is over a second.",
        "metric": "response_time_p95_ms",
        "condition": "gt",
        "threshold": 1000.0,
        "window_minutes": 5,
        "severity": "warning",
        "cooldown_minutes": 30,
    },
    {
        "name": "Web high error rate",
        "description": "More than 5% of web requests are failing.",
        "metric": "http_5xx_pct",
        "condition": "gt",
        "threshold": 5.0,
        "window_minutes": 5,
        "severity": "critical",
        "cooldown_minutes": 15,
    },
    {
        "name": "Web low uptime",
        "description": "The reader-derived uptime is below 99%.",
        "metric": "uptime_pct",
        "condition": "lt",
        "threshold": 99.0,
        "window_minutes": 15,
        "severity": "critical",
        "cooldown_minutes": 30,
    },
    {
        "name": "Android crash-free rate low",
        "description": "Fewer than 99% of Android sessions are crash-free.",
        "metric": "crash_free_rate_pct",
        "condition": "lt",
        "threshold": 99.0,
        "window_minutes": 30,
        "severity": "critical",
        "cooldown_minutes": 60,
    },
    {
        "name": "Host memory pressure",
        "description": "Memory use is over 90%.",
        "metric": "ram_pct",
        "condition": "gt",
        "threshold": 90.0,
        "window_minutes": 10,
        "severity": "warning",
        "cooldown_minutes": 30,
    },
    {
        "name": "Host CPU sustained",
        "description": "CPU use is over 90%.",
        "metric": "cpu_pct",
        "condition": "gt",
        "threshold": 90.0,
        "window_minutes": 15,
        "severity": "warning",
        "cooldown_minutes": 30,
    },
)


def seed_default_rules(session: Session) -> int:
    """Create the default rules that do not exist yet. Returns how many."""
    existing = {row.name for row in session.exec(select(AlertRule)).all()}
    created = 0
    for rule in DEFAULT_RULES:
        if rule["name"] in existing:
            continue
        session.add(AlertRule(**rule, enabled=True, channels=[]))
        created += 1
    if created:
        session.commit()
        logger.info("seeded %d default alert rule(s)", created)
    return created
