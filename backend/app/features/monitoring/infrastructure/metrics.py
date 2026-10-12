"""Prometheus instrumentation for the API.

These are the numbers the Web Health subsection reports and the AI scans for
A_W_HEALTH read. Registered in one module so there is a single place to see what
is exported and to avoid duplicate-registration errors on reload.

Design decisions worth stating:

* **Histogram, not summary, for latency.** A summary cannot be aggregated across
  instances, and `histogram_quantile` over buckets is what makes a p95 across
  several app workers meaningful.

* **Buckets are chosen for this app, not a default.** An API that answers in
  30-80 ms would have every request in the default 5 ms bucket and the p95 would
  read as 5 ms forever. These buckets straddle the range this codebase actually
  produces, which includes a PDF/OCR path that is legitimately slow.

* **No user identifiers in labels.** `user_id` or `email` as a Prometheus label
  would blow up cardinality and write personal data into a metrics store. Labels
  here are route templates and status classes only.

* **Every instrument is created at import time.** Prometheus registries raise on
  duplicate registration, so these must not be created per request.
"""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

#: Buckets in seconds, tuned for this API: most reads are tens of milliseconds,
#: file/OCR work runs to a few seconds. Without a bucket around 0.1-1s the p95 is
#: meaningless.
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

REGISTRY = CollectorRegistry(auto_describe=True)


def _build() -> None:
    global REQUESTS, REQUEST_DURATION, REQUEST_IN_FLIGHT, DB_QUERY_DURATION, \
        DB_QUERIES, COLLECTOR_EVENTS, SCAN_DURATION, SCAN_FAILURES, SCAN_RUNS

    REQUESTS = Counter(
        "campuspilot_http_requests_total",
        "HTTP requests handled, by route template, method and status class.",
        ["route", "method", "status"],
        registry=REGISTRY,
    )

    REQUEST_DURATION = Histogram(
        "campuspilot_http_request_duration_seconds",
        "Request latency in seconds, by route template and method.",
        ["route", "method"],
        buckets=LATENCY_BUCKETS,
        registry=REGISTRY,
    )

    REQUEST_IN_FLIGHT = Gauge(
        "campuspilot_http_requests_in_flight",
        "Requests currently being served. Alert on this: it is the first thing to "
        "climb under a traffic spike or a run of slow queries.",
        registry=REGISTRY,
    )

    DB_QUERY_DURATION = Histogram(
        "campuspilot_db_query_duration_seconds",
        "Session-level database work, by operation label.",
        ["operation"],
        buckets=LATENCY_BUCKETS,
        registry=REGISTRY,
    )

    DB_QUERIES = Counter(
        "campuspilot_db_queries_total",
        "Database operations by outcome.",
        ["operation", "outcome"],
        registry=REGISTRY,
    )

    COLLECTOR_EVENTS = Counter(
        "campuspilot_collector_events_total",
        "Events accepted or rejected by the telemetry collector, by reason.",
        ["platform", "outcome"],
        registry=REGISTRY,
    )

    SCAN_DURATION = Histogram(
        "campuspilot_scan_duration_seconds",
        "AI scan wall-clock time.",
        ["subsection"],
        buckets=(1, 5, 10, 30, 60, 120, 240, 600),
        registry=REGISTRY,
    )

    SCAN_RUNS = Counter(
        "campuspilot_scan_runs_total",
        "AI scans by terminal status.",
        ["subsection", "status"],
        registry=REGISTRY,
    )

    SCAN_FAILURES = Counter(
        "campuspilot_scan_failures_total",
        "AI scans that failed before producing a verdict. Distinct from a Critical "
        "verdict: a failed scan says nothing about system health.",
        ["subsection", "reason"],
        registry=REGISTRY,
    )


_build()


def route_template(path: str) -> str:
    """Collapse a concrete path to its route template.

    Without this, `/feedback/12345` and `/feedback/67890` become two separate
    time series and a busy endpoint quietly doubles the size of the TSDB. Takes
    the first path segment pair, which is enough for this app's shape:
    `/auth/login` -> `auth/login`, `/health` -> `health`.
    """
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "/"
    if parts[0] in {"auth", "feedback", "teams", "exam", "attendance", "monitoring"}:
        return f"{parts[0]}/{parts[1]}" if len(parts) > 1 else parts[0]
    return parts[0]


def status_class(code: int) -> str:
    """Status as a class, so 404s aggregate instead of one series per code.

    Per-status labels are tempting and wrong here: `status` alone produces one
    series per distinct code, and a scanner probing random paths will invent
    hundreds.
    """
    return f"{code // 100}xx"