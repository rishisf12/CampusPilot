"""Sample the API's own Prometheus instruments into `health_metric` rows.

This is the only writer of `health_metric`. Before it existed the table, the
queries, the API and the Health panel were all present and nothing ever
inserted a row, so the panel reported "awaiting first data" forever.

**Counters are cumulative, so every percentage here is a delta.** A Prometheus
counter only ever increases from process start. Reading `REQUESTS` directly
would make `http_5xx_pct` a lifetime average: one 500 during a deploy would
keep the panel amber for weeks even after the outage was over. Each sample
therefore records the previous cumulative reading and reports the change since.

**Only columns this process can honestly measure are filled.** The rest stay
NULL on purpose, which is what `HealthMetric`'s nullable columns and
`evaluate_a_w_health`'s `missing_data` list are designed for:

* `uptime_pct` - needs an *external* prober. This process cannot record the
  intervals during which it was not running: there is no row to hold them, so a
  self-reported figure would read a perfect 100% through every outage. The
  thresholds module attributes this metric to `uptime_kuma` for that reason.
* `cpu_pct` / `ram_pct` / `disk_pct` - host-level, attributed to
  `node_exporter` in the thresholds module. Reading them here would duplicate
  the host agent and report the app container's view as the host's.
* `crash_free_rate_pct` / `anr_rate_pct` - marked Android-only on the model.
  Web crash information comes from the `crash` telemetry events instead.

Percentages are None rather than 0.0 when there was no traffic in the window:
"no requests" and "no errors" are different facts, and only one of them is goodnews.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlmodel import Session, delete, select

from core.config import settings
from features.monitoring.domain.models import HealthMetric
from features.monitoring.infrastructure import metrics as M

logger = logging.getLogger(__name__)

#: The Health subsection this table backs. Android rows are pushed by the app.
PLATFORM = "web"


# ---------------------------------------------------------------------------
# Cumulative-counter bookkeeping
# ---------------------------------------------------------------------------

#: Cumulative readings at the previous sample, keyed by sample identity.
#: Process-local on purpose: these are this process's counters, so a restart
#: resets both the counters and this cache together and they stay consistent.
_PREV: dict[str, float] = {}
_PREV_LOCK = threading.Lock()


def _counter_deltas() -> dict[str, float]:
    """Read every counter and histogram as change-since-last-sample.

    Returns a mapping of identity -> delta. Identity is the sample name plus
    its labels, so `REQUESTS{route=/health,status=5xx}` and
    `REQUESTS{route=/auth/login,status=5xx}` are tracked apart.
    """
    current: dict[str, float] = {}

    for metric in (M.REQUESTS, M.REQUEST_DURATION, M.DB_QUERIES, M.DB_QUERY_DURATION):
        for fam in metric.collect():
            for s in fam.samples:
                if s.name.endswith("_created"):
                    # prometheus_client emits a `_created` timestamp series that
                    # would otherwise pollute the delta map with wall-clock floats.
                    continue
                labels = ",".join(f"{k}={v}" for k, v in sorted(s.labels.items()))
                current[f"{s.name}|{labels}"] = float(s.value)

    with _PREV_LOCK:
        deltas: dict[str, float] = {}
        for key, value in current.items():
            before = _PREV.get(key, 0.0)
            # A counter that went backwards was reset by a process restart we did
            # not observe. Treat the whole current value as the delta rather than
            # emitting a negative change.
            deltas[key] = value - before if value >= before else value
        _PREV.clear()
        _PREV.update(current)
    return deltas


def _reset_counter_state() -> None:
    """Forget the baseline. Used by tests and after a deliberate reset."""
    with _PREV_LOCK:
        _PREV.clear()


# ---------------------------------------------------------------------------
# Reading deltas back into the numbers the panel wants
# ---------------------------------------------------------------------------

def _prefix_sum(deltas: dict[str, float], prefix: str) -> dict[float, float]:
    """Collapse per-label bucket deltas into one cumulative curve per `le`.

    A Prometheus histogram stores cumulative counts per bucket, separately for
    each label combination. Aggregating across routes is what produces a single
    p95 for the whole service.
    """
    buckets: dict[float, float] = {}
    for key, delta in deltas.items():
        name, _, labels = key.partition("|")
        if not name.startswith(prefix):
            continue
        if not name.endswith("_bucket"):
            continue
        le = None
        for part in labels.split(","):
            if part.startswith("le="):
                le = part[3:]
        if le is None:
            continue
        edge = float("inf") if le in ("+Inf", "inf") else float(le)
        buckets[edge] = buckets.get(edge, 0.0) + delta
    return buckets


def _curve(buckets: dict[float, float]) -> tuple[dict[float, float], float]:
    """Split a bucket map into its finite edges and its true total.

    A Prometheus histogram's `_bucket` series is *cumulative*: `le=1.0` already
    contains every observation in `le=0.01`. So the total is the `+Inf` bucket
    (or the largest finite one when `+Inf` is absent) and **not** the sum of the
    buckets - summing them counts most observations several times over.
    """
    finite = {le: c for le, c in buckets.items() if le != float("inf")}
    below_top = max(finite.values()) if finite else 0.0
    top = buckets.get(float("inf"))
    total = max(top, below_top) if top is not None else below_top
    return finite, total


def _quantile(buckets: dict[float, float], q: float) -> Optional[float]:
    """Interpolate a quantile from a cumulative bucket curve.

    Linear interpolation inside the bucket that straddles the quantile, which is
    what Prometheus' own `histogram_quantile` does. Observations that landed in
    the `+Inf` overflow cannot be interpolated - there is no upper edge - so the
    largest finite edge is returned, which is the only finite statement available.
    """
    finite, total = _curve(buckets)
    if not finite or total <= 0:
        return None

    target = q * total
    prev_le = 0.0
    prev_count = 0.0
    for le in sorted(finite):
        count = finite[le]
        if count >= target:
            span = count - prev_count
            frac = (target - prev_count) / span if span > 0 else 0.0
            return prev_le + (le - prev_le) * frac
        prev_le, prev_count = le, count

    # The quantile fell in the +Inf overflow.
    return max(finite)


def _count_at_or_above(buckets: dict[float, float], threshold_s: float) -> float:
    """How many observations were `threshold_s` or slower.

    Expressed as `total - (cumulative count below the threshold)` rather than by
    summing the slow buckets, because those buckets are cumulative and summing
    them would count a single 8-second query once for every edge above it.
    """
    finite, total = _curve(buckets)
    if not finite or total <= 0:
        return 0.0
    below_edges = [le for le in finite if le < threshold_s]
    below = finite[max(below_edges)] if below_edges else 0.0
    return max(0.0, total - below)


def _ms(seconds: Optional[float]) -> Optional[int]:
    return None if seconds is None else int(round(seconds * 1000))


def _pct(part: float, whole: float) -> Optional[float]:
    if whole <= 0:
        return None
    return round(part / whole * 100, 3)


def _http_status_counts(deltas: dict[str, float]) -> dict[str, float]:
    """Sum `REQUESTS` deltas by status class."""
    out: dict[str, float] = {}
    for key, delta in deltas.items():
        name, _, labels = key.partition("|")
        if name != "campuspilot_http_requests_total":
            continue
        for part in labels.split(","):
            if part.startswith("status="):
                cls = part[7:]
                out[cls] = out.get(cls, 0.0) + delta
    return out


# ---------------------------------------------------------------------------
# Database connection counts (PostgreSQL only)
# ---------------------------------------------------------------------------

def _db_connections(db: Session) -> tuple[Optional[int], Optional[int]]:
    """Active and idle backends from `pg_stat_activity`.

    Best-effort: any dialect other than PostgreSQL, or a permission failure,
    yields (None, None) instead of failing the sample. A monitoring probe that
    can take the whole scheduler down is worse than one that reports nothing.
    """
    from sqlalchemy import text

    try:
        dialect = db.get_bind().dialect.name
    except Exception:
        return None, None
    if dialect != "postgresql":
        return None, None
    try:
        # Counted in SQL rather than by mapping rows client-side: `Session.exec`
        # hands back Row objects for a raw `text()` query, so `str(row)` is the
        # tuple repr ("('active',)") and a naive string comparison against
        # "active" silently yields zero for both counts.
        row = db.exec(
            text(
                "SELECT count(*) FILTER (WHERE state = 'active') AS active, "
                "       count(*) FILTER (WHERE state = 'idle') AS idle "
                "FROM pg_stat_activity WHERE datname = current_database()"
            )
        ).first()
        if row is None:
            return None, None
        return int(row[0]), int(row[1])
    except Exception:
        db.rollback()
        return None, None


# ---------------------------------------------------------------------------
# The sample itself
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sample_once(db: Session, platform: str = PLATFORM) -> HealthMetric:
    """Take one reading and persist it. Returns the stored row."""
    deltas = _counter_deltas()

    # --- HTTP status mix -------------------------------------------------
    by_class = _http_status_counts(deltas)
    total_req = sum(by_class.values())
    two_xx = sum(v for k, v in by_class.items() if k == "2xx")
    four_xx = sum(v for k, v in by_class.items() if k == "4xx")
    five_xx = sum(v for k, v in by_class.items() if k == "5xx")

    # --- Request latency (seconds -> ms) --------------------------------
    http_buckets = _prefix_sum(deltas, "campuspilot_http_request_duration_seconds")

    # A measured count of zero is a fact; None means "not measured". Only report
    # None when the histogram has no samples at all, so "0 slow queries" and
    # "no queries ran" stay distinguishable.
    db_buckets = _prefix_sum(deltas, "campuspilot_db_query_duration_seconds")
    _, db_total = _curve(db_buckets)
    slow = _count_at_or_above(db_buckets, settings.health_slow_query_ms / 1000.0)

    active, idle = _db_connections(db)

    row = HealthMetric(
        ts=_now_utc(),
        platform=platform,
        response_time_ms=_ms(_quantile(http_buckets, 0.50)),
        response_time_p95_ms=_ms(_quantile(http_buckets, 0.95)),
        response_time_p99_ms=_ms(_quantile(http_buckets, 0.99)),
        http_2xx_pct=_pct(two_xx, total_req),
        http_4xx_pct=_pct(four_xx, total_req),
        http_5xx_pct=_pct(five_xx, total_req),
        db_query_p50_ms=_ms(_quantile(db_buckets, 0.50)),
        db_query_p95_ms=_ms(_quantile(db_buckets, 0.95)),
        db_slow_queries_count=int(slow) if db_total > 0 else None,
        db_connections_active=active,
        db_connections_idle=idle,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def prune(db: Session, retention_days: Optional[int] = None) -> int:
    """Delete samples older than the retention window. Returns rows removed."""
    days = retention_days if retention_days is not None else settings.health_retention_days
    if days <= 0:
        return 0
    cutoff = _now_utc() - timedelta(days=days)
    result = db.exec(delete(HealthMetric).where(HealthMetric.ts < cutoff))
    db.commit()
    return int(result.rowcount or 0)


# ---------------------------------------------------------------------------
# Timer
# ---------------------------------------------------------------------------

def start_loop(interval_s: Optional[int] = None) -> threading.Thread:
    """Sample on a timer in this process. Mirrors the rollup loop in main.py."""
    interval = interval_s or settings.health_sample_interval_s

    def loop() -> None:
        from core.database import session_scope

        while True:
            time.sleep(interval)
            try:
                # Read the values while the session is still open. `commit()`
                # expires every attribute and `session_scope` then closes the
                # session, so touching `row.*` afterwards raises
                # DetachedInstanceError.
                with session_scope() as db:
                    prune(db)
                    row = sample_once(db)
                    p95 = row.response_time_p95_ms
                    five_xx = row.http_5xx_pct
                    slow = row.db_slow_queries_count
                logger.info(
                    "health sample: p95=%sms 5xx=%s%% slow=%s", p95, five_xx, slow
                )
            except Exception:
                logger.exception("health sample failed; will retry next interval")

    thread = threading.Thread(target=loop, name="health-sampler", daemon=True)
    thread.start()
    logger.info("health sampler started (interval %ds)", interval)
    return thread


def run_now() -> dict[str, Any]:
    """One off-sample, for the admin endpoint and for scripts."""
    from core.database import session_scope

    with session_scope() as db:
        prune(db)
        row = sample_once(db)
        return {
            "ts": row.ts.isoformat(),
            "platform": row.platform,
            "response_time_ms": row.response_time_ms,
            "response_time_p95_ms": row.response_time_p95_ms,
            "response_time_p99_ms": row.response_time_p99_ms,
            "http_2xx_pct": row.http_2xx_pct,
            "http_4xx_pct": row.http_4xx_pct,
            "http_5xx_pct": row.http_5xx_pct,
            "db_query_p50_ms": row.db_query_p50_ms,
            "db_query_p95_ms": row.db_query_p95_ms,
            "db_slow_queries_count": row.db_slow_queries_count,
            "db_connections_active": row.db_connections_active,
            "db_connections_idle": row.db_connections_idle,
        }