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

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import Session, func, select

from core.config import settings
from features.monitoring.domain.models import HealthMetric


@dataclass(frozen=True)
class CoverageDetail:
    """The coverage number, and the facts needed to explain it.

    A coverage of 40% means two very different things depending on *why*:

    - the process was not running for that time (the host was off, the
      service was stopped) — an availability fact about the deployment, not
      a fault in the service; or
    - the process **was** running and the sampler stopped reporting — a real
      defect, and the one that deserves an incident.

    The reader can tell them apart, because the reader is running *inside*
    the process: if the newest sample is old while the scan is being served,
    the sampler stalled. That distinction is what `sampler_stalled` carries.
    """

    coverage_pct: Optional[float]
    #: Samples found in the window.
    rows: int
    #: Samples the window should have held.
    expected: int
    #: Length of the window in seconds.
    span_s: int
    #: How long ago the newest sample was written, in seconds.
    newest_sample_age_s: Optional[int]
    #: True when the API is serving but the sampler is not reporting.
    sampler_stalled: bool
    #: How much of the window had no process running, in seconds.
    downtime_s: int


def coverage_detail(
    session: Session,
    *,
    platform: str = "web",
    start: datetime,
    end: datetime,
    interval_s: Optional[int] = None,
    now: Optional[datetime] = None,
) -> CoverageDetail:
    """Coverage, with the facts that explain it. See `CoverageDetail`."""
    interval = interval_s if interval_s is not None else settings.health_sample_interval_s
    span_s = int((end - start).total_seconds()) if end > start else 0
    if end <= start or interval <= 0:
        return CoverageDetail(None, 0, 0, span_s, None, False, 0)

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

    newest = session.exec(
        select(func.max(HealthMetric.ts)).where(HealthMetric.platform == platform)
    ).one()
    reference = now or datetime.utcnow()
    newest_age_s: Optional[int] = None
    if newest is not None:
        age = (reference - newest).total_seconds()
        newest_age_s = int(age)
    # The scan is being served by the API right now, so a newest sample that
    # is several intervals old means the sampler stopped, not the process.
    stalled = bool(
        newest is not None
        and newest_age_s is not None
        and newest_age_s > max(3 * interval, 300)
    )

    if rows == 0 or not first_in_window:
        # Distinguish "no data at all" (the sampler may not be enabled yet)
        # from "the sampler was already running before this window, and then
        # every interval went missing" - the latter is a 0, the former None.
        first_ever = session.exec(
            select(func.min(HealthMetric.ts)).where(HealthMetric.platform == platform)
        ).one()
        if first_ever and first_ever < start:
            return CoverageDetail(
                coverage_pct=0.0,
                rows=0,
                expected=0,
                span_s=span_s,
                newest_sample_age_s=newest_age_s,
                sampler_stalled=stalled,
                downtime_s=span_s,
            )
        return CoverageDetail(
            coverage_pct=None,
            rows=0,
            expected=0,
            span_s=span_s,
            newest_sample_age_s=newest_age_s,
            sampler_stalled=stalled,
            downtime_s=0,
        )

    # Expected samples from the anchor row onward: the first row itself covers
    # nothing, every interval after it can be missing.
    span = (end - first_in_window).total_seconds()
    expected = max(1, round(span / interval))
    coverage = round(min(100.0, rows / expected * 100.0), 2)
    return CoverageDetail(
        coverage_pct=coverage,
        rows=rows,
        expected=expected,
        span_s=span_s,
        newest_sample_age_s=newest_age_s,
        sampler_stalled=stalled,
        downtime_s=int(span_s * (1.0 - coverage / 100.0)),
    )


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
    return coverage_detail(
        session, platform=platform, start=start, end=end, interval_s=interval_s
    ).coverage_pct
