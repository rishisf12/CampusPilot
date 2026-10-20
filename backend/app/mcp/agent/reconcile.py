"""The reconciler: the pass that catches a fabricated number.

A model that says "p95 was 1.84 seconds" has to be *checkable*. The audit
trail is the record of what the tools actually returned, so this module
re-reads it and compares every cited number against it:

- a metric that no tool in this scan produced → the scan fails;
- a number that no tool returned (beyond tolerance) → the scan fails;
- a `change_pct` whose arithmetic does not match its two endpoints → the
  scan fails.

The tolerance is 2 %, which absorbs a model re-rounding a number on its way
into prose and still catches a number that was invented. A scan that fails
here is retried once and then stored as `error` - never as `healthy`.
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlmodel import Session, select

from features.monitoring.domain.models import ToolCallAudit

#: 2 % relative tolerance: float rounding and unit conversion are tolerated,
#: a model that picked a round number instead of reading it is not.
TOLERANCE = 0.02


class ReconcileError(RuntimeError):
    """A cited number could not be traced back to a tool call."""


def _close(a: float, b: float, rel: float = TOLERANCE, abs_: float = 0.001) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def _numbers(value: Any) -> list[float]:
    """Every number inside a tool's answer (the tool may return a scalar, a
    list of rows or a nested dict)."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        out: list[float] = []
        for item in value.values():
            out.extend(_numbers(item))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_numbers(item))
        return out
    return []


def _cited_value(result: Any, path: str) -> Any:
    """Follow a dotted path into a tool's answer (`a.b[0].c` and `a.b.0.c`)."""
    current = result
    for part in path.replace("[", ".").replace("]", "").split("."):
        if part == "":
            continue
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, (list, tuple)):
            try:
                index = int(part)
            except ValueError:
                return None
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def _audit_index(
    session: Session, scan_id: str
) -> tuple[dict[str, list[ToolCallAudit]], list[ToolCallAudit]]:
    """metric_key -> the audit rows of this scan, plus the rows themselves."""
    rows = session.exec(
        select(ToolCallAudit).where(
            ToolCallAudit.scan_id == scan_id,
            ToolCallAudit.ok.is_(True),
            ToolCallAudit.metric_key.is_not(None),
        )
    ).all()
    index: dict[str, list[ToolCallAudit]] = {}
    for row in rows:
        index.setdefault(row.metric_key, []).append(row)
    return index, list(rows)


def reconcile(
    session: Session,
    result: Any,
    *,
    scan_id: str | None = None,
    tolerance: float = TOLERANCE,
) -> Any:
    """Check every cited number against the audit trail.

    Raises `ReconcileError` with a precise reason when a number cannot be
    traced. Returns the result unchanged when everything checks out.
    """
    resolved_scan_id = scan_id or getattr(result, "scan_id", None)
    if not resolved_scan_id:
        raise ReconcileError("cannot reconcile: the result carries no scan id")
    index, _rows = _audit_index(session, resolved_scan_id)

    for finding in getattr(result, "findings", []) or []:
        for evidence in getattr(finding, "evidence", []) or []:
            metric = getattr(evidence, "metric", None)
            if not metric:
                raise ReconcileError("a finding cites an evidence metric with no name")
            value = getattr(evidence, "value", None)

            # The metric may be the tool's key, or a path into its answer.
            key, _, path = metric.partition(".")
            candidates = index.get(key) or index.get(metric)
            if not candidates:
                raise ReconcileError(
                    f"cited metric {metric!r} was never fetched by any tool in "
                    f"scan {resolved_scan_id!r}"
                )

            actuals: list[float] = []
            for row in candidates:
                payload = row.metric_value
                if path:
                    target = _cited_value(payload, path)
                    actuals.extend(_numbers(target))
                else:
                    actuals.extend(_numbers(payload))

            if not actuals:
                raise ReconcileError(
                    f"tool {key!r} returned no value for {metric!r} to check"
                )
            if not any(_close(actual, float(value), rel=tolerance) for actual in actuals):
                raise ReconcileError(
                    f"{metric!r}: the model said {value}, the tool said "
                    f"{_nearest(actuals, float(value))} - outside {tolerance:.0%}"
                )

            # `change_pct` is arithmetic, not opinion: it must match its two
            # endpoints, or the model made it up.
            change = getattr(evidence, "change_pct", None)
            previous = getattr(evidence, "previous_value", None)
            if change is not None:
                if previous is None:
                    raise ReconcileError(
                        f"{metric!r} claims a change of {change}% without a "
                        "previous value"
                    )
                if float(previous) == 0:
                    raise ReconcileError(
                        f"{metric!r} claims a change of {change}% against a "
                        "previous value of zero"
                    )
                expected = (float(value) - float(previous)) / abs(float(previous)) * 100.0
                if not _close(expected, float(change), rel=tolerance, abs_=0.5):
                    raise ReconcileError(
                        f"{metric!r}: change of {change}% does not match its "
                        f"endpoints (expected {expected:.2f}%)"
                    )

    return result


def _nearest(values: Iterable[float], target: float) -> float:
    return min(values, key=lambda v: abs(v - target))
