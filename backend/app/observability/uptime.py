"""Reader-derived web uptime from `health_metric` sample coverage.

Replaces the blackbox-exporter prober (`docs/MCP_MIGRATION_PLAN.md` parity
row 8). A process cannot write rows during its own downtime - there is no row
to hold the missing intervals, which is exactly why the self-reported-uptime
shortcut was rejected in `infrastructure/health.py`. So uptime is computed
when the numbers are *read*, from coverage: over a window, `health_metric`
should hold one row per sampling interval. Each missing run is either a
failed sample or a period in which the API was down; the ratio is the only
availability statement this deployment can make without putting a second,
external prober back.

Limitations, stated plainly:

- A reader computes this only while the database is reachable. An outage that
  is still under way is not visible yet; the *next* read reports it as the
  fraction of the window that lost coverage.
- Coverage is anchored to the platform's oldest surviving sample, so bootstrap
  time (sampler just enabled, retention prune) does not masquerade as
  downtime.
- No rows at all and no older sample means "cannot say" (`None`), never 0% -
  the same None-vs-zero discipline the rest of the pipeline obeys.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, func, select

from core.config import settings
from features.monitoring.domain.models import HealthMetric


def coverage_pct(
    session: Session,
    *,
    platform: str = "web",
    start: datetime,
    end: datetime,
    interval_s: Optional[int] = None,
) -> Optional[float]:
    """Fraction of `window` covered by health samples, or None when unknowable.

    100.0 means every expected interval holds a row; less means some did not.
    A large gap (the process was down the whole window, and older rows from
    before `start` prove the sampler was already expected) reads as 0.0.
    """
    if end <= start:
        return None
    interval = interval_s if interval_s is not None else settings.health_sample_interval_s
    if interval <= 0:
        return None

    first_in_window = session.exec(
        select(func.min(HealthMetric.ts)).where(
            HealthMetric.ts >= start,
            HealthMetric.ts < end,
            HealthMetric.platform == platform,
        )
    ).one()
    rows = session.exec(
        select(func.count()).where(
            HealthMetric.ts >= start,
            HealthMetric.ts < end,
            HealthMetric.platform == platform,
        )
    ).one() or 0

    if rows == 0 or not first_in_window:
        # Distinguish "no data at all" (the sampler may not be enabled yet)
        # from "the sampler was already running before this window, and then
        # every interval went missing" - the latter is a 0, the former None.
        first_ever = session.exec(
            select(func.min(HealthMetric.ts)).where(HealthMetric.platform == platform)
        ).one()
        if first_ever and first_ever < start:
            return 0.0
        return None

    # Expected samples from the anchor row onward: the first row itself covers
    # nothing, every interval after it can be missing.
    span = (end - first_in_window).total_seconds()
    expected = max(1, round(span / interval))
    return round(min(100.0, rows / expected * 100.0), 2)
