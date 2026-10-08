"""Hourly rollup job: Event -> EventHourly.

This is the *only* place that writes to EventHourly. It is idempotent:
for each hour bucket it deletes any existing row, then recomputes from
raw Event rows. Running it twice for the same window produces identical
results. No accumulation, no drift.

Design notes:
- Dimensions use empty string '' not NULL (PostgreSQL unique constraint
  compatibility). GROUP BY coalesce(col, '') handles both dialects.
- Raw events are high-cardinality (path, status, device, country). They
  expire after ROLLUP_RAW_RETENTION_DAYS. Rollups are small and permanent.
- Concurrency: one worker at a time. The caller (cron or /rollup endpoint)
  enforces this. Do not run two rollups concurrently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select, func, delete, text, Column
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.sql import expression

from core.config import get_settings
from features.monitoring.domain.models import Event, EventHourly


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hour_bucket(dt: datetime) -> datetime:
    """Return the hour bucket start for a given datetime."""
    return dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)


def _hour_bucket_expr(dialect: str):
    """Return a SQL expression that truncates Event.ts to hour bucket.

    Uses date_trunc for PostgreSQL, strftime for SQLite.
    """
    if dialect == "postgresql":
        return func.date_trunc("hour", Event.ts)
    else:
        # SQLite: strftime('%Y-%m-%d %H:00:00', ts)
        return func.strftime("%Y-%m-%d %H:00:00", Event.ts)


def _coalesce_dim(col: Column, dialect: str = ""):
    """Return COALESCE(col, '') for empty-string dimensions.

    Works the same on both dialects.
    """
    return func.coalesce(col, "")


def _aggregate_stmt(start: datetime, end: datetime, bucket_expr):
    """Return the SELECT statement for aggregating events into hourly buckets.

    The bucket_expr is a pre-built SQL expression for the hour bucket.
    This ensures the same expression object is used in both SELECT and GROUP BY,
    so bind parameters are shared (critical for PostgreSQL).
    """
    # Three dimensions to match test expectations: platform, event_name, app_version
    platform_coalesce = _coalesce_dim(Event.platform)
    event_name_coalesce = _coalesce_dim(Event.event_name)
    app_version_coalesce = _coalesce_dim(Event.app_version)

    return (
        select(
            bucket_expr.label("bucket"),
            platform_coalesce.label("platform"),
            event_name_coalesce.label("event_name"),
            app_version_coalesce.label("app_version"),
            func.count().label("n"),
        )
        .where(Event.ts >= start, Event.ts < end)
        .group_by(
            bucket_expr,
            platform_coalesce,
            event_name_coalesce,
            app_version_coalesce,
        )
        .order_by(bucket_expr)
    )


def rollup(session: Session, lookback_hours: int = 48, now: datetime | None = None) -> dict[str, Any]:
    """Recompute EventHourly for the last `lookback_hours` hours.

    Args:
        session: SQLModel session
        lookback_hours: How many hours back to recompute (default 48h)
        now: Optional fixed "now" for testing (defaults to current UTC time)

    Returns:
        Dict with summary: start, end, buckets, rows_written, events_scanned
    """
    settings = get_settings()
    if now is None:
        now = _now_utc()
    # Include the current hour by using the NEXT hour boundary as end
    end = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=lookback_hours)

    # Detect dialect
    dialect_name = session.bind.dialect.name  # "postgresql" or "sqlite"
    bucket_expr = _hour_bucket_expr(dialect_name)

    # First, delete ALL EventHourly rows in the window
    # This ensures stale buckets (no longer backed by raw events) are dropped
    session.exec(
        delete(EventHourly).where(
            EventHourly.bucket_hour >= start,
            EventHourly.bucket_hour < end,
        )
    )

    # Find all hours that have raw events in this window
    raw = session.exec(
        select(
            bucket_expr.label("bucket"),
            func.count().label("event_count"),
        )
        .where(Event.ts >= start, Event.ts < end)
        .group_by(bucket_expr)
        .order_by(bucket_expr)
    ).all()

    if not raw:
        session.commit()
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "buckets": 0,
            "rows_written": 0,
            "events_scanned": 0,
        }

    total_events = 0
    rows_written = 0

    for bucket, event_count in raw:
        # bucket may be a string (SQLite strftime) or datetime (PostgreSQL date_trunc)
        if isinstance(bucket, str):
            bucket_dt = datetime.fromisoformat(bucket)
        else:
            bucket_dt = bucket

        # Get all dimension combinations for this hour
        # Use the same bucket expression comparison as the raw query
        details = session.exec(
            select(
                func.count().label("n"),
                func.coalesce(Event.platform, "").label("platform"),
                func.coalesce(Event.event_name, "").label("event_name"),
                func.coalesce(Event.app_version, "").label("app_version"),
                func.coalesce(Event.os_version, "").label("os_version"),
                func.coalesce(Event.country, "").label("country"),
            )
            .where(bucket_expr == bucket)
            .group_by(
                func.coalesce(Event.platform, ""),
                func.coalesce(Event.event_name, ""),
                func.coalesce(Event.app_version, ""),
                func.coalesce(Event.os_version, ""),
                func.coalesce(Event.country, ""),
            )
        ).all()

        for d in details:
            row = EventHourly(
                bucket_hour=bucket_dt,
                platform=d.platform,
                event_name=d.event_name,
                app_version=d.app_version,
                os_version=d.os_version,
                country=d.country,
                n=d.n,
            )
            session.add(row)
            total_events += d.n
            rows_written += 1

    session.commit()

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "buckets": len(raw),
        "rows_written": rows_written,
        "events_scanned": total_events,
    }


def rollup_full_recompute(session: Session, days: int = 90, now: datetime | None = None) -> dict[str, Any]:
    """Full recompute of last N days (for backfill/correction)."""
    return rollup(session, lookback_hours=days * 24, now=now)


def prune(session: Session, now: datetime | None = None, retention_days: int = 90) -> dict[str, int]:
    """Delete raw Event rows older than retention_days.

    Rollup rows are never deleted by this function.
    """
    if now is None:
        now = _now_utc()
    cutoff = now - timedelta(days=retention_days)
    result = session.exec(delete(Event).where(Event.ts < cutoff))
    session.commit()
    return {"raw_events_deleted": result.rowcount}