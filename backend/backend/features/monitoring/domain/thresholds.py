"""Rule-based thresholds for Stage 1 scans.

These are the concrete numbers that define Healthy/Warning/Critical.
They live in code, not in the prompt, so the model never invents them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class ScanStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


@dataclass(frozen=True)
class Finding:
    """A single rule evaluation result."""
    title: str
    severity: str  # "info", "warning", "critical"
    metric: str
    value: float
    unit: str
    threshold: float
    window: str
    source: str


@dataclass(frozen=True)
class ScanVerdict:
    """Result of running all rules for one subsection."""
    status: ScanStatus
    findings: list[Finding]
    root_causes: list[str]
    actions: list[str]
    confidence: str  # "high", "medium", "low"
    missing_data: list[str]


# ---------------------------------------------------------------------------
# A-W Health: Web uptime, latency, error rates, system resources, DB, SSL
# ---------------------------------------------------------------------------

def evaluate_a_w_health(
    http_p95_ms: Optional[float],
    http_5xx_pct: Optional[float],
    uptime_pct: Optional[float],
    cpu_pct: Optional[float],
    ram_pct: Optional[float],
    disk_pct: Optional[float],
    db_query_p95_ms: Optional[float],
    ssl_expiry_days: Optional[int],
) -> ScanVerdict:
    """Evaluate A-W Health rules."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    # HTTP p95 latency
    if http_p95_ms is None:
        missing.append("http_p95_ms")
    else:
        if http_p95_ms > 2000:
            findings.append(Finding("HTTP p95 latency critical", "critical", "http_p95_ms", http_p95_ms, "ms", 2000, "current", "prometheus"))
            root_causes.append("Backend saturation or slow downstream dependency")
            actions.append("investigate_endpoint")
        elif http_p95_ms > 1000:
            findings.append(Finding("HTTP p95 latency elevated", "warning", "http_p95_ms", http_p95_ms, "ms", 1000, "current", "prometheus"))
            root_causes.append("Possible load increase or query regression")
            actions.append("investigate_endpoint")
        elif http_p95_ms > 500:
            findings.append(Finding("HTTP p95 latency above healthy", "info", "http_p95_ms", http_p95_ms, "ms", 500, "current", "prometheus"))

    # HTTP 5xx rate
    if http_5xx_pct is None:
        missing.append("http_5xx_pct")
    else:
        if http_5xx_pct > 5.0:
            findings.append(Finding("HTTP 5xx rate critical", "critical", "http_5xx_pct", http_5xx_pct, "%", 5.0, "current", "prometheus"))
            root_causes.append("Unhandled exceptions or upstream failures")
            actions.append("investigate_endpoint")
        elif http_5xx_pct > 2.0:
            findings.append(Finding("HTTP 5xx rate elevated", "warning", "http_5xx_pct", http_5xx_pct, "%", 2.0, "current", "prometheus"))
        elif http_5xx_pct > 0.5:
            findings.append(Finding("HTTP 5xx rate above healthy", "info", "http_5xx_pct", http_5xx_pct, "%", 0.5, "current", "prometheus"))

    # Uptime
    if uptime_pct is None:
        missing.append("uptime_pct")
    else:
        if uptime_pct < 99.0:
            findings.append(Finding("Uptime critical", "critical", "uptime_pct", uptime_pct, "%", 99.0, "current", "uptime_kuma"))
            root_causes.append("Service downtime or health check failures")
            actions.append("investigate_endpoint")
        elif uptime_pct < 99.9:
            findings.append(Finding("Uptime below target", "warning", "uptime_pct", uptime_pct, "%", 99.9, "current", "uptime_kuma"))

    # System resources
    if cpu_pct is not None and cpu_pct > 85:
        findings.append(Finding("CPU usage high", "warning", "cpu_pct", cpu_pct, "%", 85, "current", "node_exporter"))
        root_causes.append("Sustained high load or inefficient queries")
        actions.append("scale_worker")

    if ram_pct is not None and ram_pct > 90:
        findings.append(Finding("RAM usage critical", "critical", "ram_pct", ram_pct, "%", 90, "current", "node_exporter"))
        root_causes.append("Memory leak or insufficient capacity")
        actions.append("scale_worker")

    if disk_pct is not None and disk_pct > 85:
        findings.append(Finding("Disk usage high", "warning", "disk_pct", disk_pct, "%", 85, "current", "node_exporter"))
        root_causes.append("Log growth or missing retention")
        actions.append("investigate_data_pipeline")

    # DB query latency
    if db_query_p95_ms is not None and db_query_p95_ms > 500:
        findings.append(Finding("DB query p95 high", "warning", "db_query_p95_ms", db_query_p95_ms, "ms", 500, "current", "prometheus"))
        root_causes.append("Missing indexes or connection pool exhaustion")
        actions.append("investigate_endpoint")

    # SSL expiry
    if ssl_expiry_days is not None and ssl_expiry_days <= 14:
        findings.append(Finding("SSL certificate expiring soon", "critical" if ssl_expiry_days <= 7 else "warning", "ssl_expiry_days", float(ssl_expiry_days), "days", 14.0, "current", "ssl_check"))
        root_causes.append("Certificate renewal not automated")
        actions.append("review_recent_changes")

    # Determine overall status
    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


