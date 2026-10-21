"""MCP #1: Monitoring - the query layer that replaces the Prometheus stack.

Everything the old containers scraped or stored is answered here through the
shared tool contract (`mcp.core`): subsection-scoped tools, a per-call timeout,
a row cap, refusals audited alongside successes. `telemetry.health_metric` is
the one store - written in-app by `features.monitoring.infrastructure.health`,
covering the latency/HTTP/DB figures Prometheus used to keep, and since Phase 2
the host figures node-exporter/cadvisor used to scrape. Uptime comes from
`observability.uptime`'s reader-derived coverage, replacing blackbox-exporter.

`docs/MCP_MIGRATION_PLAN.md`'s parity table gates removing the containers on
these tools answering everything the dashboards showed - not on this file
existing.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from features.monitoring.domain.models import HealthMetric
from features.monitoring.services import queries as mqueries
from mcp.core.registry import ToolError, ToolRegistry, ToolResult, ToolSpec
from mcp.monitoring.aggregates import register_aggregates
from mcp.monitoring.common import (
    MAX_DAU_WINDOW_DAYS,
    MAX_UPTIME_WINDOW_HOURS,
    PLATFORMS,
    utc_now_naive as _utc_now_naive,
    validated_platform as _validated,
)
from observability.uptime import coverage_pct

__all__ = [
    "MAX_DAU_WINDOW_DAYS",
    "MAX_UPTIME_WINDOW_HOURS",
    "PLATFORMS",
    "REGISTRY",
]


def _row_to_dict(row: HealthMetric) -> dict[str, Any]:
    """Detached-safe snapshot of a row, read while the session is open."""
    return {
        "ts": row.ts,
        "platform": row.platform,
        "cpu_pct": row.cpu_pct,
        "ram_pct": row.ram_pct,
        "disk_pct": row.disk_pct,
        "network_rx_bytes": row.network_rx_bytes,
        "network_tx_bytes": row.network_tx_bytes,
        "response_time_p95_ms": row.response_time_p95_ms,
        "response_time_p99_ms": row.response_time_p99_ms,
        "http_5xx_pct": row.http_5xx_pct,
        "db_query_p95_ms": row.db_query_p95_ms,
        "db_slow_queries_count": row.db_slow_queries_count,
        "db_connections_active": row.db_connections_active,
        "db_connections_idle": row.db_connections_idle,
    }


def health_latest(session: Session, platform: str = "web") -> ToolResult:
    """The newest health sample for a platform, or None before the first one."""
    _validated(platform)
    row = session.exec(
        select(HealthMetric)
        .where(HealthMetric.platform == platform)
        .order_by(HealthMetric.ts.desc())
        .limit(1)
    ).first()
    metric_key = f"{platform}_health_latest"
    if row is None:
        return ToolResult(data=None, row_count=0, metric_key=metric_key)
    return ToolResult(data=_row_to_dict(row), row_count=1, metric_key=metric_key)


def health_uptime_pct(
    session: Session,
    platform: str = "web",
    window_hours: int = 24,
) -> ToolResult:
    """Reader-derived availability for the last `window_hours` (or None)."""
    _validated(platform)
    if not isinstance(window_hours, int) or not 1 <= window_hours <= MAX_UPTIME_WINDOW_HOURS:
        raise ToolError(f"window_hours must be 1..{MAX_UPTIME_WINDOW_HOURS}, got {window_hours!r}")
    end = _utc_now_naive()
    start = end - timedelta(hours=window_hours)
    pct = coverage_pct(session, platform=platform, start=start, end=end)
    return ToolResult(
        data=pct,
        row_count=1 if pct is not None else 0,
        metric_key=f"{platform}_uptime_pct",
    )


def daily_active_users(
    session: Session,
    platform: str = "web",
    window_days: int = 1,
) -> ToolResult:
    """Distinct signed-in visitors holding sessions in the window."""
    _validated(platform)
    if not isinstance(window_days, int) or not 1 <= window_days <= MAX_DAU_WINDOW_DAYS:
        raise ToolError(f"window_days must be 1..{MAX_DAU_WINDOW_DAYS}, got {window_days!r}")
    end = _utc_now_naive()
    start = end - timedelta(days=window_days)
    dau = mqueries.active_users(session, start, end, platform)
    return ToolResult(
        data=int(dau),
        row_count=1,
        metric_key=f"{platform}_dau_{window_days}d",
    )


REGISTRY = ToolRegistry()
REGISTRY.register(
    ToolSpec(name="health_latest", subsections=frozenset({"A_W_HEALTH"})),
    health_latest,
)
REGISTRY.register(
    ToolSpec(name="health_uptime_pct", subsections=frozenset({"A_W_HEALTH"})),
    health_uptime_pct,
)
REGISTRY.register(
    ToolSpec(
        name="daily_active_users",
        subsections=frozenset({"B_W_ACTIVITY", "B_A_ACTIVITY"}),
    ),
    daily_active_users,
)

# Phase 5: the curated aggregate tools - counts and summaries only.
register_aggregates(REGISTRY)

# The alerting tools: what is firing, what is watched, where it would go.
from mcp.alerting import register_alerting  # noqa: E402 - avoids an import cycle

register_alerting(REGISTRY)
