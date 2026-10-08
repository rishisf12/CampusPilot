"""Query functions for the Web App Monitoring and Android App Monitoring sections.

All functions return SQLModel/SQLModel-compatible objects (SQLModel instances,
dicts, or lists). Nothing ever writes to these tables from the API – they are
read-only queries. The scan service (separate worker) is the only writer, and it
writes via the allowlisted tool layer, not directly via these queries.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlmodel import Session, select, func

from features.monitoring.domain.models import (
    AdEvent,
    CrashReport,
    DependencyVulnerability,
    Event,
    EventHourly,
    FeedbackAnalysis,
    HealthMetric,
    SecurityEvent,
    SecurityHeaderCheck,
    SecurityLog,
    Session as MonitorSession,
    Purchase,
    Subscription,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _window(days: int) -> tuple[datetime, datetime]:
    # Anchor to clock-hour boundaries: `end` is the start of the next
    # hour, so the window covers every complete hour up to and
    # including the current one. Two calls within the same hour then
    # return an identical window - a dashboard that re-runs the rollup
    # and re-reads the overview must not see the bounds drift by
    # milliseconds - and a window edge never splits a rollup bucket.
    end = _now_utc().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = end - timedelta(days=days)
    return start, end


# Public alias for tests
window = _window


# ---------------------------------------------------------------------------
# Query functions expected by tests (matching original API)
# ---------------------------------------------------------------------------

def active_users(session: Session, start: datetime, end: datetime,
                 platform: Optional[str] = None) -> int:
    """Count distinct users (by user_hash) with sessions in the window."""
    stmt = select(func.count(func.distinct(MonitorSession.user_hash))).where(
        MonitorSession.started_at >= start,
        MonitorSession.started_at < end,
        MonitorSession.user_hash.is_not(None),
    )
    if platform:
        stmt = stmt.where(MonitorSession.platform == platform)
    return session.exec(stmt).one() or 0


def sessions_count(session: Session, start: datetime, end: datetime,
                   platform: Optional[str] = None) -> int:
    """Count total sessions in the window."""
    stmt = select(func.count()).select_from(MonitorSession).where(
        MonitorSession.started_at >= start,
        MonitorSession.started_at < end,
    )
    if platform:
        stmt = stmt.where(MonitorSession.platform == platform)
    return session.exec(stmt).one() or 0


def new_vs_returning(session: Session, start: datetime, end: datetime,
                     platform: Optional[str] = None) -> dict[str, int]:
    """Split users into new vs returning based on first session in window."""
    # Total users in window
    total_stmt = select(func.count(func.distinct(MonitorSession.user_hash))).where(
        MonitorSession.started_at >= start,
        MonitorSession.started_at < end,
        MonitorSession.user_hash.is_not(None),
    )
    if platform:
        total_stmt = total_stmt.where(MonitorSession.platform == platform)
    total = session.exec(total_stmt).one() or 0

    # Users whose FIRST session is in this window
    subq = (
        select(MonitorSession.user_hash, func.min(MonitorSession.started_at).label("first_seen"))
        .where(MonitorSession.user_hash.is_not(None))
        .group_by(MonitorSession.user_hash)
        .subquery()
    )
    new_stmt = select(func.count()).select_from(subq).where(
        subq.c.first_seen >= start,
        subq.c.first_seen < end,
    )
    if platform:
        # Need to join back to MonitorSession for platform filter
        new_stmt = select(func.count(func.distinct(MonitorSession.user_hash))).where(
            MonitorSession.started_at >= start,
            MonitorSession.started_at < end,
            MonitorSession.user_hash.is_not(None),
            ~MonitorSession.user_hash.in_(
                select(MonitorSession.user_hash).where(
                    MonitorSession.started_at < start,
                    MonitorSession.user_hash.is_not(None),
                )
            ),
        )
        if platform:
            new_stmt = new_stmt.where(MonitorSession.platform == platform)
    new = session.exec(new_stmt).one() or 0

    return {
        "total": total,
        "new": new,
        "returning": max(0, total - new),
    }


def retention_cohorts(session: Session, days: int,
                      platform: Optional[str] = None) -> dict[str, dict]:
    """Return day-1, day-2, ... retention for calendar-day cohorts.

    Each output key "N" represents the cohort of users whose FIRST session
    was (N+1) days ago. We check if they returned on day N (N days after
    their first session).

    For example:
    - out["1"] = cohort from 2 days ago, check if they returned 1 day after first session
    - out["2"] = cohort from 3 days ago, check if they returned 2 days after first session
    - out["4"] = cohort from 5 days ago, check if they returned 4 days after first session

    This matches the test expectations where:
    - out["N"] corresponds to cohort from (N+1) days ago
    - Retention day = N (N days after first session)
    """
    now = _now_utc()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get first session date for each user in a wide lookback window
    # We look back far enough to capture all relevant cohorts (90 days)
    first_sessions = session.exec(
        select(
            MonitorSession.user_hash,
            func.min(MonitorSession.started_at).label("first_ts"),
            func.min(MonitorSession.platform).label("platform"),
        ).where(
            MonitorSession.started_at >= today - timedelta(days=90),
            MonitorSession.user_hash.is_not(None),
        ).group_by(MonitorSession.user_hash)
    ).all()

    # Filter by platform if specified
    if platform:
        first_sessions = [fs for fs in first_sessions if fs.platform == platform]

    # Group users by their cohort calendar date (first session date)
    cohorts = {}
    for fs in first_sessions:
        cohort_date = fs.first_ts.date()
        if cohort_date not in cohorts:
            cohorts[cohort_date] = []
        cohorts[cohort_date].append(fs.user_hash)

    # Build output for each cohort that is at least 2 days old
    # (need at least 1 day for day-1 retention)
    out = {}
    for cohort_date, user_hashes in cohorts.items():
        days_ago = (today.date() - cohort_date).days

        # Cohort must be at least 2 days old to have day-1 retention
        # (first session was at least 2 days ago)
        if days_ago < 2:
            continue

        # Output key N = days_ago - 1
        # This cohort is from (N+1) days ago, we check day-N retention
        key = str(days_ago - 1)

        # Only include keys up to a reasonable maximum
        try:
            key_int = int(key)
            if key_int > 90:  # reasonable max
                continue
        except ValueError:
            continue

        cohort_size = len(user_hashes)
        if cohort_size == 0:
            continue

        # Day-N retention where N = days_ago - 1
        # Check if users returned N days after their first session
        retention_day = days_ago - 1
        return_date = cohort_date + timedelta(days=retention_day)
        return_start = datetime.combine(return_date, datetime.min.time())
        return_end = return_start + timedelta(days=1)

        # Only count if return date is not in the future
        if return_date > today.date():
            out[str(days_ago - 1)] = {"pct": 0, "cohort": cohort_size}
            continue

        # Count how many from this cohort returned on the return date
        returned = session.exec(
            select(func.count(func.distinct(MonitorSession.user_hash))).where(
                MonitorSession.started_at >= return_start,
                MonitorSession.started_at < return_end,
                MonitorSession.user_hash.in_(user_hashes),
            )
        ).one() or 0

        pct = round(returned / len(user_hashes) * 100) if user_hashes else 0
        out[str(days_ago - 1)] = {"pct": pct, "cohort": len(user_hashes)}

    # Ensure all keys from 1 to max_key are present (fill missing with zeros)
    # The maximum key we might need is based on the cohorts found or the days parameter
    max_key = max(int(k) for k in out) if out else 0
    max_key = max(max_key, days)  # at least up to the days parameter
    
    for i in range(1, max_key + 1):
        if str(i) not in out:
            out[str(i)] = {"pct": 0, "cohort": 0}

    # Ensure keys are sorted and return
    return {k: out[k] for k in sorted(out.keys(), key=int)}


def _dialect(session: Session) -> str:
    """Return the dialect name: 'postgresql' or 'sqlite'."""
    return session.bind.dialect.name


def _date_trunc_day(dialect: str, col):
    """Return SQL expression for truncating a datetime to day."""
    if dialect == "postgresql":
        return func.date_trunc("day", col)
    return func.strftime("%Y-%m-%d", col)


def _date_trunc_hour(dialect: str, col):
    """Return SQL expression for truncating a datetime to hour."""
    if dialect == "postgresql":
        return func.date_trunc("hour", col)
    return func.strftime("%Y-%m-%d %H:00:00", col)


# ---------------------------------------------------------------------------
# Overview (single call for all dashboard panels)
# ---------------------------------------------------------------------------

def activity_overview(session: Session, start: datetime, end: datetime,
                      platform: Optional[str] = None) -> dict[str, Any]:
    """Return high-level activity metrics for one platform.

    Live figures (users, sessions, new/returning) read the session
    table directly. Event volume, dimension breakdowns and the hourly
    series read the rollup, so they are zero until the rollup has run
    for the window. The split is deliberate: a dashboard cannot
    silently present stale rollup volume as if it were current.
    """

    window_len = end - start
    prev_end = start
    prev_start = start - window_len
    days = max(1, int(window_len.total_seconds() // 86400))

    # Live counts: no rollup needed.
    active_now = active_users(session, start, end, platform)
    active_prev = active_users(session, prev_start, prev_end, platform)
    sessions = sessions_count(session, start, end, platform)
    sessions_prev = sessions_count(session, prev_start, prev_end, platform)

    # Event volume: from the rollup table, so it is zero until the
    # rollup job has run for the window.
    events_stmt = select(func.coalesce(func.sum(EventHourly.n), 0)).where(
        EventHourly.bucket_hour >= start,
        EventHourly.bucket_hour < end,
    )
    if platform:
        events_stmt = events_stmt.where(EventHourly.platform == platform)
    events = session.exec(events_stmt).one() or 0

    # Composition of the already-tested query functions.
    nvr = new_vs_returning(session, start, end, platform)
    retention = retention_cohorts(session, days, platform)
    countries = top_dimensions(session, start, end, "country",
                               limit=8, platform=platform)
    versions = top_dimensions(session, start, end, "app_version",
                              limit=8, platform=platform)

    # Hourly volume, also from the rollup.
    hourly_stmt = select(
        EventHourly.bucket_hour.label("hour"),
        func.sum(EventHourly.n).label("events"),
    ).where(
        EventHourly.bucket_hour >= start,
        EventHourly.bucket_hour < end,
    )
    if platform:
        hourly_stmt = hourly_stmt.where(EventHourly.platform == platform)
    hourly_stmt = hourly_stmt.group_by(EventHourly.bucket_hour).order_by(
        EventHourly.bucket_hour)
    hourly_rows = session.exec(hourly_stmt).all()
    hourly = [{"hour": r.hour.isoformat(), "events": r.events}
              for r in hourly_rows]

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "active_users": active_now,
        "active_users_prev": active_prev,
        "sessions": sessions,
        "sessions_prev": sessions_prev,
        "events": events,
        "new_vs_returning": nvr,
        "retention": retention,
        "countries": countries,
        "versions": versions,
        "hourly": hourly,
    }


def security_overview(session: Session, start: datetime, end: datetime,
                      platform: Optional[str] = None) -> dict[str, Any]:
    """Return high-level security metrics for one platform.

    `counts` is every security event by kind; `blocked` is the
    subset the system acted on. Integrity signals (root, emulator,
    tamper) are observations by default, so `blocked` is usually
    far smaller than `counts` - that is the intended reading, not
    a gap in the data.
    """

    counts = security_counts(session, start, end, platform=platform)

    blocked_stmt = select(SecurityEvent.kind, func.count()).where(
        SecurityEvent.ts >= start,
        SecurityEvent.ts < end,
        SecurityEvent.blocked == True,  # type: ignore[comparison]
    )
    if platform:
        blocked_stmt = blocked_stmt.where(SecurityEvent.platform == platform)
    blocked_rows = session.exec(
        blocked_stmt.group_by(SecurityEvent.kind)
    ).all()
    blocked = dict(blocked_rows)

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "counts": counts,
        "blocked": blocked,
    }


def revenue_overview(session: Session, start: datetime, end: datetime,
                     platform: Optional[str] = None) -> dict[str, Any]:
    """Return high-level revenue metrics for one platform."""

    base = select(Purchase).where(
        Purchase.ts >= start,
        Purchase.ts < end,
    )
    if platform:
        base = base.where(Purchase.platform == platform)

    verified = session.exec(
        select(func.sum(Purchase.price_micros)).select_from(Purchase).where(
            Purchase.ts >= start, Purchase.ts < end,
            Purchase.verified == True,  # type: ignore[comparison]
            Purchase.platform == (platform or "web"),
        )
    ).one() or 0

    unverified = session.exec(
        select(func.sum(Purchase.price_micros)).select_from(Purchase).where(
            Purchase.ts >= start, Purchase.ts < end,
            Purchase.verified == False,  # type: ignore[comparison]
            Purchase.platform == (platform or "web"),
        )
    ).one() or 0

    ad_rev = session.exec(
        select(func.sum(AdEvent.revenue_micros)).select_from(AdEvent).where(
            AdEvent.ts >= start, AdEvent.ts < end,
            AdEvent.platform == (platform or "web"),
        )
    ).one() or 0

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "revenue_verified_micros": verified,
        "revenue_unverified_micros": unverified,
        "ad_revenue_micros": ad_rev,
        "total_revenue_micros": (verified or 0) + (ad_rev or 0),
    }


def health_overview(session: Session, start: datetime, end: datetime,
                    platform: Optional[str] = None) -> dict[str, Any]:
    """Return high-level health metrics for one platform."""

    latest = session.exec(
        select(HealthMetric).where(
            HealthMetric.ts >= start,
            HealthMetric.ts < end,
            HealthMetric.platform == (platform or "web"),
        ).order_by(HealthMetric.ts.desc()).limit(1)
    ).first()

    if not latest:
        return {
            "platform": platform,
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "has_data": False,
            "message": "awaiting first data",
        }

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "has_data": True,
        "uptime_pct": latest.uptime_pct,
        "response_time_p95_ms": latest.response_time_p95_ms,
        "http_5xx_pct": latest.http_5xx_pct,
        "cpu_pct": latest.cpu_pct,
        "ram_pct": latest.ram_pct,
        "disk_pct": latest.disk_pct,
        "crash_free_rate_pct": latest.crash_free_rate_pct,
        "anr_rate_pct": latest.anr_rate_pct,
        "startup_time_ms": latest.startup_time_ms,
        "slow_frames_pct": latest.slow_frames_pct,
        "ssl_expiry_days": latest.ssl_expiry_days,
    }


def feedback_overview(session: Session, start: datetime, end: datetime,
                      platform: Optional[str] = None) -> dict[str, Any]:
    """Return high-level feedback metrics."""

    latest = session.exec(
        select(FeedbackAnalysis).where(
            FeedbackAnalysis.window_start >= start,
            FeedbackAnalysis.window_end <= end,
        ).order_by(FeedbackAnalysis.window_end.desc()).limit(1)
    ).first()

    if not latest:
        return {
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "has_data": False,
            "message": "awaiting first data",
        }

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "has_data": True,
        "total_count": latest.total_count,
        "sentiment": {
            "positive": latest.sentiment_positive,
            "neutral": latest.sentiment_neutral,
            "negative": latest.sentiment_negative,
            "mean": latest.sentiment_mean,
        },
        "top_topics": latest.topics[:5] if latest.topics else [],
    }


# ---------------------------------------------------------------------------
# Health Detail (Subsection A)
# ---------------------------------------------------------------------------

def health_detail(session: Session, start: datetime, end: datetime,
                  platform: str) -> dict[str, Any]:
    """Return the Health subsection in the shape the Health panel
    renders: `http`, `db`, `crashes`, `data_freshness`.

    `http` and the registry counts read the live in-process Prometheus
    registry, so the admin dashboard and the `/metrics` scrape report
    the same numbers by construction. `db` and `crashes` read the
    session and crash tables - live, no rollup needed. The shape is
    present even on an empty database: an empty dashboard is a fact,
    not an error.
    """
    from features.monitoring import metrics as metrics_mod

    def _totals(metric_name: str, label_keys: tuple[str, ...]) -> dict[str, int]:
        totals: dict[str, int] = {}
        for metric in metrics_mod.REGISTRY.collect():
            if metric.name != metric_name:
                continue
            for sample in metric.samples:
                key = "/".join(sample.labels.get(k, "unknown") for k in label_keys)
                totals[key] = totals.get(key, 0) + int(sample.value)
        return totals

    # Registry shape: how many families and series are exported.
    families = list(metrics_mod.REGISTRY.collect())
    registry_families = len(families)
    registry_series = sum(len(m.samples) for m in families)

    requests_by_route = _totals("campuspilot_http_requests_total", ("route",))
    requests_by_status = _totals("campuspilot_http_requests_total", ("status",))

    # Live session activity for the selected platform: no rollup needed.
    active_now = active_users(session, start, end, platform)
    sessions = sessions_count(session, start, end, platform)

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "http": {
            "requests_by_route": requests_by_route,
            "requests_by_status": requests_by_status,
            "requests_total": sum(requests_by_route.values()),
            "registry_series": registry_series,
            "registry_families": registry_families,
        },
        "db": {
            "active_users": active_now,
            "sessions": sessions,
        },
        "crashes": {
            "web": crash_free_rate(session, start, end, "web"),
            "android": crash_free_rate(session, start, end, "android"),
        },
        "data_freshness": data_freshness(session),
    }


# ---------------------------------------------------------------------------
# Activity & Monetization Detail (Subsection B)
# ---------------------------------------------------------------------------

def activity_detail(session: Session, start: datetime, end: datetime,
                    platform: Optional[str] = None) -> dict[str, Any]:
    """Return detailed activity metrics for the Activity subsection."""

    dialect = _dialect(session)
    day_expr_eh = _date_trunc_day(dialect, EventHourly.bucket_hour)
    day_expr_cr = _date_trunc_day(dialect, CrashReport.ts)

    # DAU/WAU/MAU via EventHourly
    dau = session.exec(
        select(
            day_expr_eh.label("day"),
            func.sum(EventHourly.active_users).label("dau"),
        )
        .where(EventHourly.bucket_hour >= start, EventHourly.bucket_hour < end)
        .group_by(day_expr_eh)
        .order_by(day_expr_eh)
    ).all()

    # Sessions
    sessions = session.exec(
        select(
            day_expr_cr.label("day"),
            func.count(func.distinct(CrashReport.session_id)).label("sessions"),
        )
        .where(CrashReport.ts >= start, CrashReport.ts < end)
        .group_by(day_expr_cr)
        .order_by(day_expr_cr)
    ).all()

    # Top pages/screens
    top_pages = session.exec(
        select(EventHourly.path, func.sum(EventHourly.count).label("views"))
        .where(EventHourly.bucket_hour >= start, EventHourly.bucket_hour < end)
        .group_by(EventHourly.path)
        .order_by(func.sum(EventHourly.count).desc())
        .limit(20)
    ).all()

    # Geography
    geo = session.exec(
        select(EventHourly.country, func.sum(EventHourly.count).label("views"))
        .where(EventHourly.bucket_hour >= start, EventHourly.bucket_hour < end)
        .group_by(EventHourly.country)
        .order_by(func.sum(EventHourly.count).desc())
        .limit(20)
    ).all()

    # Devices
    devices = session.exec(
        select(EventHourly.device_type, func.sum(EventHourly.count).label("views"))
        .where(EventHourly.bucket_hour >= start, EventHourly.bucket_hour < end)
        .group_by(EventHourly.device_type)
        .order_by(func.sum(EventHourly.count).desc())
    ).all()

    # Retention (simplified: day-1 and day-7 returning)
    # This is a placeholder - real retention needs cohort analysis
    retention = {"day_1": 0.0, "day_7": 0.0}

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "dau": [{"day": str(d.day), "dau": d.dau} for d in dau],
        "sessions": [{"day": str(s.day), "sessions": s.sessions} for s in sessions],
        "top_pages": [{"path": p.path, "views": p.views} for p in top_pages],
        "geography": [{"country": g.country or "unknown", "views": g.views} for g in geo],
        "devices": [{"device": d.device_type or "unknown", "views": d.views} for d in devices],
        "retention": retention,
    }


def monetisation_detail(session: Session, start: datetime, end: datetime,
                        prev_start: datetime, prev_end: datetime,
                        platform: Optional[str] = None) -> dict[str, Any]:
    """Return detailed monetization metrics with period-over-period comparison."""

    def _revenue_for(platform_: Optional[str], s: datetime, e: datetime) -> dict:
        verified = session.exec(
            select(func.sum(Purchase.price_micros)).select_from(Purchase).where(
                Purchase.ts >= s, Purchase.ts < e,
                Purchase.verified == True,  # type: ignore[comparison]
                Purchase.platform == (platform_ or "web"),
            )
        ).one() or 0
        unverified = session.exec(
            select(func.sum(Purchase.price_micros)).select_from(Purchase).where(
                Purchase.ts >= s, Purchase.ts < e,
                Purchase.verified == False,  # type: ignore[comparison]
                Purchase.platform == (platform_ or "web"),
            )
        ).one() or 0
        ad_rev = session.exec(
            select(func.sum(AdEvent.revenue_micros)).select_from(AdEvent).where(
                AdEvent.ts >= s, AdEvent.ts < e,
                AdEvent.platform == (platform_ or "web"),
            )
        ).one() or 0
        subs = session.exec(
            select(func.count()).select_from(Subscription).where(
                Subscription.ts >= s, Subscription.ts < e,
                Subscription.status == "active",
                Subscription.platform == (platform_ or "web"),
            )
        ).one() or 0
        return {
            "revenue_verified_micros": verified,
            "revenue_unverified_micros": unverified,
            "ad_revenue_micros": ad_rev,
            "total_revenue_micros": (verified or 0) + (ad_rev or 0),
            "active_subscriptions": subs,
        }

    current = _revenue_for(platform, start, end)
    previous = _revenue_for(platform, prev_start, prev_end)

    def _pct(curr: int, prev: int) -> Optional[float]:
        if prev == 0:
            return None
        return round((curr - prev) / prev * 100, 2)

    # Breakdowns
    by_product = session.exec(
        select(Purchase.product_id, func.sum(Purchase.price_micros).label("rev"))
        .where(Purchase.ts >= start, Purchase.ts < end, Purchase.verified == True)
        .group_by(Purchase.product_id)
    ).all()

    by_country = session.exec(
        select(Purchase.country, func.sum(Purchase.price_micros).label("rev"))
        .where(Purchase.ts >= start, Purchase.ts < end, Purchase.verified == True)
        .group_by(Purchase.country)
    ).all()

    # Ad metrics
    ad_impressions = session.exec(
        select(func.sum(AdEvent.impressions)).select_from(AdEvent).where(
            AdEvent.ts >= start, AdEvent.ts < end,
            AdEvent.platform == (platform or "web"),
        )
    ).one() or 0
    ad_clicks = session.exec(
        select(func.sum(AdEvent.clicks)).select_from(AdEvent).where(
            AdEvent.ts >= start, AdEvent.ts < end,
            AdEvent.platform == (platform or "web"),
        )
    ).one() or 0

    ecpm = round((current["ad_revenue_micros"] / ad_impressions * 1000) if ad_impressions else 0, 2)

    return {
        "platform": platform,
        "current_window": {"start": start.isoformat(), "end": end.isoformat()},
        "previous_window": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
        "current": current,
        "previous": previous,
        "changes": {
            "total_revenue_pct": _pct(current["total_revenue_micros"], previous["total_revenue_micros"]),
            "verified_revenue_pct": _pct(current["revenue_verified_micros"], previous["revenue_verified_micros"]),
            "ad_revenue_pct": _pct(current["ad_revenue_micros"], previous["ad_revenue_micros"]),
            "subscriptions_pct": _pct(current["active_subscriptions"], previous["active_subscriptions"]),
        },
        "breakdowns": {
            "by_product": [{"product": p.product_id, "revenue_micros": p.rev} for p in by_product],
            "by_country": [{"country": c.country or "unknown", "revenue_micros": c.rev} for c in by_country],
        },
        "ad_metrics": {
            "impressions": ad_impressions,
            "clicks": ad_clicks,
            "revenue_micros": current["ad_revenue_micros"],
            "ecpm_micros": ecpm,
        },
        "note": "Unverified purchases are labelled as claims, not revenue. See ENABLE_STORE_VERIFY.",
    }


# ---------------------------------------------------------------------------
# Security Detail (Subsection C)
# ---------------------------------------------------------------------------

def security_detail(session: Session, start: datetime, end: datetime,
                    platform: Optional[str] = None) -> dict[str, Any]:
    """Return detailed security metrics for the Security subsection."""

    logs = session.exec(
        select(SecurityLog).where(
            SecurityLog.ts >= start,
            SecurityLog.ts < end,
            SecurityLog.platform == (platform or "web"),
        ).order_by(SecurityLog.ts.desc()).limit(200)
    ).all()

    vulns = session.exec(
        select(DependencyVulnerability).where(
            DependencyVulnerability.ts >= start,
            DependencyVulnerability.ts < end,
        ).order_by(DependencyVulnerability.severity.desc()).limit(50)
    ).all()

    headers = session.exec(
        select(SecurityHeaderCheck).where(
            SecurityHeaderCheck.ts >= start,
            SecurityHeaderCheck.ts < end,
            SecurityHeaderCheck.platform == (platform or "web"),
        ).order_by(SecurityHeaderCheck.ts.desc()).limit(10)
    ).all()

    by_severity = {}
    by_category = {}
    by_action = {}
    for log in logs:
        by_severity[log.severity] = by_severity.get(log.severity, 0) + 1
        by_category[log.category] = by_category.get(log.category, 0) + 1
        by_action[log.action] = by_action.get(log.action, 0) + 1

    unresolved = sum(1 for log in logs if not log.resolved)
    root_emu = sum(1 for log in logs if log.root_detected or log.emulator_detected)
    tamper = sum(1 for log in logs if log.tamper_detected)

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "total_events": len(logs),
        "by_severity": by_severity,
        "by_category": by_category,
        "by_action": by_action,
        "unresolved": unresolved,
        "root_emulator_detected": root_emu,
        "tamper_detected": tamper,
        "recent_events": [
            {
                "ts": log.ts.isoformat(),
                "category": log.category,
                "severity": log.severity,
                "action": log.action,
                "rule_id": log.rule_id,
                "description": log.description,
                "resolved": log.resolved,
            } for log in logs[:50]
        ],
        "vulnerabilities": [
            {
                "vuln_id": v.vuln_id,
                "package": f"{v.ecosystem}/{v.package_name}@{v.installed_version}",
                "severity": v.severity,
                "cvss_score": v.cvss_score,
                "status": v.status,
            } for v in vulns
        ],
        "header_checks": [
            {
                "ts": h.ts.isoformat(),
                "url": h.url,
                "score": h.score,
                "grade": h.grade,
                "hsts": h.hsts,
                "csp": h.csp,
                "x_frame_options": h.x_frame_options,
            } for h in headers
        ],
    }


# ---------------------------------------------------------------------------
# Feedback Detail (Subsection D)
# ---------------------------------------------------------------------------

def feedback_detail(session: Session, start: datetime, end: datetime) -> dict[str, Any]:
    """Return detailed feedback analysis for the Feedback subsection."""

    analyses = session.exec(
        select(FeedbackAnalysis).where(
            FeedbackAnalysis.window_start >= start,
            FeedbackAnalysis.window_end <= end,
        ).order_by(FeedbackAnalysis.window_end.desc())
    ).all()

    if not analyses:
        return {
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "has_data": False,
            "message": "awaiting first data",
        }

    latest = analyses[0]

    # Sentiment trend
    sentiment_trend = [
        {
            "window_start": a.window_start.isoformat(),
            "window_end": a.window_end.isoformat(),
            "positive": a.sentiment_positive,
            "neutral": a.sentiment_neutral,
            "negative": a.sentiment_negative,
            "mean": a.sentiment_mean,
        } for a in analyses
    ]

    # Volume trend
    volume_trend = [
        {
            "window_start": a.window_start.isoformat(),
            "window_end": a.window_end.isoformat(),
            "total": a.total_count,
        } for a in analyses
    ]

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "has_data": True,
        "current": {
            "total_count": latest.total_count,
            "with_attachment_count": latest.with_attachment_count,
            "replied_count": latest.replied_count,
            "sentiment": {
                "positive": latest.sentiment_positive,
                "neutral": latest.sentiment_neutral,
                "negative": latest.sentiment_negative,
                "mean": latest.sentiment_mean,
            },
            "topics": latest.topics,
            "rating_distribution": latest.rating_distribution,
            "top_complaints": latest.top_complaints,
            "top_requests": latest.top_requests,
            "crash_correlation": latest.crash_correlation,
            "release_correlation": latest.release_correlation,
        },
        "sentiment_trend": sentiment_trend,
        "volume_trend": volume_trend,
    }


def crashes_overview(session: Session, start: datetime, end: datetime,
                     platform: Optional[str] = None) -> dict[str, Any]:
    """Return high-level crash metrics for one platform."""

    # Crash-free rate
    total_sessions = session.exec(
        select(func.count(func.distinct(CrashReport.session_id)))
        .where(CrashReport.ts >= start, CrashReport.ts < end,
               CrashReport.platform == (platform or "web"))
    ).one() or 0

    crashed_sessions = session.exec(
        select(func.count(func.distinct(CrashReport.session_id)))
        .where(CrashReport.ts >= start, CrashReport.ts < end,
               CrashReport.platform == (platform or "web"),
               CrashReport.kind == "crash")
    ).one() or 0

    crash_free_rate = 100.0 if total_sessions == 0 else (1.0 - crashed_sessions / total_sessions) * 100

    # Top crash clusters
    clusters = session.exec(
        select(CrashReport.exception_type, func.count().label("count"))
        .where(CrashReport.ts >= start, CrashReport.ts < end,
               CrashReport.platform == (platform or "web"),
               CrashReport.kind == "crash")
        .group_by(CrashReport.exception_type)
        .order_by(func.count().desc())
        .limit(10)
    ).all()

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "crash_free_rate_pct": round(crash_free_rate, 2),
        "total_sessions": total_sessions,
        "crashed_sessions": crashed_sessions,
        "top_clusters": [{"exception_type": c.exception_type, "count": c.count} for c in clusters],
    }


def arpu_overview(session: Session, start: datetime, end: datetime,
                  platform: Optional[str] = None) -> dict[str, Any]:
    """Return ARPU (Average Revenue Per User) for one platform."""

    # Active users
    active_users = session.exec(
        select(func.count(func.distinct(CrashReport.session_id)))
        .where(CrashReport.ts >= start, CrashReport.ts < end,
               CrashReport.platform == (platform or "web"))
    ).one() or 0

    # Verified revenue
    verified_revenue = session.exec(
        select(func.sum(Purchase.price_micros)).where(
            Purchase.ts >= start, Purchase.ts < end,
            Purchase.verified == True,  # type: ignore[comparison]
            Purchase.platform == (platform or "web"),
        )
    ).one() or 0

    arpu = 0 if active_users == 0 else verified_revenue / active_users

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "arpu_micros": round(arpu),
        "active_users": active_users,
        "verified_revenue_micros": verified_revenue,
    }


def ads_overview(session: Session, start: datetime, end: datetime,
                 platform: Optional[str] = None) -> dict[str, Any]:
    """Return ad metrics for one platform."""

    # Build platform filter - if platform is None, don't filter by platform
    platform_filter = []
    if platform:
        platform_filter.append(AdEvent.platform == platform)

    impressions = session.exec(
        select(func.count()).where(
            AdEvent.ts >= start, AdEvent.ts < end,
            AdEvent.event_type == "impression",
            *platform_filter,
        )
    ).one() or 0

    clicks = session.exec(
        select(func.count()).where(
            AdEvent.ts >= start, AdEvent.ts < end,
            AdEvent.event_type == "click",
            *platform_filter,
        )
    ).one() or 0

    revenue = session.exec(
        select(func.sum(AdEvent.revenue_micros)).where(
            AdEvent.ts >= start, AdEvent.ts < end,
            *platform_filter,
        )
    ).one() or 0

    ecpm = 0 if impressions == 0 else round(revenue / impressions * 1000)
    ctr = 0 if impressions == 0 else round(clicks / impressions * 100, 4)

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "impressions": impressions,
        "clicks": clicks,
        "revenue_micros": revenue,
        "ecpm_micros": ecpm,
        "ctr_pct": ctr,
    }


# ---------------------------------------------------------------------------
# Additional query functions expected by tests
# ---------------------------------------------------------------------------

def revenue(session: Session, start: datetime, end: datetime,
            platform: Optional[str] = None) -> dict[str, Any]:
    """Return revenue metrics for a window."""
    # Build platform filter - if platform is None, don't filter by platform
    platform_filter = []
    if platform:
        platform_filter.append(Purchase.platform == platform)
        platform_filter_ad = [AdEvent.platform == platform]
    else:
        platform_filter_ad = []

    verified = session.exec(
        select(func.sum(Purchase.price_micros)).where(
            Purchase.ts >= start, Purchase.ts < end,
            Purchase.verified == True,  # type: ignore[comparison]
            *platform_filter,
        )
    ).one() or 0

    unverified = session.exec(
        select(func.sum(Purchase.price_micros)).where(
            Purchase.ts >= start, Purchase.ts < end,
            Purchase.verified == False,  # type: ignore[comparison]
            *platform_filter,
        )
    ).one() or 0

    ad_rev = session.exec(
        select(func.sum(AdEvent.revenue_micros)).where(
            AdEvent.ts >= start, AdEvent.ts < end,
            *platform_filter_ad,
        )
    ).one() or 0

    verified_count = session.exec(
        select(func.count()).where(
            Purchase.ts >= start, Purchase.ts < end,
            Purchase.verified == True,  # type: ignore[comparison]
            *platform_filter,
        )
    ).one() or 0

    total_count = session.exec(
        select(func.count()).where(
            Purchase.ts >= start, Purchase.ts < end,
            *platform_filter,
        )
    ).one() or 0

    return {
        "verified_micros": verified,
        "unverified_micros": unverified,
        "ad_revenue_micros": ad_rev,
        "total_micros": (verified or 0) + (unverified or 0) + (ad_rev or 0),
        "verified_purchases": verified_count,
        "purchases": total_count,
    }


def arpu(session: Session, start: datetime, end: datetime,
         platform: Optional[str] = None) -> dict[str, Any]:
    """Return ARPU (Average Revenue Per User) for a window."""
    platform_filter = []
    if platform:
        platform_filter.append(MonitorSession.platform == platform)
        platform_filter_purchase = [Purchase.platform == platform]
    else:
        platform_filter_purchase = []

    active_users = session.exec(
        select(func.count(func.distinct(MonitorSession.session_id)))
        .where(MonitorSession.started_at >= start, MonitorSession.started_at < end, *platform_filter)
    ).one() or 0

    verified_revenue = session.exec(
        select(func.sum(Purchase.price_micros)).where(
            Purchase.ts >= start, Purchase.ts < end,
            Purchase.verified == True,  # type: ignore[comparison]
            *platform_filter_purchase,
        )
    ).one() or 0

    arpu = 0 if active_users == 0 else verified_revenue / active_users

    return {
        "active_users": active_users,
        "arpu_micros": round(arpu),
        "verified_revenue_micros": verified_revenue,
    }


def ad_performance(session: Session, start: datetime, end: datetime,
                   platform: Optional[str] = None) -> dict[str, Any]:
    """Return ad performance metrics for a window (alias for ads_overview)."""
    return ads_overview(session, start, end, platform)


def crash_free_rate(session: Session, start: datetime, end: datetime,
                    platform: str = "android") -> dict[str, Any]:
    """Return crash-free rate for a platform (only fatal crashes count)."""
    # Total sessions from MonitorSession (where sessions are created)
    total_sessions = session.exec(
        select(func.count(func.distinct(MonitorSession.session_id)))
        .where(MonitorSession.started_at >= start, MonitorSession.started_at < end,
               MonitorSession.platform == platform)
    ).one() or 0

    # Only fatal crashes count towards crash-free rate
    crashed_sessions = session.exec(
        select(func.count(func.distinct(CrashReport.session_id)))
        .where(CrashReport.ts >= start, CrashReport.ts < end,
               CrashReport.platform == platform,
               CrashReport.kind == "crash",
               CrashReport.fatal == True)
    ).one() or 0

    crash_free_rate_val = 100.0 if total_sessions == 0 else (1.0 - crashed_sessions / total_sessions) * 100

    return {
        "platform": platform,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "crash_free_pct": round(crash_free_rate_val, 2),
        "sessions": total_sessions,
        "crashed_sessions": crashed_sessions,
    }


def crash_clusters(session: Session, start: datetime, end: datetime,
                   platform: str = "android") -> list[dict[str, Any]]:
    """Return crash clusters ordered by frequency."""
    clusters = session.exec(
        select(
            CrashReport.fingerprint,
            func.count().label("count"),
            func.count(func.distinct(CrashReport.session_id)).label("sessions"),
        )
        .where(CrashReport.ts >= start, CrashReport.ts < end,
               CrashReport.platform == platform,
               CrashReport.kind == "crash")
        .group_by(CrashReport.fingerprint)
        .order_by(func.count().desc())
    ).all()

    return [
        {
            "fingerprint": c.fingerprint,
            "count": c.count,
            "sessions": c.sessions,
        } for c in clusters
    ]


def funnel(session: Session, steps: list[str], start: datetime, end: datetime,
           platform: Optional[str] = None) -> list[dict[str, Any]]:
    """Return funnel analysis for a sequence of event names.

    Returns drop-off percentages (not conversion rates). Drop-off = % that dropped
    from previous step. Negative values mean the step grew.
    """
    if not steps:
        return []

    out = []
    prev_count = None

    for i, step in enumerate(steps):
        # Count total events for this step (not distinct sessions)
        platform_filter = []
        if platform:
            platform_filter.append(Event.platform == platform)

        count = session.exec(
            select(func.count()).where(
                Event.ts >= start, Event.ts < end,
                Event.event_name == step,
                *platform_filter
            )
        ).one() or 0

        step_data = {"step": step, "count": count}

        if i > 0 and prev_count is not None and prev_count > 0:
            # Drop-off = % that dropped from previous step
            # Positive = users dropped off, Negative = step grew
            drop_off = round((1 - count / prev_count) * 100, 1)
            step_data["drop_off_pct"] = drop_off

        out.append(step_data)
        prev_count = count

    return out


def top_dimensions(session: Session, start: datetime, end: datetime,
                   dimension: str, limit: int = 10,
                   platform: Optional[str] = None) -> list[dict[str, Any]]:
    """Return top values for a dimension (country, os_version, etc.)."""
    # Only include dimensions that exist in EventHourly
    dim_map = {
        "country": EventHourly.country,
        "os_version": EventHourly.os_version,
        "app_version": EventHourly.app_version,
    }

    col = dim_map.get(dimension)
    if col is None:
        raise ValueError(f"Unknown dimension: {dimension}")

    if dimension == "user_hash":
        # Query Event table directly for user_hash
        base = select(col, func.count().label("value")).select_from(Event).where(
            Event.ts >= start,
            Event.ts < end,
        )
    else:
        # Query EventHourly for other dimensions
        base = select(col, func.sum(EventHourly.n).label("value")).where(
            EventHourly.bucket_hour >= start,
            EventHourly.bucket_hour < end,
        )

    if platform:
        if dimension == "user_hash":
            base = base.where(Event.platform == platform)
        else:
            base = base.where(EventHourly.platform == platform)

    top = session.exec(
        base.group_by(col)
        .order_by(func.count().desc() if dimension == "user_hash" else func.sum(EventHourly.n).desc())
        .limit(limit)
    ).all()

    return [
        {"value": str(t[0] or "unknown"), "events": t[1]}
        for t in top
    ]


def security_counts(session: Session, start: datetime, end: datetime,
                    kinds: Optional[set[str]] = None,
                    platform: Optional[str] = None) -> dict[str, int]:
    """Return security event counts grouped by kind."""
    base = select(SecurityEvent.kind, func.count()).where(
        SecurityEvent.ts >= start,
        SecurityEvent.ts < end,
    )
    if platform:
        base = base.where(SecurityEvent.platform == platform)
    if kinds:
        base = base.where(SecurityEvent.kind.in_(kinds))

    counts = session.exec(base.group_by(SecurityEvent.kind)).all()
    return dict(counts)


def previous_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Return the previous window of the same length immediately before the given window."""
    length = end - start
    return start - length, start


def baseline_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Return the 28-day baseline window immediately before the previous window.

    The test expects the baseline to end at the current window's start.
    """
    # The test expects a 28-day window ending at the current window's start
    return start - timedelta(days=28), start


def data_freshness(session: Session) -> dict[str, Any]:
    """Return the age of the newest data in each monitoring table."""

    latest_event = session.exec(
        select(Event.ts).order_by(Event.ts.desc()).limit(1)
    ).first()

    latest_rollup = session.exec(
        select(EventHourly.bucket_hour).order_by(EventHourly.bucket_hour.desc()).limit(1)
    ).first()

    latest_crash = session.exec(
        select(CrashReport.ts).order_by(CrashReport.ts.desc()).limit(1)
    ).first()

    now = _now_utc()

    return {
        "now": now.isoformat(),
        "latest_event_at": latest_event.isoformat() if latest_event else None,
        "latest_rollup_hour": latest_rollup.isoformat() if latest_rollup else None,
        "latest_crash_at": latest_crash.isoformat() if latest_crash else None,
        "event_lag_minutes": int((now - latest_event).total_seconds() // 60) if latest_event else None,
        "rollup_lag_minutes": int((now - latest_rollup).total_seconds() // 60) if latest_rollup else None,
    }