# ---------------------------------------------------------------------------
# C-W Security: Failed logins, CVEs, security headers, audit log
# ---------------------------------------------------------------------------

def evaluate_c_w_security(
    failed_logins_per_hour: Optional[float],
    critical_cves: int,
    high_cves: int,
    max_failed_logins_single_ip: Optional[float],
    security_headers_grade: Optional[str],
) -> ScanVerdict:
    """Evaluate C-W Security rules."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    # Failed logins per hour
    if failed_logins_per_hour is None:
        missing.append("failed_logins_per_hour")
    else:
        if failed_logins_per_hour > 1000:
            findings.append(Finding("Failed logins critical", "critical", "failed_logins_per_hour", failed_logins_per_hour, "/h", 1000.0, "current hour", "security_event"))
            root_causes.append("Credential stuffing or brute force attack")
            actions.append("add_rate_limit")
        elif failed_logins_per_hour > 100:
            findings.append(Finding("Failed logins elevated", "warning", "failed_logins_per_hour", failed_logins_per_hour, "/h", 100.0, "current hour", "security_event"))
            root_causes.append("Possible brute force attempt")
            actions.append("add_rate_limit")

    # Failed logins from single IP
    if max_failed_logins_single_ip is not None and max_failed_logins_single_ip > 1000:
        findings.append(Finding("Single IP brute force", "critical", "max_failed_logins_single_ip", max_failed_logins_single_ip, "/h", 1000.0, "current hour", "security_event"))
        root_causes.append("Targeted credential stuffing from single source")
        actions.append("rotate_credentials")
    elif max_failed_logins_single_ip is not None and max_failed_logins_single_ip > 100:
        findings.append(Finding("Single IP high failure rate", "warning", "max_failed_logins_single_ip", max_failed_logins_single_ip, "/h", 100.0, "current hour", "security_event"))
        actions.append("add_rate_limit")

    # CVEs
    if critical_cves > 0:
        findings.append(Finding("Critical CVEs in dependencies", "critical", "critical_cves", float(critical_cves), "count", 0.0, "current scan", "trivy"))
        root_causes.append("Outdated dependencies with known exploits")
        actions.append("review_recent_changes")
    elif high_cves > 0:
        findings.append(Finding("High severity CVEs present", "warning", "high_cves", float(high_cves), "count", 0.0, "current scan", "trivy"))
        actions.append("review_recent_changes")

    # Security headers
    if security_headers_grade is not None and security_headers_grade in ("E", "F"):
        findings.append(Finding("Security headers missing", "warning", "security_headers_grade", 0, "grade", 1.0, "current scan", "security_header_check"))
        root_causes.append("Missing HSTS, CSP, or frame options")
        actions.append("review_recent_changes")

    # Determine overall status
    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant security issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


# ---------------------------------------------------------------------------
# A-A Health: Android crash-free rate, ANR, startup, slow frames
# ---------------------------------------------------------------------------

def evaluate_a_a_health(
    crash_free_rate: Optional[float],
    anr_rate: Optional[float],
    startup_time_ms: Optional[float],
    slow_frames_pct: Optional[float],
) -> ScanVerdict:
    """Evaluate A-A Health rules (Android)."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    if crash_free_rate is None:
        missing.append("crash_free_rate")
    else:
        if crash_free_rate < 99.0:
            findings.append(Finding("Crash-free rate critical", "critical", "crash_free_rate", crash_free_rate, "%", 99.0, "current window", "crash_report"))
            root_causes.append("Unhandled exceptions in production")
            actions.append("triage_crash_cluster")
        elif crash_free_rate < 99.5:
            findings.append(Finding("Crash-free rate below target", "warning", "crash_free_rate", crash_free_rate, "%", 99.5, "current window", "crash_report"))
            actions.append("triage_crash_cluster")

    if anr_rate is None:
        missing.append("anr_rate")
    else:
        if anr_rate > 2.0:
            findings.append(Finding("ANR rate critical", "critical", "anr_rate", anr_rate, "%", 2.0, "current window", "crash_report"))
            root_causes.append("Main thread blocking operations")
            actions.append("triage_crash_cluster")
        elif anr_rate > 0.5:
            findings.append(Finding("ANR rate elevated", "warning", "anr_rate", anr_rate, "%", 0.5, "current window", "crash_report"))

    if startup_time_ms is not None and startup_time_ms > 5000:
        findings.append(Finding("Cold start too slow", "warning", "startup_time_ms", startup_time_ms, "ms", 5000.0, "current window", "crash_report"))
        root_causes.append("Heavy initialization on main thread")

    if slow_frames_pct is not None and slow_frames_pct > 25:
        findings.append(Finding("Jank / slow frames high", "warning", "slow_frames_pct", slow_frames_pct, "%", 25.0, "current window", "crash_report"))
        root_causes.append("UI thread overloaded")

    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


