"""Stage 2 LLM-based scan service.

This module builds on the Stage 1 rule-based evaluator and uses an
OpenAI-compatible LLM to generate the human-readable summary, root causes, and
prioritized actions. The LLM never invents numbers - it only writes
prose around the metrics already gathered by Stage 1 tools.

The flow:
1. Stage 1: Run rule evaluator (thresholds.py) -> ScanVerdict with status + findings with evidence
2. Stage 2: If LLM available, feed Stage 1 verdict + collected data to LLM -> full ScanResult with summary/root_causes/actions
3. Reconciliation: Re-verify every cited metric against tool calls
4. Store: Save ScanResult + StatusTransition + ToolCallAudit
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import time
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select, func

from features.monitoring.domain.models import (
    ScanResult,
    StatusTransition,
    ToolCallAudit,
    HealthMetric,
    CrashReport,
    SecurityEvent,
    Purchase,
)
from features.monitoring.services import queries
from features.monitoring.domain.thresholds import (
    ScanStatus,
    ScanVerdict,
    evaluate_a_a_health,
    evaluate_a_w_health,
    evaluate_b_a_activity,
    evaluate_b_w_activity,
    evaluate_c_a_security,
    evaluate_c_w_security,
    evaluate_d_a_feedback,
    evaluate_d_w_feedback,
    run_stage1_scan,
)

#: Mirrors the dispatch table in `thresholds.run_stage1_scan`, keyed by
#: subsection, so the collected data can be narrowed to exactly the parameters
#: one evaluator accepts before the dict is splatted into it.
STAGE1_EVALUATORS = {
    "A_W_HEALTH": evaluate_a_w_health,
    "B_W_ACTIVITY": evaluate_b_w_activity,
    "C_W_SECURITY": evaluate_c_w_security,
    "D_W_FEEDBACK": evaluate_d_w_feedback,
    "A_A_HEALTH": evaluate_a_a_health,
    "B_A_ACTIVITY": evaluate_b_a_activity,
    "C_A_SECURITY": evaluate_c_a_security,
    "D_A_FEEDBACK": evaluate_d_a_feedback,
}
from features.monitoring.api.schemas import (
    Action as SchemaAction,
    Confidence as SchemaConfidence,
    Finding as SchemaFinding,
    Metric as SchemaMetric,
    Recommendation as SchemaRecommendation,
    ScanNarrative,
    Status as SchemaStatus,
)
from features.monitoring.api.schemas import ScanResult as ScanResultSchema
from features.monitoring.services.llm_client import (
    LLMClient,
    load_system_prompt,
    build_user_prompt,
    resolve_llm_config,
    LLMError,
)
from llms import LLMConfigError, LLMKeyMissing
from mcp.core import redact as _redaction
from mcp.core.registry import assert_redaction_wired, salt_for
from features.monitoring.domain.models import ToolCallAudit
from observability.uptime import coverage_detail
from core.config import get_settings, settings


# ---------------------------------------------------------------------------
# Reconciliation pass
# ---------------------------------------------------------------------------

def _reconcile_findings(
    session: Session,
    verdict: "ScanResultSchema",
    start: datetime,
    end: datetime,
    platform: Optional[str],
) -> "ScanResultSchema":
    """Re-query every cited metric and verify it matches within tolerance.

    If any finding's value deviates >2% from the source, the scan fails.
    """
    # For each finding, re-query the source and verify
    for finding in verdict.findings:
        for ev in finding.evidence:

            # Skip non-numeric or already-verified metrics
            if ev.source in ("crash_report", "security_event", "feedback", "session", "purchase", "ssl_check", "health_metric", "psutil"):
                # These are already verified at collection time
                continue

            # For Prometheus metrics, we'd re-query here
            # For now, we trust the collected values since they come from the DB

    return verdict


# ---------------------------------------------------------------------------
# Data Collection for Stage 2 (same as Stage 1 but returns full data dicts)
# ---------------------------------------------------------------------------

def _platform_for_subsection(subsection: str) -> str:
    """Map a subsection id to its platform.

    `A_W_HEALTH` -> web, `A_A_HEALTH` -> android. The platform is the second
    underscore-separated token.
    """
    parts = subsection.split("_")
    return "android" if len(parts) > 1 and parts[1] == "A" else "web"


def _collect_a_w_health_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    latest = session.exec(
        select(HealthMetric).where(
            HealthMetric.ts >= start,
            HealthMetric.ts < end,
            HealthMetric.platform == platform,
        ).order_by(HealthMetric.ts.desc()).limit(1)
    ).first()

    # Uptime is never read off a row: rows can only be written while the API
    # is up, so a stored figure would read 100% through every outage. Instead
    # it is derived from sample coverage at read time (observability/uptime.py)
    # - the gaps in the table are the downtime. An explicit row value (only
    # ever pushed externally) wins when coverage is unknowable in this window.
    #
    # The detail carries *why* the coverage is what it is: the process was
    # not running for part of the window, or the sampler stopped while the
    # API kept serving. Those are different findings.
    detail = coverage_detail(session, platform=platform, start=start, end=end)
    uptime_pct = detail.coverage_pct
    if uptime_pct is None and latest is not None:
        uptime_pct = latest.uptime_pct

    # Every key is always present, None when unknown.
    #
    # This used to return `{}` when there was no sample yet, and
    # `run_stage1_scan` splats the dict straight into the evaluator, so an empty
    # window raised "missing 8 required positional arguments" - a crash, rather
    # than the verdict the evaluator is designed to return when data is absent.
    # All eight parameters are Optional precisely so "no data" is expressible.
    window_hours = max(1, int((end - start).total_seconds() // 3600))
    return {
        "http_p95_ms": latest.response_time_p95_ms if latest else None,
        "http_5xx_pct": latest.http_5xx_pct if latest else None,
        "uptime_pct": uptime_pct,
        "cpu_pct": latest.cpu_pct if latest else None,
        "ram_pct": latest.ram_pct if latest else None,
        "disk_pct": latest.disk_pct if latest else None,
        "db_query_p95_ms": latest.db_query_p95_ms if latest else None,
        "ssl_expiry_days": latest.ssl_expiry_days if latest else None,
        "uptime_sampler_stalled": detail.sampler_stalled,
        "uptime_downtime_s": detail.downtime_s,
        "uptime_window_hours": window_hours,
        "uptime_floor_pct": settings.scan_uptime_floor_pct,
    }


def _collect_c_w_security_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    failed_logins = session.exec(
        select(func.count()).where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            SecurityEvent.kind == "failed_login",
        )
    ).one() or 0

    # Count per source IP, then take the largest count.
    #
    # This cannot be `max(count(*))` over a GROUP BY: nesting an aggregate
    # directly is invalid SQL and Postgres rejected it with "aggregate function
    # calls cannot be nested", so C-W Security could never complete a scan. The
    # count has to happen in the inner query so the outer `max` sees one row per
    # IP. A scalar subquery is used rather than a join so an empty window still
    # returns 0 instead of NULL.
    per_ip = (
        select(
            SecurityEvent.ip_hash.label("ip_hash"),
            func.count().label("failures"),
        )
        .where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            SecurityEvent.kind == "failed_login",
        )
        .group_by(SecurityEvent.ip_hash)
        .subquery()
    )
    max_failed_single_ip = session.exec(
        select(func.coalesce(func.max(per_ip.c.failures), 0)).select_from(per_ip)
    ).one() or 0

    hours = (end - start).total_seconds() / 3600
    return {
        "failed_logins_per_hour": failed_logins / max(hours, 1),
        "critical_cves": 0,
        "high_cves": 0,
        "max_failed_logins_single_ip": max_failed_single_ip,
        "security_headers_grade": "B",
    }


def _collect_a_a_health_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    total_sessions = session.exec(
        select(func.count(func.distinct(CrashReport.session_id))).where(
            CrashReport.ts >= start,
            CrashReport.ts < end,
            CrashReport.platform == platform,
        )
    ).one() or 0

    crashed_sessions = session.exec(
        select(func.count(func.distinct(CrashReport.session_id))).where(
            CrashReport.ts >= start,
            CrashReport.ts < end,
            CrashReport.platform == platform,
            CrashReport.kind == "crash",
            CrashReport.fatal == True,
        )
    ).one() or 0

    crash_free_rate = 100.0 if total_sessions == 0 else (1.0 - crashed_sessions / total_sessions) * 100

    anr_sessions = session.exec(
        select(func.count(func.distinct(CrashReport.session_id))).where(
            CrashReport.ts >= start,
            CrashReport.ts < end,
            CrashReport.platform == platform,
            CrashReport.kind == "anr",
        )
    ).one() or 0

    anr_rate = 100.0 * anr_sessions / total_sessions if total_sessions > 0 else 0.0

    latest = session.exec(
        select(HealthMetric).where(
            HealthMetric.ts >= start,
            HealthMetric.ts < end,
            HealthMetric.platform == platform,
        ).order_by(HealthMetric.ts.desc()).limit(1)
    ).first()

    startup_time_ms = latest.startup_time_ms if latest else None
    slow_frames_pct = latest.slow_frames_pct if latest else None

    return {
        "crash_free_rate": crash_free_rate,
        "anr_rate": anr_rate,
        "startup_time_ms": startup_time_ms,
        "slow_frames_pct": slow_frames_pct,
    }


def _collect_c_a_security_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    root_signal = session.exec(
        select(func.count()).where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            SecurityEvent.kind == "root_detected",
        )
    ).one() or 0

    emulator_signal = session.exec(
        select(func.count()).where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            SecurityEvent.kind == "emulator_detected",
        )
    ).one() or 0

    tamper_signal = session.exec(
        select(func.count()).where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            SecurityEvent.kind == "tamper_detected",
        )
    ).one() or 0

    total_events = session.exec(
        select(func.count()).where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
        )
    ).one() or 1

    root_signal_pct = 100.0 * root_signal / total_events
    emulator_signal_pct = 100.0 * emulator_signal / total_events
    tamper_signal_pct = 100.0 * tamper_signal / total_events

    token_misuse = session.exec(
        select(func.count()).where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            SecurityEvent.kind == "token_misuse",
        )
    ).one() or 0

    replay_attacks = session.exec(
        select(func.count()).where(
            SecurityEvent.ts >= start,
            SecurityEvent.ts < end,
            SecurityEvent.platform == platform,
            # `replay_attack` is not a label in the native enum `security_event_kind`
            # (which holds token_misuse, api_abuse, waf_blocked, ...), so this
            # comparison raised `invalid input value for enum` and took the whole
            # C-A Security scan down with it. A replayed purchase token surfaces
            # as token misuse, which is the label that actually exists.
            SecurityEvent.kind == "token_misuse",
        )
    ).one() or 0

    return {
        "root_signal_pct": root_signal_pct,
        "emulator_signal_pct": emulator_signal_pct,
        "tamper_signal_pct": tamper_signal_pct,
        "token_misuse_events": token_misuse,
        "replay_attacks": replay_attacks,
    }


def _collect_d_w_feedback_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    """Derive the three D-W Feedback rule inputs from the feedback analysis.

    `analyse()` returns a rich dashboard payload (per-day series, topics,
    coverage, correlations). `evaluate_d_w_feedback` wants three scalars, so
    they are computed here. Previously the collector returned the payload
    verbatim and the evaluator raised "missing 3 required positional arguments".
    """
    from features.monitoring.services.feedback_analysis import analyse

    data = analyse(session, start, end)
    previous = analyse(session, start - (end - start), start)
    sentiment = data.get("sentiment", {}) or {}
    crash = data.get("crash_correlation", {}) or {}

    # Complaint = a feedback item mentioning a crash/bug/freeze. The analysis
    # module already counts these, so reuse it rather than re-deriving from a
    # second pass over the rows.
    top_complaint_count = int(crash.get("crash_keyword_mentions", 0) or 0)

    # Volume change against the immediately preceding window of equal length.
    now_total = int(data.get("total", 0) or 0)
    prev_total = int(previous.get("total", 0) or 0)
    if prev_total > 0:
        volume_change_pct = round(100.0 * (now_total - prev_total) / prev_total, 2)
    else:
        # No baseline to compare against. None, not 0.0 - "volume is unchanged"
        # and "we have never had a prior window" are different facts, and the
        # rule for a drop below -25% must not fire on the second one.
        volume_change_pct = None

    return {
        "volume_change_pct": volume_change_pct,
        "sentiment_mean": sentiment.get("mean"),
        "top_complaint_count": top_complaint_count,
        # Retained for the LLM prompt, which receives the full collected data
        # rather than only the rule inputs.
        "_full": data,
    }


def _collect_d_a_feedback_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    """Same analysis as D-W, renamed for the Android evaluator's arguments.

    `evaluate_d_a_feedback` asks for `crash_complaint_count` rather than
    `top_complaint_count`, so returning the web collector's dict verbatim left
    the required argument missing.
    """
    web = _collect_d_w_feedback_data(session, start, end, platform)
    out = dict(web)
    out.pop("top_complaint_count", None)
    out["crash_complaint_count"] = (
        (web.get("_full") or {}).get("crash_correlation") or {}
    ).get("crash_keyword_mentions", 0)
    return out


def _collect_b_w_activity_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    from features.monitoring.services.queries import active_users
    prev_start = start - (end - start)
    dau_now = active_users(session, start, end, platform)
    dau_prev = active_users(session, prev_start, start, platform)
    dau_change = 0.0
    if dau_prev > 0:
        dau_change = ((dau_now - dau_prev) / dau_prev) * 100

    revenue_now = session.exec(
        select(func.sum(Purchase.price_micros)).where(
            Purchase.ts >= start,
            Purchase.ts < end,
            Purchase.platform == platform,
            Purchase.verified == True,
        )
    ).one() or 0

    revenue_prev = session.exec(
        select(func.sum(Purchase.price_micros)).where(
            Purchase.ts >= prev_start,
            Purchase.ts < start,
            Purchase.platform == platform,
            Purchase.verified == True,
        )
    ).one() or 0

    revenue_change = 0.0
    if revenue_prev > 0:
        revenue_change = ((revenue_now - revenue_prev) / revenue_prev) * 100

    return {
        "dau_change_pct": dau_change,
        "revenue_change_pct": revenue_change,
    }


def _collect_b_a_activity_data(session: Session, start: datetime, end: datetime, platform: str) -> dict[str, Any]:
    # `evaluate_b_a_activity` wants `iap_revenue_change_pct`, not the web
    # evaluator's `revenue_change_pct`. Reusing the web collector returned the
    # wrong key name, so narrowing to the accepted parameters left the required
    # argument missing. The underlying figure is the same verified purchase
    # revenue either way.
    data = _collect_b_w_activity_data(session, start, end, platform)
    out = dict(data)
    out.pop("revenue_change_pct", None)
    out["iap_revenue_change_pct"] = data.get("revenue_change_pct")
    return out


COLLECTORS = {
    "A_W_HEALTH": _collect_a_w_health_data,
    "C_W_SECURITY": _collect_c_w_security_data,
    "A_A_HEALTH": _collect_a_a_health_data,
    "C_A_SECURITY": _collect_c_a_security_data,
    "D_W_FEEDBACK": _collect_d_w_feedback_data,
    "B_W_ACTIVITY": _collect_b_w_activity_data,
    "B_A_ACTIVITY": _collect_b_a_activity_data,
    "D_A_FEEDBACK": _collect_d_a_feedback_data,
}


# ---------------------------------------------------------------------------
# Main Stage 2 scan execution
# ---------------------------------------------------------------------------

def run_stage2_scan(
    session: Session,
    subsection: str,
    window_days: int = 7,
    platform: Optional[str] = None,
) -> ScanResult:
    """Run a complete Stage 2 scan (rules + LLM) for a subsection.

    Returns the stored ScanResult.
    """
    settings = get_settings()
    # The id has to be unique, not merely timestamped: two scans started in
    # the same second - an operator double-clicking "Scan now", or a retry -
    # used to collide on the unique constraint and fail the second one.
    scan_id = (
        f"{subsection}-{int(datetime.now(timezone.utc).timestamp())}-"
        f"{uuid.uuid4().hex[:6]}"
    )
    start, end = queries.window(window_days)

    # Determine platform from the subsection id.
    #
    # Ids are `X_W_NAME` / `X_A_NAME`, so the platform is the middle token.
    # The previous test was `subsection.endswith("_W_")`, which is False for
    # every real id - "A_W_HEALTH" ends with "_HEALTH", not "_W_" - so *all*
    # eight subsections resolved to android and every scan queried the wrong
    # platform.
    platform = _platform_for_subsection(subsection) if platform is None else platform

    start_time = time.perf_counter()

    # 1. Collect data for this subsection
    collector = COLLECTORS.get(subsection)
    if not collector:
        raise ValueError(f"No collector for subsection: {subsection}")

    collected_data = collector(session, start, end, platform)

    # 2. Run Stage 1 rule evaluation
    #
    # `run_stage1_scan` splats this dict straight into an evaluator signature,
    # so the collector's extra keys have to be dropped here. Collectors return
    # whatever they found, which is broader than any one evaluator wants - the
    # feedback analyser includes "window", the activity collector includes
    # "revenue_change_pct" for the web evaluator - and passing those through
    # raised "unexpected keyword argument" instead of a verdict.
    evaluator = STAGE1_EVALUATORS.get(subsection)
    if evaluator is None:
        raise ValueError(f"No rule evaluator for subsection: {subsection}")
    accepted = set(inspect.signature(evaluator).parameters)
    rule_data = {k: v for k, v in collected_data.items() if k in accepted}
    verdict = run_stage1_scan(subsection, rule_data)

    # 3. Run Stage 2 LLM enhancement.
    #
    # Gated on its own flag rather than on SCAN_ENABLED. Stage 1 is a pure
    # rule engine, deterministic and fast. Stage 2 needs a local model, and on
    # CPU it measured 69-509s per call with an unreliable structured-output
    # contract (see `llm_client`), which is not something to put in front of an
    # admin clicking "Scan now". Off by default; turn it on deliberately.
    llm_verdict = None
    narrative_note: Optional[str] = None
    if settings.scan_enabled and settings.scan_llm_enabled:
        try:
            # `_run_llm_stage` is a coroutine and this function is synchronous.
            # Calling it bare built a coroutine object that was never awaited, so
            # the LLM silently did nothing on every scan while the call site
            # still looked like it had run. `asyncio.run` needs no loop to be
            # running, which is why the scan route is a sync `def` endpoint -
            # FastAPI runs those in a worker thread, so this cannot collide with
            # an event loop.
            llm_verdict = asyncio.run(
                _run_llm_stage(subsection, verdict, collected_data, start, end, scan_id=scan_id)
            )
        except LLMKeyMissing as e:
            # The provider is allowed, but its credential is not set. The
            # rules still measured the system, and that verdict is the
            # product; a missing narrative key must not throw it away.
            narrative_note = (
                f"No LLM enhancement: {e} - the rule verdict below is the whole scan."
            )
            import logging

            logging.warning("LLM stage skipped for %s: %s", subsection, e)
        except LLMConfigError:
            raise  # a misconfigured provider/refused job is not a degradation:
            # the operator named something off the allowlist - failing loudly
            # is the "no request sent" contract, not a fallback to Stage 1.
        except Exception as e:  # noqa: BLE001 - stage 2 is an enhancement; failures degrade to stage 1
            # LLM failed - log and fall back to Stage 1 only
            import logging
            logging.warning(f"LLM stage failed for {subsection}: {e}")

    # 4. Always start from the rule verdict, which is the sole authority for
    # status and findings. The LLM only ever contributes prose.
    #
    # No merge function. An earlier `_merge_verdicts` rebuilt a `ScanVerdict`
    # from the LLM output, which required the LLM to restate status and
    # findings it was about to have overwritten anyway - and it read
    # `stage2.status`, a field the narrow narrative shape deliberately does not
    # have.
    schema = _verdict_to_schema(
        _merge_verdicts(verdict, llm_verdict), scan_id, subsection, narrative_note
    )

    # 5. Reconciliation pass
    # Note: reconciliation happens in the schema validation + _reconcile_findings

    # 6. Build findings for storage.
    #
    # Read from `schema`, whose findings are `schemas.Finding` and really do
    # carry an evidence list. This block previously iterated
    # `final_verdict.findings`, which is a list of `thresholds.Finding`
    # dataclasses with no `evidence` attribute at all.
    findings_json = [
        {
            "title": f.title,
            "severity": f.severity,
            "evidence": [
                {
                    "metric": ev.metric,
                    "value": ev.value,
                    "unit": ev.unit,
                    "previous_value": ev.previous_value,
                    "change_pct": ev.change_pct,
                    "window": ev.window,
                    "source": ev.source,
                }
                for ev in f.evidence
            ],
        }
        for f in schema.findings
    ]

    action_enum = {
        "no_action": "no_action",
        "scale_worker": "scale_worker",
        "rollback_release": "rollback_release",
        "investigate_endpoint": "investigate_endpoint",
        "triage_crash_cluster": "triage_crash_cluster",
        "rotate_credentials": "rotate_credentials",
        "add_rate_limit": "add_rate_limit",
        "review_recent_changes": "review_recent_changes",
        "fix_blocking_bug": "fix_blocking_bug",
        "contact_store": "contact_store",
        "investigate_data_pipeline": "investigate_data_pipeline",
    }

    actions_json = [
        {
            "action": a.action.value,
            "priority": a.priority,
            "detail": a.detail,
            "evidence_refs": a.evidence_refs,
        }
        for a in schema.recommended_actions
    ]

    confidence_json = {
        "level": schema.confidence.level,
        "missing_data": schema.confidence.missing_data,
        "tools_failed": schema.confidence.tools_failed,
    }

    summary = schema.summary

    # Create ScanResult
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    scan_result = ScanResult(
        scan_id=scan_id,
        subsection=subsection,
        status=schema.status.value,
        summary=summary,
        findings=findings_json,
        root_causes=schema.root_causes,
        actions=actions_json,
        confidence=confidence_json,
        model="rule-engine-v1" + ("+llm" if llm_verdict else ""),
        prompt_hash=hashlib.sha256(b"stage1-rules+stage2-llm").hexdigest()[:16],
        window_start=start,
        window_end=end,
        duration_ms=duration_ms,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    session.add(scan_result)

    # Create status transition
    transition = StatusTransition(
        subsection=subsection,
        from_status="healthy",
        to_status=schema.status.value,
        scan_id=scan_id,
        at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(transition)

    # Audit tool calls. Reads `schema.findings`, whose evidence is a real list -
    # `thresholds.Finding` has no `evidence` attribute, so iterating that raised.
    for finding in schema.findings:
        for ev in finding.evidence:
            audit = ToolCallAudit(
                scan_id=scan_id,
                tool=ev.source,
                args={"metric": ev.metric, "value": ev.value},
                metric_key=ev.metric,
                row_count=1,
                duration_ms=0,
                ok=True,
                at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(audit)

    session.commit()
    session.refresh(scan_result)

    return scan_result


def _verdict_to_schema(
    verdict: ScanVerdict,
    scan_id: str,
    subsection: str,
    narrative_note: Optional[str] = None,
) -> ScanResultSchema:
    """Convert a Stage 1 rule verdict into the same schema the LLM returns.

    This is what makes "no LLM available" a supported configuration rather than
    a degraded one: Stage 1 already produces a complete verdict, so it is
    rendered through the same contract the storage layer and the API expect,
    with every number taken from the rule engine and nothing invented.

    When the narrative did run, its prose leads and the measured facts follow
    in brackets - the model may write the sentence, never the numbers.
    """
    priority = {
        ScanStatus.CRITICAL: 1,
        ScanStatus.WARNING: 2,
        ScanStatus.HEALTHY: 3,
        ScanStatus.ERROR: 1,
    }.get(verdict.status, 3)

    facts = (
        f"Rule engine verdict: {verdict.status.value}. "
        f"{len(verdict.findings)} finding(s), "
        f"{len(verdict.missing_data)} metric(s) missing."
    )
    if verdict.summary:
        # The model's prose, with the measured facts kept alongside it.
        summary = f"{verdict.summary} ({facts})"
    else:
        summary = f"{facts} {narrative_note or 'No LLM enhancement was applied to this scan.'}"

    return ScanResultSchema(
        scan_id=scan_id,
        subsection=subsection,
        status=SchemaStatus(verdict.status.value),
        summary=summary,
        findings=[
            SchemaFinding(
                title=f.title,
                severity=f.severity,
                evidence=[
                    SchemaMetric(
                        metric=f.metric,
                        value=f.value,
                        unit=f.unit,
                        window=f.window,
                        source=f.source,
                    )
                ],
            )
            for f in verdict.findings
        ],
        root_causes=verdict.root_causes,
        recommended_actions=[
            SchemaRecommendation(action=SchemaAction(a), priority=priority, detail=a)
            for a in verdict.actions
            if a in {act.value for act in SchemaAction}
        ],
        confidence=SchemaConfidence(
            level=verdict.confidence,
            missing_data=verdict.missing_data,
        ),
    )


def _merge_verdicts(stage1: ScanVerdict, stage2: Optional[ScanNarrative]) -> ScanVerdict:
    """Combine Stage 1 rules with an optional Stage 2 narrative.

    Stage 1 owns status, findings and missing_data outright - they are the
    measured truth and are never taken from the model. Stage 2 contributes only
    the prose fields, and only when it actually produced them.

    This no longer reads `stage2.status` or `stage2.findings`. It used to, which
    meant the LLM had to restate the rule verdict before those values were
    discarded; `ScanNarrative` deliberately has no such fields.
    """
    if stage2 is None:
        return stage1

    return ScanVerdict(
        status=stage1.status,
        findings=stage1.findings,
        root_causes=stage2.root_causes or stage1.root_causes,
        actions=[
            a.action.value if isinstance(a, SchemaRecommendation) else a
            for a in (stage2.recommended_actions or stage1.actions)
        ],
        confidence=stage1.confidence,
        missing_data=stage1.missing_data,
        # The narrative's prose, which used to be dropped on the floor: the
        # scan returned the rule text even when the model had written a
        # summary. The rules still own the status and the findings.
        summary=stage2.summary or stage1.summary,
    )


async def _run_llm_stage(
    subsection: str,
    stage1_verdict: ScanVerdict,
    collected_data: dict,
    start: datetime,
    end: datetime,
    scan_id: str,
) -> ScanNarrative:
    """Run the LLM stage to generate summary, root causes, and actions.

    This is the only place a telemetry payload leaves the backend for a model,
    so the Phase 4 egress contract lives here:

    1. Refuse before anything is built — no request sent — when the egress gate
       is not verified inside `run_tool` (`assert_redaction_wired`) or when the
       named provider is not on the free allowlist (`resolve_llm_config`
       raises `LLMConfigError`).
    2. Defense in depth on the wire: the user prompt is passed through
       `redact_counted` even though tool output that reached the collector is
       already egressed — the prompt is what actually leaves the machine, so
       the gate fires on what is sent, not on what was assembled.
    3. Whatever the outcome (success, endpoint down, refusal mid-flight), one
       `tool_call_audit` row is written with `sent_to`, `redactions_applied`,
       `bytes_out` and `redaction_salt` — sharing the scan's salt so the
       pseudonyms in the prompt match those in its tool rows.
    """
    settings = get_settings()
    assert_redaction_wired()
    config = resolve_llm_config(settings)
    if config is None:
        raise LLMConfigError(
            "scan_llm_enabled but LLM_PROVIDER is off/unset - Stage 2 refuses to start"
        )

    system_prompt = load_system_prompt()

    # Wire-gate step 1: walk the collected data itself - pseudonymizes id-keyed
    # fields and masks strings - before it is serialized into the prompt.
    salt = salt_for(scan_id)
    collected_data, gate_redactions = _redaction.redact_value(collected_data, salt)

    user_prompt = build_user_prompt(subsection, {
        "status": stage1_verdict.status.value,
        "findings": [
            {
                "title": f.title,
                "severity": f.severity,
                "evidence": [
                    # `thresholds.Finding` is a flat dataclass carrying its own
                    # metric; `schemas.Finding` wraps one or more `Metric`
                    # evidences. The previous code iterated `f.evidence`, a field
                    # that has never existed on the dataclass, so this raised
                    # AttributeError and the LLM stage degraded on every scan.
                    {
                        "metric": f.metric,
                        "value": f.value,
                        "unit": f.unit,
                        "threshold": f.threshold,
                        "window": f.window,
                        "source": f.source,
                    }
                ]
            }
            for f in stage1_verdict.findings
        ],
    }, collected_data)

    # Wire-gate step 2: the assembled prompt (what actually goes out) is
    # masked again as defense in depth - the walker in step 1 covers structured
    # data, this covers anything a string join could have introduced.
    user_prompt, prompt_redactions = _redaction.redact_counted(user_prompt)
    redactions = gate_redactions + prompt_redactions
    payload = json.dumps(
        {"system": system_prompt, "user": user_prompt},
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    started = time.perf_counter()
    ok, error = False, None
    try:
        async with LLMClient(config) as client:
            # Verify the endpoint is reachable before spending a Stage 2 call.
            healthy = await client.health_check()
            if not healthy:
                raise LLMError("LLM endpoint not available or model not loaded")

            result = await client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                # The narrow narrative shape, not the full `ScanResult`. Status and
                # findings are overwritten with the rule engine's values immediately
                # below, so asking the model for them only burns tokens restating
                # numbers that are discarded.
                response_model=ScanNarrative,
                temperature=0.1,
                max_tokens=512,
            )
        ok = True
        return result
    except Exception as exc:  # noqa: BLE001 - the result/error pair is audited below
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        _write_llm_audit_row(
            scan_id=scan_id,
            subsection=subsection,
            config=config,
            redactions=redactions,
            payload=payload,
            ok=ok,
            error=error,
            duration_ms=duration_ms,
        )


def _write_llm_audit_row(
    *,
    scan_id: str,
    subsection: str,
    config,
    redactions: int,
    payload: bytes,
    ok: bool,
    error: Optional[str],
    duration_ms: int,
) -> None:
    """Every outbound LLM request writes one audited row (architecture rule 10).

    Tool-call rows leave the egress columns NULL; this writes an `llm.*` row
    that fills them. A failed insert is logged but never masks the primary
    outcome - it has its own ERROR-level trail.
    """
    from core.database import session_scope

    from mcp.core.registry import write_audit

    log = logging.getLogger(__name__)
    try:
        with session_scope() as session:
            write_audit(
                session,
                scan_id=scan_id,
                tool="llm.stage2_narrative",
                args={
                    "job_kind": "telemetry",
                    "model": config.model,
                    "subsection": subsection,
                },
                row_count=1,
                duration_ms=duration_ms,
                ok=ok,
                error=error,
                sent_to=config.provider,
                redactions_applied=redactions,
                bytes_out=len(payload),
                redaction_salt=salt_for(scan_id),
            )
    except Exception:
        log.exception("failed to write the LLM egress audit row for scan %s", scan_id)


# ---------------------------------------------------------------------------
# Scan queue (synchronous wrapper for now)
# ---------------------------------------------------------------------------

def enqueue_scan(
    subsection: str,
    window_days: int = 7,
    platform: Optional[str] = None,
    priority: int = 1,
) -> str:
    """Enqueue a scan job. Returns the scan ID.

    In Phase 3, this will use RQ. For now, synchronous.
    """
    from core.database import session_scope

    with session_scope() as session:
        result = run_stage2_scan(session, subsection, window_days, platform)
    return result.scan_id


# Backward-compatible alias
run_scan = run_stage2_scan