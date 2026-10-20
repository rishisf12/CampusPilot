"""Phase 5 aggregate tools: the curated, count-only question layer.

The scan agent needs answers, not rows. Every tool here answers one question
with **counts and summaries only**:

===============================  ==================================  ====================
tool                             answers                             never returns
===============================  ==================================  ====================
``failed_logins_by_hour``        failed logins per hour, and how     no IPs, no user ids,
                                 many distinct sources               no raw events
``feedback_themes_top5``         the top feedback topics and the     no message text, no
                                 sentiment balance                   complaint bodies
``p95_latency_window``           the slowest endpoints and their     no request/response
                                 p95                                 bodies, no user data
``crash_clusters``               crash fingerprints, how many,      no stack traces, no
                                 which versions                      messages, no session ids
``telemetry_health``             uptime, latency and error           no per-sample rows
                                 aggregates for the window
``security_signals``             signal counts by kind, blocked      no rule details, no
                                 ratio, open CVEs by severity        IPs, no user agents
===============================  ==================================  ====================

That "never returns" column is not a promise in prose: the Phase 3 egress
gate masks anything PII-shaped that slips through, and the planted-PII test
proves it for these tools as well.

Every tool is read-only, answers in one round trip, and is scoped to the
scan subsections that legitimately need it.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from features.monitoring.domain.models import (
    CrashReport,
    DependencyVulnerability,
    FeedbackAnalysis,
    HealthMetric,
    SecurityEvent,
    SecurityEventKind,
    SecurityLog,
    SlowEndpoint,
)
from mcp.core.registry import ToolError, ToolResult
from mcp.monitoring.common import (
    MAX_AGGREGATE_ROWS,
    MAX_AGGREGATE_WINDOW_DAYS,
    MAX_AGGREGATE_WINDOW_HOURS,
    utc_now_naive,
    validated_platform,
    validated_window,
)
from observability.uptime import coverage_pct


def failed_logins_by_hour(
    session: Session,
    hours: int = 24,
    platform: str = "web",
) -> ToolResult:
    """Failed logins per hour, and how many distinct sources each hour had.

    Counts only. The IPs themselves stay in the database: the model gets
    "three distinct sources at 14:00", not the addresses.
    """
    validated_platform(platform)
    validated_window(hours, name="hours", low=1, high=MAX_AGGREGATE_WINDOW_HOURS)
    end = utc_now_naive()
    start = end - timedelta(hours=hours)

    hour = func.date_trunc("hour", SecurityEvent.ts)
    rows = session.exec(
        select(
            hour.label("hour"),
            func.count().label("failed_logins"),
            func.count(func.distinct(SecurityEvent.ip_hash)).label("distinct_sources"),
            func.count(func.distinct(SecurityEvent.user_hash)).label("distinct_users"),
        )
        .where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            SecurityEvent.kind == SecurityEventKind.FAILED_LOGIN,
        )
        .group_by(hour)
        .order_by(hour)
    ).all()

    data = [
        {
            "hour": row[0].isoformat(),
            "failed_logins": int(row[1]),
            "distinct_sources": int(row[2]),
            "distinct_users": int(row[3]),
        }
        for row in rows
    ]
    return ToolResult(
        data=data,
        row_count=len(data),
        metric_key=f"failed_logins_by_hour_{hours}h_{platform}",
    )


def feedback_themes_top5(
    session: Session,
    days: int = 7,
    top_n: int = 5,
) -> ToolResult:
    """The most frequent feedback topics and the sentiment balance.

    Topic labels are a fixed, hand-written vocabulary (see
    `features.monitoring.services.feedback_analysis`), so they cannot carry
    user text. Complaint bodies are deliberately not returned - only how
    often a topic came up.
    """
    validated_window(days, name="days", low=1, high=MAX_AGGREGATE_WINDOW_DAYS)
    validated_window(top_n, name="top_n", low=1, high=MAX_AGGREGATE_ROWS)
    end = utc_now_naive()
    start = end - timedelta(days=days)

    rows = session.exec(
        select(FeedbackAnalysis).where(
            FeedbackAnalysis.ts >= start,
            FeedbackAnalysis.ts < end,
        )
    ).all()

    topics: Counter[str] = Counter()
    positive = neutral = negative = 0
    sentiment_sum = 0.0
    total = 0
    for row in rows:
        for entry in row.topics or []:
            label = str(entry.get("topic", "")).strip()
            if label:
                topics[label] += int(entry.get("count", 0) or 0)
        positive += int(row.sentiment_positive or 0)
        neutral += int(row.sentiment_neutral or 0)
        negative += int(row.sentiment_negative or 0)
        sentiment_sum += float(row.sentiment_mean or 0.0) * int(row.total_count or 0)
        total += int(row.total_count or 0)

    top = [{"topic": label, "count": count} for label, count in topics.most_common(top_n)]
    data = {
        "topics": top,
        "total_count": total,
        "sentiment": {
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
            "mean": round(sentiment_sum / total, 4) if total else 0.0,
        },
        "windows_covered": len(rows),
    }
    return ToolResult(
        data=data,
        row_count=len(top),
        metric_key=f"feedback_themes_top{top_n}_{days}d",
    )


def p95_latency_window(
    session: Session,
    hours: int = 6,
    platform: str = "web",
    top_n: int = 10,
) -> ToolResult:
    """The slowest endpoints in the window, with their p95 and error counts.

    Endpoint labels are route templates ("/api/feedback"), never URLs with
    identifiers in them.
    """
    validated_platform(platform)
    validated_window(hours, name="hours", low=1, high=MAX_AGGREGATE_WINDOW_HOURS)
    validated_window(top_n, name="top_n", low=1, high=MAX_AGGREGATE_ROWS)
    end = utc_now_naive()
    start = end - timedelta(hours=hours)

    rows = session.exec(
        select(SlowEndpoint)
        .where(
            SlowEndpoint.ts >= start,
            SlowEndpoint.ts < end,
            SlowEndpoint.platform == platform,
        )
        .order_by(SlowEndpoint.p95_ms.desc())
        .limit(top_n)
    ).all()

    endpoints = [
        {
            "endpoint": row.endpoint,
            "method": row.method,
            "p50_ms": int(row.p50_ms),
            "p95_ms": int(row.p95_ms),
            "p99_ms": int(row.p99_ms),
            "request_count": int(row.request_count),
            "error_count": int(row.error_count),
        }
        for row in rows
    ]
    worst = max((e["p95_ms"] for e in endpoints), default=0)
    data = {
        "endpoints": endpoints,
        "worst_p95_ms": worst,
        "window_hours": hours,
    }
    return ToolResult(
        data=data,
        row_count=len(endpoints),
        metric_key=f"p95_latency_window_{hours}h_{platform}",
    )


def crash_clusters(
    session: Session,
    days: int = 7,
    platform: str = "web",
    max_n: int = 10,
) -> ToolResult:
    """Crash clusters: which fingerprints crash, how often, and where.

    The fingerprint, the exception type and the version are the whole
    answer. Messages and stack traces are exactly where a user's data hides,
    so they never leave the database.
    """
    validated_platform(platform)
    validated_window(days, name="days", low=1, high=MAX_AGGREGATE_WINDOW_DAYS)
    validated_window(max_n, name="max_n", low=1, high=MAX_AGGREGATE_ROWS)
    end = utc_now_naive()
    start = end - timedelta(days=days)

    rows = session.exec(
        select(CrashReport).where(
            CrashReport.ts >= start,
            CrashReport.ts < end,
            CrashReport.platform == platform,
        )
    ).all()

    clusters: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = clusters.setdefault(
            row.fingerprint,
            {
                "fingerprint": row.fingerprint,
                "exception_type": row.exception_type or "unknown",
                "count": 0,
                "fatal": 0,
                "sessions": 0,
                "first_seen": row.ts,
                "last_seen": row.ts,
                "app_versions": set(),
            },
        )
        entry["count"] += 1
        entry["fatal"] += 1 if row.fatal else 0
        entry["sessions"] += 1 if row.session_id else 0
        entry["first_seen"] = min(entry["first_seen"], row.ts)
        entry["last_seen"] = max(entry["last_seen"], row.ts)
        if row.app_version:
            entry["app_versions"].add(row.app_version)

    ordered = sorted(clusters.values(), key=lambda c: c["count"], reverse=True)[:max_n]
    data = [
        {
            "fingerprint": entry["fingerprint"],
            "exception_type": entry["exception_type"],
            "count": entry["count"],
            "fatal_count": entry["fatal"],
            "affected_sessions": entry["sessions"],
            "first_seen": entry["first_seen"].isoformat(),
            "last_seen": entry["last_seen"].isoformat(),
            "app_versions": sorted(entry["app_versions"]),
        }
        for entry in ordered
    ]
    return ToolResult(
        data=data,
        row_count=len(data),
        metric_key=f"crash_clusters_{days}d_{platform}",
    )


def telemetry_health(
    session: Session,
    days: int = 7,
    platform: str = "web",
) -> ToolResult:
    """Uptime, latency and error aggregates for the window.

    One number per measure, never a list of samples: the agent needs the
    shape of the window, not every point in it.
    """
    validated_platform(platform)
    validated_window(days, name="days", low=1, high=MAX_AGGREGATE_WINDOW_DAYS)
    end = utc_now_naive()
    start = end - timedelta(days=days)

    rows = session.exec(
        select(HealthMetric).where(
            HealthMetric.ts >= start,
            HealthMetric.ts < end,
            HealthMetric.platform == platform,
        )
    ).all()

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 3) if values else 0.0

    def _max(values: list[float]) -> float:
        return round(max(values), 3) if values else 0.0

    latencies = [float(r.response_time_p95_ms or 0) for r in rows if r.response_time_p95_ms is not None]
    db_latencies = [float(r.db_query_p95_ms or 0) for r in rows if r.db_query_p95_ms is not None]
    error_rates = [float(r.http_5xx_pct or 0) for r in rows if r.http_5xx_pct is not None]
    cpu = [float(r.cpu_pct or 0) for r in rows if r.cpu_pct is not None]
    ram = [float(r.ram_pct or 0) for r in rows if r.ram_pct is not None]

    data = {
        "samples": len(rows),
        "uptime_pct": coverage_pct(session, platform=platform, start=start, end=end),
        "response_p95_ms_avg": _avg(latencies),
        "response_p95_ms_max": _max(latencies),
        "db_query_p95_ms_avg": _avg(db_latencies),
        "http_5xx_pct_avg": _avg(error_rates),
        "http_5xx_pct_max": _max(error_rates),
        "cpu_pct_avg": _avg(cpu),
        "ram_pct_avg": _avg(ram),
        "window_days": days,
    }
    return ToolResult(
        data=data,
        row_count=1,
        metric_key=f"telemetry_health_{days}d_{platform}",
    )


def security_signals(
    session: Session,
    days: int = 7,
) -> ToolResult:
    """Security signal counts: events by kind, blocked ratio, open CVEs.

    Rule names, IPs, user agents and descriptions are left in the database -
    the model gets counts it can compare against thresholds.
    """
    validated_window(days, name="days", low=1, high=MAX_AGGREGATE_WINDOW_DAYS)
    end = utc_now_naive()
    start = end - timedelta(days=days)

    event_rows = session.exec(
        select(
            SecurityEvent.kind,
            func.count(),
            # `sum(boolean)` does not exist in Postgres; a filtered count does.
            func.count().filter(SecurityEvent.blocked.is_(True)),
        )
        .where(SecurityEvent.ts >= start, SecurityEvent.ts < end)
        .group_by(SecurityEvent.kind)
    ).all()
    by_kind = {
        str(kind.value if hasattr(kind, "value") else kind): {
            "count": int(total),
            "blocked": int(blocked or 0),
        }
        for kind, total, blocked in event_rows
    }

    log_rows = session.exec(
        select(SecurityLog.severity, func.count())
        .where(SecurityLog.ts >= start, SecurityLog.ts < end)
        .group_by(SecurityLog.severity)
    ).all()
    by_severity = {str(severity): int(count) for severity, count in log_rows}

    root_signals = session.exec(
        select(func.count()).where(
            SecurityLog.ts >= start,
            SecurityLog.ts < end,
            SecurityLog.root_detected.is_(True),
        )
    ).one()

    cve_rows = session.exec(
        select(DependencyVulnerability.severity, func.count())
        .where(DependencyVulnerability.status == "open")
        .group_by(DependencyVulnerability.severity)
    ).all()
    open_cves = {str(severity): int(count) for severity, count in cve_rows}

    total_events = sum(v["count"] for v in by_kind.values())
    total_blocked = sum(v["blocked"] for v in by_kind.values())
    data = {
        "events_by_kind": by_kind,
        "events_total": total_events,
        "events_blocked": total_blocked,
        "blocked_pct": round(100.0 * total_blocked / total_events, 2) if total_events else 0.0,
        "logs_by_severity": by_severity,
        "root_signals": int(root_signals or 0),
        "open_cves_by_severity": open_cves,
        "window_days": days,
    }
    return ToolResult(
        data=data,
        row_count=1,
        metric_key=f"security_signals_{days}d",
    )


#: Every aggregate tool, with the subsections allowed to ask. Scoping is
#: server-side: a scan cannot conjure another subsection's tool.
AGGREGATE_TOOLS = (
    ("failed_logins_by_hour", failed_logins_by_hour, frozenset({"C_W_SECURITY", "C_A_SECURITY"})),
    ("feedback_themes_top5", feedback_themes_top5, frozenset({"D_W_FEEDBACK", "D_A_FEEDBACK"})),
    ("p95_latency_window", p95_latency_window, frozenset({"A_W_HEALTH", "A_A_HEALTH"})),
    ("crash_clusters", crash_clusters, frozenset({"A_A_HEALTH", "D_A_FEEDBACK"})),
    ("telemetry_health", telemetry_health, frozenset({"A_W_HEALTH", "A_A_HEALTH"})),
    ("security_signals", security_signals, frozenset({"C_W_SECURITY", "C_A_SECURITY"})),
)


def register_aggregates(registry) -> None:
    """Register the aggregate tools on a registry."""
    from mcp.core.registry import ToolSpec

    for name, fn, subsections in AGGREGATE_TOOLS:
        registry.register(ToolSpec(name=name, subsections=subsections), fn)