# ---------------------------------------------------------------------------
# C-A Security: Android root/emulator signals, token misuse, tampering
# ---------------------------------------------------------------------------

def evaluate_c_a_security(
    root_signal_pct: Optional[float],
    emulator_signal_pct: Optional[float],
    tamper_signal_pct: Optional[float],
    token_misuse_events: int,
    replay_attacks: int,
) -> ScanVerdict:
    """Evaluate C-A Security rules (Android)."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    # Root signals
    if root_signal_pct is None:
        missing.append("root_signal_pct")
    else:
        if root_signal_pct > 5.0:
            findings.append(Finding("Root detection rate high", "critical", "root_signal_pct", root_signal_pct, "%", 5.0, "current window", "security_event"))
            root_causes.append("Widespread root access or detection bypass")
            actions.append("rotate_credentials")
        elif root_signal_pct > 2.0:
            findings.append(Finding("Root detection rate elevated", "warning", "root_signal_pct", root_signal_pct, "%", 2.0, "current window", "security_event"))

    # Emulator signals
    if emulator_signal_pct is not None and emulator_signal_pct > 5.0:
        findings.append(Finding("Emulator detection rate high", "warning", "emulator_signal_pct", emulator_signal_pct, "%", 5.0, "current window", "security_event"))
        root_causes.append("Automated testing or farming on emulators")

    # Tampering
    if tamper_signal_pct is not None and tamper_signal_pct > 1.0:
        findings.append(Finding("Tampering detected", "critical", "tamper_signal_pct", tamper_signal_pct, "%", 1.0, "current window", "security_event"))
        root_causes.append("APK modification or runtime hooking")
        actions.append("triage_crash_cluster")

    # Token misuse
    if token_misuse_events >= 3:
        findings.append(Finding("Token misuse events", "critical", "token_misuse_events", float(token_misuse_events), "count", 2.0, "current window", "security_event"))
        root_causes.append("Session token theft or replay")
        actions.append("rotate_credentials")
    elif token_misuse_events > 0:
        findings.append(Finding("Token misuse detected", "warning", "token_misuse_events", float(token_misuse_events), "count", 0.0, "current window", "security_event"))

    # Replay attacks
    if replay_attacks > 0:
        findings.append(Finding("Replay attack confirmed", "critical", "replay_attacks", float(replay_attacks), "count", 0.0, "current window", "security_event"))
        root_causes.append("Purchase token or session replay")
        actions.append("contact_store")

    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant security issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


# ---------------------------------------------------------------------------
# D-W Feedback: Sentiment, volume, complaints
# ---------------------------------------------------------------------------

def evaluate_d_w_feedback(
    volume_change_pct: Optional[float],
    sentiment_mean: Optional[float],
    top_complaint_count: int,
) -> ScanVerdict:
    """Evaluate D-W Feedback rules."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    if volume_change_pct is None:
        missing.append("volume_change_pct")
    else:
        if volume_change_pct < -50:
            findings.append(Finding("Feedback volume dropped critically", "critical", "volume_change_pct", volume_change_pct, "%", -50.0, "vs baseline", "feedback"))
            root_causes.append("User disengagement or collection issue")
            actions.append("investigate_data_pipeline")
        elif volume_change_pct < -25:
            findings.append(Finding("Feedback volume dropped", "warning", "volume_change_pct", volume_change_pct, "%", -25.0, "vs baseline", "feedback"))

    if sentiment_mean is None:
        missing.append("sentiment_mean")
    else:
        if sentiment_mean < 0.0:
            findings.append(Finding("Mean sentiment negative", "critical", "sentiment_mean", sentiment_mean, "score", 0.0, "current window", "feedback"))
            root_causes.append("Widespread dissatisfaction")
            actions.append("review_recent_changes")
        elif sentiment_mean < 0.3:
            findings.append(Finding("Mean sentiment low", "warning", "sentiment_mean", sentiment_mean, "score", 0.3, "current window", "feedback"))

    if top_complaint_count >= 20:
        findings.append(Finding("Complaint cluster detected", "critical", "top_complaint_count", float(top_complaint_count), "count", 20.0, "current window", "feedback"))
        root_causes.append("Specific feature or regression causing widespread issues")
        actions.append("review_recent_changes")
    elif top_complaint_count >= 10:
        findings.append(Finding("Complaint cluster forming", "warning", "top_complaint_count", float(top_complaint_count), "count", 10.0, "current window", "feedback"))

    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant feedback issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


