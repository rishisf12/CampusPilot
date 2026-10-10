"""Tables for the Web App Monitoring and Android App Monitoring sections.

Four groups:

* **Event capture** (`Event`, `Session`, `Purchase`, `AdEvent`) - privacy-friendly
  facts about usage. No emails, no names, no IP addresses.
* **Rollups** (`EventHourly`) - hourly aggregates the dashboards and the AI
  scans actually query. Raw events are high-cardinality and expire; rollups are
  small, permanent, and fast enough to sit inside a scan's time budget.
* **Scan history** (`ScanResult`, `StatusTransition`) - every verdict an AI scan
  has ever returned, plus the incident log derived from transitions.
* **Tool audit** (`ToolCallAudit`) - every single tool call a scan made. This is
  what makes "the LLM never invented that number" checkable rather than a claim.

Naming note: `session_id` here means a *device/app session*, not an auth session.
It is a random per-install identifier with no link to the user table, so joining
these tables cannot deanonymise anyone.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Text, UniqueConstraint, func
from sqlmodel import Column, Field, SQLModel


class Platform(str, Enum):
    WEB = "web"
    ANDROID = "android"


class ScanStatus(str, Enum):
    """Verdict for one subsection.

    ``ERROR`` is separate from ``CRITICAL`` on purpose: a scan that could not run
    is not evidence that the system is broken, and conflating the two would page
    an administrator at 3am because Ollama was restarting.
    """

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


class Event(SQLModel, table=True):
    """One thing a user did.

    ``user_hash`` is an HMAC of the user id with a server-side pepper, never a
    plain hash: a plain SHA-256 of an email is trivially reversible for a known
    user population, an HMAC is not. Rotating the pepper pseudonymises all
    history at once, which doubles as an erasure mechanism.
    """

    __tablename__ = "event"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: RFC3339 UTC, naive (no tzinfo) to match every other column in this schema.
    #: Mixing aware and naive datetimes in one database is a reliable source of
    #: off-by-one-hour bugs at the boundaries, so the convention is naive-UTC
    #: everywhere and conversion happens at the edge.
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    #: Random per-install id. Not an auth session and not linkable to a user.
    session_id: str = Field(index=True)
    #: HMAC(pepper, user_id), or NULL when the visitor is anonymous. Kept as a
    #: column so "distinct active users" is an indexed count rather than a
    #: JSON extraction over every row.
    user_hash: Optional[str] = Field(default=None, index=True)
    event_name: str = Field(index=True)
    props: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    #: Dimensions kept as columns rather than props so breakdowns are indexable.
    app_version: Optional[str] = Field(default=None, index=True)
    os_version: Optional[str] = Field(default=None, index=True)
    device_model: Optional[str] = Field(default=None, index=True)
    #: ISO country, from the edge, never a full IP. Deliberately coarse: a city
    #: would be re-identifying for a single-campus app.
    country: Optional[str] = Field(default=None, index=True)


class EventHourly(SQLModel, table=True):
    """Hourly aggregate of `Event`.

    Every volume chart and every AI scan reads this, never `event`. That is what
    makes a 90-day period-over-period comparison cheap enough to run inside a
    scan's 240 second budget: `event` over 90 days is millions of rows, this is
    a few thousand.

    Deliberately has no `user_hash`. Distinct-user counting belongs on
    `monitoring_session`, where there is one row per session; putting users in
    this table would make the rollup as large as the raw data, which defeats the
    entire purpose of having it.

    **The dimensions are non-nullable strings, not NULLs, on purpose.** This
    table's uniqueness is what makes the rollup idempotent. PostgreSQL treats
    NULLs as distinct in a unique index, so a constraint over nullable columns
    would silently permit a hundred duplicate rows for the same bucket whenever
    the client sent no app_version - which is most of them. SQLite would enforce
    it and Postgres would not, and the divergence would only show up in
    production. Empty string is the "absent" marker; the query layer renders it
    as "unknown".
    """

    __tablename__ = "event_hourly"
    __table_args__ = (
        UniqueConstraint(
            "bucket_hour", "platform", "event_name", "app_version",
            "os_version", "country", name="uq_event_hourly",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    bucket_hour: datetime = Field(sa_column=Column("bucket_hour", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    event_name: str = Field(index=True)
    app_version: str = Field(default="", index=True)
    os_version: str = Field(default="", index=True)
    country: str = Field(default="", index=True)
    n: int = Field(default=0)
    updated_at: datetime = Field(
        default=None,
        sa_column=Column("updated_at", DateTime, nullable=False, server_default=func.now()),
    )


class Session(SQLModel, table=True):
    """One app/web session. The source of truth for DAU/WAU/MAU and retention.

    Carries `user_hash` rather than `user_id` so nothing in the monitoring tables
    can be joined back to a person without the pepper.
    """

    __tablename__ = "monitoring_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    platform: str = Field(index=True)
    user_hash: Optional[str] = Field(default=None, index=True)
    started_at: datetime = Field(default=None, sa_column=Column("started_at", DateTime, nullable=False, index=True))
    last_seen_at: datetime = Field(default=None, sa_column=Column("last_seen_at", DateTime, nullable=False))
    #: Rolled up on session end so retention queries do not rescan raw events.
    duration_s: int = 0
    event_count: int = 0
    app_version: Optional[str] = Field(default=None, index=True)
    os_version: Optional[str] = Field(default=None, index=True)
    device_model: Optional[str] = Field(default=None, index=True)
    country: Optional[str] = Field(default=None, index=True)


class Purchase(SQLModel, table=True):
    """An in-app purchase or subscription transaction.

    ``verified`` is the important column. A client that reports "I bought the
    Pro tier" without the store checking the receipt is self-reported and worth
    nothing, so unverified rows are kept but every revenue figure states how much
    of the total is verified.
    """

    __tablename__ = "purchase"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: Store transaction token. Unique, so a replayed receipt is rejected.
    transaction_id: str = Field(index=True, unique=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    product_id: str = Field(index=True)
    #: Minor units (paise/cents) as an integer. Never a float: binary floating
    #: point cannot represent 0.10 exactly, and money summed in floats drifts.
    price_micros: int = 0
    currency: str = Field(default="INR")
    user_hash: Optional[str] = Field(default=None, index=True)
    app_version: Optional[str] = Field(default=None, index=True)
    verified: bool = Field(default=False, index=True)
    #: Free-form: "subscription", "consumable", "restore".
    kind: str = Field(default="one_time")


class AdEvent(SQLModel, table=True):
    """An ad impression or click. eCPM is derived from these, never sent by the client."""

    __tablename__ = "ad_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    ad_network: str = Field(index=True)
    ad_unit: str = Field(index=True)
    #: "impression" or "click".
    event_type: str = Field(index=True)
    #: Revenue for an impression, in minor units. NULL on a click.
    revenue_micros: Optional[int] = Field(default=None)
    currency: str = Field(default="INR")
    user_hash: Optional[str] = Field(default=None, index=True)
    app_version: Optional[str] = Field(default=None, index=True)


class CrashReport(SQLModel, table=True):
    """A crash or ANR reported by the Android client or the web client.

    ``stack_trace`` is untrusted input: it contains file paths, class names and
    sometimes a message a user typed. It is stored, never rendered as HTML, and
    always wrapped in an untrusted-data marker before it reaches an LLM.
    """

    __tablename__ = "crash_report"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    #: "crash" or "anr".
    kind: str = Field(index=True)
    #: The session the crash happened in. Crash-free rate is defined on sessions,
    #: so without this column the only alternative is counting distinct users,
    #: which hides a user who crashes on every launch behind one affected user.
    session_id: str = Field(index=True)
    #: Stable grouping key (exception type + top frames, hashed client-side).
    fingerprint: str = Field(index=True)
    exception_type: Optional[str] = Field(default=None, index=True)
    message: Optional[str] = Field(default=None)
    stack_trace: Optional[str] = Field(default=None, sa_column=Column("stack_trace", Text, nullable=True))
    #: True when the process died; False for a caught exception or an ANR.
    fatal: bool = Field(default=True, index=True)
    app_version: Optional[str] = Field(default=None, index=True)
    os_version: Optional[str] = Field(default=None, index=True)
    device_model: Optional[str] = Field(default=None, index=True)
    #: Was the app in the foreground? Background ANRs are a separate and much
    #: less urgent class of problem; averaging them in hides a foreground
    #: regression behind a wall of benign ones.
    foreground: bool = Field(default=True, index=True)


class SecurityEvent(SQLModel, table=True):
    """A security-relevant occurrence, for the C subsections.

    Deliberately server-generated where possible. Client-side root/emulator
    detection is recorded as a *signal* with a boolean, never trusted as an auth
    decision: it is bypassed in minutes and gating on it just creates support
    burden from your own security feature.
    """

    __tablename__ = "security_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    #: failed_login, brute_force, token_misuse, api_abuse, root_detected,
    #: emulator_detected, tamper_detected, rate_limited, waf_blocked.
    kind: str = Field(index=True)
    #: Hashed remote address. The raw IP is never stored - it is personal data
    #: and a truncated hash still supports per-source rate limiting.
    ip_hash: Optional[str] = Field(default=None, index=True)
    user_hash: Optional[str] = Field(default=None, index=True)
    app_version: Optional[str] = Field(default=None, index=True)
    #: True when the system acted (banned, challenged), False when observed only.
    blocked: bool = Field(default=False, index=True)
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))


class ScanResult(SQLModel, table=True):
    """One AI scan verdict. Never overwritten - this table is the history."""

    __tablename__ = "scan_result"
    __table_args__ = (UniqueConstraint("scan_id", name="uq_scan_result_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: str = Field(index=True)
    #: A_W_HEALTH, B_W_ACTIVITY, C_W_SECURITY, D_W_FEEDBACK, A_A_HEALTH, ...
    subsection: str = Field(index=True)
    status: str = Field(index=True)
    summary: str = Field(default="", sa_column=Column("summary", Text, nullable=False, default=""))
    findings: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    root_causes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    actions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    confidence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    #: Recorded so a change in model can be correlated with a change in verdicts.
    model: str = Field(default="", index=True)
    #: Hash of the system prompt, same reason.
    prompt_hash: str = Field(default="")
    window_start: datetime = Field(default=None, sa_column=Column("window_start", DateTime, nullable=False))
    window_end: datetime = Field(default=None, sa_column=Column("window_end", DateTime, nullable=False))
    duration_ms: int = 0
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now(), index=True),
    )


class StatusTransition(SQLModel, table=True):
    """A change in scan status between two runs. This *is* the incident log.

    Duration is derived rather than stored: an incident that is still open has no
    end time, and storing a duration would mean rewriting rows whenever a later
    scan closes the incident.
    """

    __tablename__ = "status_transition"

    id: Optional[int] = Field(default=None, primary_key=True)
    subsection: str = Field(index=True)
    from_status: str = Field(index=True)
    to_status: str = Field(index=True)
    scan_id: str = Field(index=True)
    at: datetime = Field(
        default=None,
        sa_column=Column("at", DateTime, nullable=False, server_default=func.now(), index=True),
    )


class ToolCallAudit(SQLModel, table=True):
    """Every tool call made by every scan.

    Not optional bookkeeping. This is the record that lets the reconciler prove a
    number in a finding came from a tool, and it is the audit trail for the claim
    that scans are read-only - if no write ever appears here, nothing did one.
    """

    __tablename__ = "tool_call_audit"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: str = Field(index=True)
    tool: str = Field(index=True)
    args: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    #: Key the reconciler looks a finding's `metric` up against.
    metric_key: Optional[str] = Field(default=None, index=True)
    row_count: int = 0
    duration_ms: int = 0
    ok: bool = Field(default=True, index=True)
    error: Optional[str] = Field(default=None, sa_column=Column("error", Text, nullable=True))
    at: datetime = Field(
        default=None,
        sa_column=Column("at", DateTime, nullable=False, server_default=func.now()),
    )


# =============================================================================
# Health / Performance Metrics (Section A)
# =============================================================================

class HealthMetric(SQLModel, table=True):
    """Periodic health snapshots for web and Android.

    Collected by a background scraper or pushed by the app. These are the raw
    data points that the Health subsection and AI scan read.
    """

    __tablename__ = "health_metric"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)  # web | android

    # Uptime / Availability
    uptime_pct: Optional[float] = Field(default=None)  # 0-100
    response_time_ms: Optional[int] = Field(default=None)  # p50 or p95
    response_time_p95_ms: Optional[int] = Field(default=None)
    response_time_p99_ms: Optional[int] = Field(default=None)

    # HTTP error rates
    http_2xx_pct: Optional[float] = Field(default=None)
    http_4xx_pct: Optional[float] = Field(default=None)
    http_5xx_pct: Optional[float] = Field(default=None)

    # System resources (host-level, from node_exporter)
    cpu_pct: Optional[float] = Field(default=None)
    ram_pct: Optional[float] = Field(default=None)
    disk_pct: Optional[float] = Field(default=None)
    network_rx_bytes: Optional[int] = Field(default=None)
    network_tx_bytes: Optional[int] = Field(default=None)

    # Database performance
    db_connections_active: Optional[int] = Field(default=None)
    db_connections_idle: Optional[int] = Field(default=None)
    db_query_p50_ms: Optional[float] = Field(default=None)
    db_query_p95_ms: Optional[float] = Field(default=None)
    db_slow_queries_count: Optional[int] = Field(default=None)

    # SSL / Certificates
    ssl_expiry_days: Optional[int] = Field(default=None)
    ssl_issuer: Optional[str] = Field(default=None)

    # Android-specific
    crash_free_rate_pct: Optional[float] = Field(default=None)  # Android only
    anr_rate_pct: Optional[float] = Field(default=None)        # Android only
    startup_time_ms: Optional[int] = Field(default=None)       # Android cold start
    slow_frames_pct: Optional[float] = Field(default=None)     # Android jank
    api_failure_rate_pct: Optional[float] = Field(default=None) # Android API calls
    battery_pct: Optional[float] = Field(default=None)         # Android avg battery
    memory_pct: Optional[float] = Field(default=None)          # Android memory

    # Dimensions for breakdowns
    app_version: str = Field(default="", index=True)
    os_version: str = Field(default="", index=True)
    device_model: str = Field(default="", index=True)
    country: str = Field(default="", index=True)

    # Slow endpoints (top 10 by p95)
    slow_endpoints: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))


class SlowEndpoint(SQLModel, table=True):
    """Individual slow endpoint tracking for the Health subsection.

    Keeps a running window of the slowest endpoints so the dashboard can show
    "top 10 slowest" without re-scanning all requests.
    """

    __tablename__ = "slow_endpoint"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    endpoint: str = Field(index=True)  # route template, e.g. "/api/feedback"
    method: str = Field(default="GET")
    p50_ms: int = 0
    p95_ms: int = 0
    p99_ms: int = 0
    request_count: int = 0
    error_count: int = 0
    app_version: str = Field(default="", index=True)


# =============================================================================
# Security Monitoring (Section C)
# =============================================================================

class SecurityLog(SQLModel, table=True):
    """Detailed security event log for the Security subsection.

    Extends the basic SecurityEvent with more context for investigation.
    """

    __tablename__ = "security_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)

    # Event classification
    category: str = Field(index=True)  # auth | network | application | data | compliance
    severity: str = Field(index=True)  # info | low | medium | high | critical
    action: str = Field(index=True)    # blocked | challenged | logged | alerted

    # Source
    ip_hash: Optional[str] = Field(default=None, index=True)
    user_hash: Optional[str] = Field(default=None, index=True)
    user_agent: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None, index=True)

    # Details
    rule_id: Optional[str] = Field(default=None, index=True)  # e.g. "WAF-RULE-001"
    rule_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))

    # Android-specific
    root_detected: bool = Field(default=False)
    emulator_detected: bool = Field(default=False)
    tamper_detected: bool = Field(default=False)
    hooking_detected: bool = Field(default=False)
    debugger_attached: bool = Field(default=False)

    # Resolution
    resolved: bool = Field(default=False, index=True)
    resolved_at: Optional[datetime] = Field(default=None)
    resolved_by: Optional[str] = Field(default=None)


class DependencyVulnerability(SQLModel, table=True):
    """Track known vulnerabilities in dependencies (from Trivy/OSV scans)."""

    __tablename__ = "dependency_vulnerability"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))

    # Package info
    ecosystem: str = Field(index=True)  # pypi | npm | maven | go | cargo | nuget
    package_name: str = Field(index=True)
    installed_version: str = Field(index=True)
    fixed_version: Optional[str] = Field(default=None)

    # Vulnerability details
    vuln_id: str = Field(index=True)  # CVE-XXXX-XXXX or GHSA-XXXX
    severity: str = Field(index=True)  # critical | high | medium | low
    cvss_score: Optional[float] = Field(default=None)
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    references: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))

    # Status
    status: str = Field(default="open", index=True)  # open | fixed | ignored | false_positive
    fixed_at: Optional[datetime] = Field(default=None)
    ignored_reason: Optional[str] = Field(default=None)


class SecurityHeaderCheck(SQLModel, table=True):
    """Periodic security headers compliance check."""

    __tablename__ = "security_header_check"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)
    url: str = Field(index=True)

    # Header presence (boolean)
    hsts: bool = False
    csp: bool = False
    x_frame_options: bool = False
    x_content_type_options: bool = False
    referrer_policy: bool = False
    permissions_policy: bool = False
    cross_origin_opener_policy: bool = False
    cross_origin_resource_policy: bool = False

    # CSP details
    csp_header: Optional[str] = Field(default=None)
    csp_report_only: bool = False

    # Scoring
    score: int = 0  # 0-100
    grade: str = "F"  # A+ through F

    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))


# =============================================================================
# Feedback Analysis (Section D) - Extended
# =============================================================================

class FeedbackAnalysis(SQLModel, table=True):
    """Pre-computed feedback analysis for the Feedback subsection.

    Run periodically (hourly/daily) so the dashboard and AI scans don't
    recompute sentiment/topic clustering on every request.
    """

    __tablename__ = "feedback_analysis"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    window_start: datetime = Field(default=None, sa_column=Column("window_start", DateTime, nullable=False, index=True))
    window_end: datetime = Field(default=None, sa_column=Column("window_end", DateTime, nullable=False))

    # Volume
    total_count: int = 0
    with_attachment_count: int = 0
    replied_count: int = 0

    # Sentiment (VADER)
    sentiment_positive: int = 0
    sentiment_neutral: int = 0
    sentiment_negative: int = 0
    sentiment_mean: float = 0.0

    # Topics (BERTopic or keyword-based)
    topics: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))

    # Rating trends (if applicable)
    rating_distribution: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))

    # Top complaints / feature requests
    top_complaints: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    top_requests: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))

    # Correlation with crashes/releases
    crash_correlation: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    release_correlation: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))


class FeedbackSentimentSnapshot(SQLModel, table=True):
    """Per-feedback sentiment for drill-down in the Feedback subsection."""

    __tablename__ = "feedback_sentiment_snapshot"

    id: Optional[int] = Field(default=None, primary_key=True)
    feedback_id: int = Field(index=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))

    # VADER scores
    compound: float = 0.0
    positive: float = 0.0
    neutral: float = 0.0
    negative: float = 0.0

    # Topic assignment
    topic: Optional[str] = Field(default=None, index=True)
    subtopic: Optional[str] = Field(default=None, index=True)

    # Key phrases extracted
    key_phrases: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))


# =============================================================================
# Monetization / Revenue - Extended (Section B)
# =============================================================================

class Subscription(SQLModel, table=True):
    """Subscription lifecycle tracking for churn/retention analysis."""

    __tablename__ = "subscription"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    platform: str = Field(index=True)

    # User identification (pseudonymized)
    user_hash: Optional[str] = Field(default=None, index=True)

    # Subscription details
    product_id: str = Field(index=True)
    status: str = Field(index=True)  # active | cancelled | expired | past_due | trial
    billing_period: str = Field(default="monthly")  # monthly | yearly | weekly

    # Revenue
    price_micros: int = 0
    currency: str = Field(default="INR")
    verified: bool = Field(default=False)

    # Lifecycle
    started_at: datetime = Field(default=None, sa_column=Column("started_at", DateTime, nullable=False, index=True))
    renewed_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)

    # Cancellation
    cancellation_reason: Optional[str] = Field(default=None)
    cancellation_survey: Optional[str] = Field(default=None)

    # Trial
    is_trial: bool = Field(default=False)
    trial_ends_at: Optional[datetime] = Field(default=None)


class RevenueSnapshot(SQLModel, table=True):
    """Pre-aggregated revenue snapshot for the Monetization subsection."""

    __tablename__ = "revenue_snapshot"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default=None, sa_column=Column("ts", DateTime, nullable=False, index=True))
    window_start: datetime = Field(default=None, sa_column=Column("window_start", DateTime, nullable=False))
    window_end: datetime = Field(default=None, sa_column=Column("window_end", DateTime, nullable=False))

    platform: str = Field(index=True)
    app_version: str = Field(default="", index=True)

    # Revenue (verified only by default, but also track unverified)
    revenue_verified_micros: int = 0
    revenue_unverified_micros: int = 0
    currency: str = Field(default="INR")

    # Purchases
    purchases_verified: int = 0
    purchases_unverified: int = 0
    subscriptions_active: int = 0
    subscriptions_new: int = 0
    subscriptions_churned: int = 0

    # Ad revenue
    ad_impressions: int = 0
    ad_clicks: int = 0
    ad_revenue_micros: int = 0
    ad_ecpm_micros: int = 0

    # ARPU
    active_users: int = 0
    arpu_verified_micros: int = 0

    # Breakdowns
    by_product: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    by_country: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))