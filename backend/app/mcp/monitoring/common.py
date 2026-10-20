"""Shared helpers for the monitoring tools.

Small things both `mcp.monitoring` and `mcp.monitoring.aggregates` need:
which platform labels are real, how far a window may reach, and how the
code spells "now" in a way that matches how the rows were written.
"""
from __future__ import annotations

from datetime import datetime, timezone

from mcp.core.registry import ToolError

#: `HealthMetric.platform` carries exactly these labels. Refusing anything
#: else beats answering a typo'd platform with an empty result that reads
#: like "no data yet".
PLATFORMS = frozenset({"web", "android"})

#: Widest defensible windows: uptime cannot outlive retention
#: (`health_retention_days=90`), and a year of DAU is the ceiling anyone asks
#: for once.
MAX_UPTIME_WINDOW_HOURS = 24 * 90
MAX_DAU_WINDOW_DAYS = 365

#: Aggregate windows stay shorter than the retention horizon on purpose: a
#: "last 90 days of failed logins by hour" is not a chart, it is a table
#: nobody reads.
MAX_AGGREGATE_WINDOW_HOURS = 24 * 30
MAX_AGGREGATE_WINDOW_DAYS = 90

#: How many rows an aggregate may return. The egress gate caps at 50; the
#: tools cap lower so the answer is a summary, not a table.
MAX_AGGREGATE_ROWS = 25


def validated_platform(platform: str) -> str:
    """Return the platform, or refuse a label that is not one of ours."""
    if platform not in PLATFORMS:
        raise ToolError(f"platform {platform!r} not in {sorted(PLATFORMS)}")
    return platform


def validated_window(value: int, *, name: str, low: int, high: int) -> int:
    """Return a window size, or refuse one outside the defensible range."""
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ToolError(f"{name} must be {low}..{high}, got {value!r}")
    return value


def utc_now_naive() -> datetime:
    """Naive-UTC, matching how the telemetry rows are written."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