# ---------------------------------------------------------------------------
# B-W Activity & B-A Activity: DAU, retention, revenue
# ---------------------------------------------------------------------------

def evaluate_b_w_activity(
    dau_change_pct: Optional[float],
    revenue_change_pct: Optional[float],
) -> ScanVerdict:
    """Evaluate B-W Activity rules (Web)."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    if dau_change_pct is None:
        missing.append("dau_change_pct")
    else:
        if dau_change_pct < -40:
            findings.append(Finding("DAU dropped critically", "critical", "dau_change_pct", dau_change_pct, "%", -40.0, "vs baseline", "session"))
            root_causes.append("Major outage or feature regression")
            actions.append("investigate_endpoint")
        elif dau_change_pct < -15:
            findings.append(Finding("DAU declining", "warning", "dau_change_pct", dau_change_pct, "%", -15.0, "vs baseline", "session"))

    if revenue_change_pct is None:
        missing.append("revenue_change_pct")
    else:
        if revenue_change_pct < -30:
            findings.append(Finding("Revenue dropped critically", "critical", "revenue_change_pct", revenue_change_pct, "%", -30.0, "vs baseline", "purchase"))
            root_causes.append("Payment issue or user churn")
            actions.append("investigate_data_pipeline")
        elif revenue_change_pct < -15:
            findings.append(Finding("Revenue declining", "warning", "revenue_change_pct", revenue_change_pct, "%", -15.0, "vs baseline", "purchase"))

    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant activity issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


def evaluate_b_a_activity(
    dau_change_pct: Optional[float],
    iap_revenue_change_pct: Optional[float],
) -> ScanVerdict:
    """Evaluate B-A Activity rules (Android)."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    if dau_change_pct is None:
        missing.append("dau_change_pct")
    else:
        if dau_change_pct < -40:
            findings.append(Finding("DAU dropped critically", "critical", "dau_change_pct", dau_change_pct, "%", -40.0, "vs baseline", "session"))
            root_causes.append("App crash or update issue")
            actions.append("triage_crash_cluster")
        elif dau_change_pct < -20:
            findings.append(Finding("DAU declining", "warning", "dau_change_pct", dau_change_pct, "%", -20.0, "vs baseline", "session"))

    if iap_revenue_change_pct is None:
        missing.append("iap_revenue_change_pct")
    else:
        if iap_revenue_change_pct < -30:
            findings.append(Finding("IAP revenue dropped critically", "critical", "iap_revenue_change_pct", iap_revenue_change_pct, "%", -30.0, "vs baseline", "purchase"))
            root_causes.append("Play billing issue or user churn")
            actions.append("contact_store")
        elif iap_revenue_change_pct < -20:
            findings.append(Finding("IAP revenue declining", "warning", "iap_revenue_change_pct", iap_revenue_change_pct, "%", -20.0, "vs baseline", "purchase"))

    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant activity issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


