"""MCP: the alerting tools.

The scan agent has to be able to say "an alert is firing for the feedback
pipeline", and it has to say it without reading the channels' secrets. So:

- `open_alerts` - the incidents that are firing or acknowledged, by severity
- `alert_rules` - the rules and what they watch
- `alert_channels` - which channels exist, and whether they are enabled
- `alert_summary` - the shape of the alerting state for a window

**A channel's `config_json` never leaves the database.** It holds webhook
URLs, bot tokens and recipient lists; the tools report the channel's name,
type and enabled flag, and nothing else.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from features.alerts.models import AlertChannel, AlertIncident, AlertRule
from mcp.core.registry import ToolError, ToolResult
from mcp.monitoring.common import (
    MAX_AGGREGATE_WINDOW_DAYS,
    validated_window,
)

#: The severities an incident can carry, in the order an operator reads them.
SEVERITY_ORDER = ("critical", "warning", "info")


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """A datetime in UTC, whatever it came in as.

    The incident columns are `TIMESTAMP WITH TIME ZONE`, so the values that
    come back are aware; subtracting a naive "now" from them raises.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _age_minutes(started_at: Optional[datetime]) -> Optional[int]:
    """How long ago the incident started, in minutes."""
    started = _as_utc(started_at)
    if started is None:
        return None
    now = datetime.now(timezone.utc)
    return int((now - started).total_seconds() // 60)


def _validated_severity(severity: Optional[str]) -> Optional[str]:
    if severity is None or severity == "":
        return None
    value = severity.strip().lower()
    if value not in SEVERITY_ORDER:
        raise ToolError(f"severity {severity!r} not in {list(SEVERITY_ORDER)}")
    return value


def open_alerts(
    session: Session,
    days: int = 7,
    severity: str | None = None,
) -> ToolResult:
    """The incidents that are firing or acknowledged, newest first.

    Counts and the rule each incident belongs to - never the channel
    configuration, and never anything that identifies a person.
    """
    validated_window(days, name="days", low=1, high=MAX_AGGREGATE_WINDOW_DAYS)
    wanted = _validated_severity(severity)
    end = _utc_now_naive()
    start = end - timedelta(days=days)

    rows = session.exec(
        select(AlertIncident)
        .where(
            AlertIncident.started_at >= start,
            AlertIncident.status.in_(["firing", "acknowledged"]),
        )
        .order_by(AlertIncident.started_at.desc())
    ).all()

    rule_ids = {row.rule_id for row in rows}
    rules = {
        rule.id: rule
        for rule in session.exec(
            select(AlertRule).where(AlertRule.id.in_(rule_ids))
        ).all()
    } if rule_ids else {}

    incidents = []
    for row in rows:
        rule = rules.get(row.rule_id)
        rule_severity = (rule.severity if rule else "unknown").lower()
        if wanted and rule_severity != wanted:
            continue
        incidents.append(
            {
                "id": row.id,
                "rule": rule.name if rule else f"rule {row.rule_id}",
                "severity": rule_severity,
                "metric": rule.metric if rule else "",
                "status": row.status,
                "value": row.value,
                "threshold": row.threshold,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "age_minutes": _age_minutes(row.started_at),
            }
        )

    counts: dict[str, int] = {}
    for incident in incidents:
        counts[incident["severity"]] = counts.get(incident["severity"], 0) + 1

    return ToolResult(
        data={"incidents": incidents, "by_severity": counts, "window_days": days},
        row_count=len(incidents),
        metric_key=f"open_alerts_{days}d",
    )


def alert_rules(session: Session, enabled_only: bool = True) -> ToolResult:
    """The alert rules: what they watch and where they would send it.

    The channel *ids* are included (so an operator can see the routing is
    wired) but never the channels' configuration.
    """
    stmt = select(AlertRule)
    if enabled_only:
        stmt = stmt.where(AlertRule.enabled.is_(True))
    rows = session.exec(stmt.order_by(AlertRule.severity, AlertRule.name)).all()
    data = [
        {
            "id": row.id,
            "name": row.name,
            "severity": row.severity,
            "metric": row.metric,
            "condition": row.condition,
            "threshold": row.threshold,
            "window_minutes": row.window_minutes,
            "cooldown_minutes": row.cooldown_minutes,
            "enabled": row.enabled,
            "channel_count": len(row.channels or []),
        }
        for row in rows
    ]
    return ToolResult(
        data={"rules": data},
        row_count=len(data),
        metric_key="alert_rules",
    )


def alert_channels(session: Session) -> ToolResult:
    """The configured notification channels - names and types, never secrets.

    A channel's `config_json` holds webhook URLs, bot tokens and recipient
    lists. This tool reports that a channel exists, what kind it is and
    whether it is enabled, and nothing else: the scan agent has no reason
    to see a credential, and every path that could leak one is one more
    thing to audit.
    """
    rows = session.exec(
        select(AlertChannel).order_by(AlertChannel.created_at.desc())
    ).all()
    data = [
        {
            "id": row.id,
            "name": row.name,
            "type": row.channel_type,
            "enabled": row.enabled,
        }
        for row in rows
    ]
    return ToolResult(
        data={"channels": data},
        row_count=len(data),
        metric_key="alert_channels",
    )


def alert_summary(session: Session, days: int = 7) -> ToolResult:
    """The shape of the alerting state: counts by status and severity.

    One number per measure, so a scan can compare the window with the
    previous one without carrying a list of incidents around.
    """
    validated_window(days, name="days", low=1, high=MAX_AGGREGATE_WINDOW_DAYS)
    end = _utc_now_naive()
    start = end - timedelta(days=days)

    rows = session.exec(
        select(AlertIncident).where(AlertIncident.started_at >= start)
    ).all()
    rule_ids = {row.rule_id for row in rows}
    rules = {
        rule.id: rule
        for rule in session.exec(
            select(AlertRule).where(AlertRule.id.in_(rule_ids))
        ).all()
    } if rule_ids else {}

    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    per_rule: dict[str, int] = {}
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        rule = rules.get(row.rule_id)
        severity = (rule.severity if rule else "unknown").lower()
        by_severity[severity] = by_severity.get(severity, 0) + 1
        name = rule.name if rule else f"rule {row.rule_id}"
        per_rule[name] = per_rule.get(name, 0) + 1

    noisiest = sorted(per_rule.items(), key=lambda item: item[1], reverse=True)[:5]
    data = {
        "incidents": len(rows),
        "by_status": by_status,
        "by_severity": by_severity,
        "noisiest_rules": [{"rule": name, "count": count} for name, count in noisiest],
        "window_days": days,
    }
    return ToolResult(
        data=data,
        row_count=1,
        metric_key=f"alert_summary_{days}d",
    )


#: The alerting tools and the subsections allowed to ask for them.
ALERTING_TOOLS = (
    ("open_alerts", open_alerts, frozenset({"A_W_HEALTH", "A_A_HEALTH", "C_W_SECURITY"})),
    ("alert_rules", alert_rules, frozenset({"A_W_HEALTH", "A_A_HEALTH", "C_W_SECURITY"})),
    ("alert_channels", alert_channels, frozenset({"C_W_SECURITY"})),
    ("alert_summary", alert_summary, frozenset({"A_W_HEALTH", "A_A_HEALTH", "C_W_SECURITY"})),
)


def register_alerting(registry) -> None:
    """Register the alerting tools on a registry."""
    from mcp.core.registry import ToolSpec

    for name, fn, subsections in ALERTING_TOOLS:
        registry.register(ToolSpec(name=name, subsections=subsections), fn)