# ---------------------------------------------------------------------------
# D-A Feedback: Android in-app feedback
# ---------------------------------------------------------------------------

def evaluate_d_a_feedback(
    volume_change_pct: Optional[float],
    sentiment_mean: Optional[float],
    crash_complaint_count: int,
) -> ScanVerdict:
    """Evaluate D-A Feedback rules (Android)."""
    findings: list[Finding] = []
    root_causes: list[str] = []
    actions: list[str] = []
    missing: list[str] = []

    if volume_change_pct is None:
        missing.append("volume_change_pct")
    else:
        if volume_change_pct < -50:
            findings.append(Finding("Feedback volume dropped critically", "critical", "volume_change_pct", volume_change_pct, "%", -50.0, "vs baseline", "feedback"))
            root_causes.append("User disengagement or collection issue")
            actions.append("investigate_data_pipeline")
        elif volume_change_pct < -25:
            findings.append(Finding("Feedback volume dropped", "warning", "volume_change_pct", volume_change_pct, "%", -25.0, "vs baseline", "feedback"))

    if sentiment_mean is None:
        missing.append("sentiment_mean")
    else:
        if sentiment_mean < 0.0:
            findings.append(Finding("Mean sentiment negative", "critical", "sentiment_mean", sentiment_mean, "score", 0.0, "current window", "feedback"))
            root_causes.append("Widespread dissatisfaction")
            actions.append("review_recent_changes")
        elif sentiment_mean < 0.3:
            findings.append(Finding("Mean sentiment low", "warning", "sentiment_mean", sentiment_mean, "score", 0.3, "current window", "feedback"))

    if crash_complaint_count >= 10:
        findings.append(Finding("Crash-related complaints", "critical", "crash_complaint_count", float(crash_complaint_count), "count", 10.0, "current window", "feedback"))
        root_causes.append("Crashes driving negative feedback")
        actions.append("triage_crash_cluster")

    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    if critical_count > 0:
        status = ScanStatus.CRITICAL
    elif warning_count > 0:
        status = ScanStatus.WARNING
    else:
        status = ScanStatus.HEALTHY

    confidence = "high" if not missing else "medium"

    return ScanVerdict(
        status=status,
        findings=findings,
        root_causes=root_causes[:3] or ["No significant feedback issues detected"],
        actions=actions[:4] or ["no_action"],
        confidence=confidence,
        missing_data=missing,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def run_stage1_scan(subsection: str, data: dict[str, Any]) -> ScanVerdict:
    """Dispatch to the appropriate rule evaluator for a subsection."""
    dispatch = {
        "A_W_HEALTH": evaluate_a_w_health,
        "C_W_SECURITY": evaluate_c_w_security,
        "A_A_HEALTH": evaluate_a_a_health,
        "C_A_SECURITY": evaluate_c_a_security,
        "D_W_FEEDBACK": evaluate_d_w_feedback,
        "B_W_ACTIVITY": evaluate_b_w_activity,
        "B_A_ACTIVITY": evaluate_b_a_activity,
        "D_A_FEEDBACK": evaluate_d_a_feedback,
    }

    evaluator = dispatch.get(subsection)
    if not evaluator:
        return ScanVerdict(
            status=ScanStatus.ERROR,
            findings=[],
            root_causes=[f"Unknown subsection: {subsection}"],
            actions=["no_action"],
            confidence="low",
            missing_data=[f"Unknown subsection: {subsection}"],
        )

    # Extract relevant data from the collected metrics
    return evaluator(**data)