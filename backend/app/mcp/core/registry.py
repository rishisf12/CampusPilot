"""Tool registry for the house-built MCPs.

A tool is a callable plus a `ToolSpec` naming which scan subsections may invoke
it. The registry is the only way a scan gets data: subsection scoping, the
per-call timeout and the row cap are enforced here, server-side, so a scan can
neither ask for another subsection's tool nor hang the worker on a wedged one.

Every executed call — success, refusal, timeout or crash — lands in
`telemetry.tool_call_audit` before anything is returned. That table is the
evidence trail for the read-only claim (SCAN-AGENT.md §4): if no write appears
there, nothing did one.
"""
from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from sqlmodel import Session

from features.monitoring.domain.models import ToolCallAudit
from mcp.core import redact as _redaction

logger = logging.getLogger(__name__)

#: A hung tool must not hold the scan worker. Mirrors SCAN-AGENT.md rule 2.
TOOL_TIMEOUT_S = 5.0

#: Hard ceiling on rows a single call may return (SCAN-AGENT.md rule 5).
ROW_CAP = 10_000

#: What crosses `run_tool` is the model's viewport, so list-typed data is
#: additionally capped here (architecture rule 2). Tools that need to reason
#: over more rows return aggregates instead of raw rows (Phase 5 tools).
EGRESS_ROW_CAP = 50

#: The eight scan subsections.
SUBSECTIONS = (
    "A_W_HEALTH",
    "B_W_ACTIVITY",
    "C_W_SECURITY",
    "D_W_FEEDBACK",
    "A_A_HEALTH",
    "B_A_ACTIVITY",
    "C_A_SECURITY",
    "D_A_FEEDBACK",
)


class ToolError(Exception):
    """Base class for MCP tool failures."""


class ToolNotPermitted(ToolError):
    """The scan's subsection may not call this tool (or the query is forbidden)."""


class ToolTimeout(ToolError):
    """The tool exceeded its time budget; the audit log records it as failed."""


@dataclass(frozen=True)
class ToolResult:
    """What a tool callable returns. `metric_key` feeds the reconciler."""

    data: Any
    row_count: int = 0
    metric_key: str | None = None

    def __post_init__(self) -> None:
        if self.row_count > ROW_CAP:
            # Enforced here rather than at the DB layer because tools may
            # aggregate: a "row_count" above the cap means the tool itself
            # misbehaved, and its data cannot be trusted either.
            raise ToolError(f"row_count {self.row_count} exceeds cap {ROW_CAP}")


@dataclass(frozen=True)
class ToolSpec:
    """A tool's declared identity and permitted callers."""

    name: str
    #: Which subsections may call it. `SUBSECTIONS` itself means "the manager
    #: duty tool every scan may use".
    subsections: frozenset[str] = field(default=frozenset(SUBSECTIONS))
    #: Docs only: tools must be read-only anyway, but the declaration doubles as
    #: the line the auditors read.
    read_only: bool = True

    def permitted_for(self, subsection: str) -> "ToolSpec":
        """Return self, or raise if that tool may not serve this subsection."""
        if subsection not in self.subsections:
            raise ToolNotPermitted(
                f"tool {self.name!r} is not permitted for subsection {subsection}"
            )
        return self


class ToolRegistry:
    """Name -> (spec, callable). Registration is explicit; nothing is guessed."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, Callable[..., ToolResult]]] = {}

    def register(self, spec: ToolSpec, fn: Callable[..., ToolResult]) -> None:
        if not spec.name:
            raise ValueError("tool name must be non-empty")
        if spec.name in self._tools:
            raise ValueError(f"tool {spec.name!r} registered twice")
        unknown = spec.subsections - set(SUBSECTIONS)
        if unknown:
            raise ValueError(f"unknown subsections for {spec.name}: {sorted(unknown)}")
        self._tools[spec.name] = (spec, fn)

    def has(self, name: str) -> bool:
        return name in self._tools

    def permitted(self, name: str, subsection: str) -> ToolSpec:
        """Return the spec, or raise if the subsection may not use the tool."""
        spec, _ = self.resolve(name)
        return spec.permitted_for(subsection)

    def resolve(self, name: str) -> tuple[ToolSpec, Callable[..., ToolResult]]:
        """The (spec, callable) for `name`, or `ToolNotPermitted` if unregistered."""
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotPermitted(f"tool {name!r} is not registered") from None

    def names(self) -> list[str]:
        """Registered tool names, sorted — the HTTP endpoint's tool list."""
        return sorted(self._tools)


#: One salt per scan run: tools called under the same `scan_id` share it, so
#: identical identifiers pseudonymize identically *within* a run (the model can
#: count recurrences) while different runs stay unlinkable. Cleared when large
#: - scan ids are per-run, so the map is bounded by runs, not by calls.
_RUN_SALTS: dict[str, str] = {}


def _salt_for(scan_id: str) -> str:
    salt = _RUN_SALTS.get(scan_id)
    if salt is None:
        if len(_RUN_SALTS) >= 4_096:
            _RUN_SALTS.clear()
        salt = uuid.uuid4().hex
        _RUN_SALTS[scan_id] = salt
    return salt


def _egress(result: ToolResult, salt: str) -> tuple[ToolResult, dict[str, Any]]:
    """The single egress point: redact + pseudonymize + cap rows (anonymization optics).

    Returns the (possibly rebuilt) result and the metadata that goes into the
    audit row. Every tool inherits this - there is no second path in or out.
    """
    data, redactions = _redaction.redact_value(result.data, salt)
    truncated = False
    if isinstance(data, list) and len(data) > EGRESS_ROW_CAP:
        data = data[:EGRESS_ROW_CAP]
        truncated = True
    if redactions or truncated:
        result = replace(result, data=data)
    meta = {
        "salt": salt,
        "redactions": redactions,
        "truncated": truncated,
    }
    return result, meta


def run_tool(
    session: Session,
    registry: ToolRegistry,
    *,
    scan_id: str | None = None,
    subsection: str,
    name: str,
    timeout_s: float = TOOL_TIMEOUT_S,
    args: dict[str, Any] | None = None,
) -> ToolResult:
    """
    Execute one tool call with the full read-only contract applied.

    Returns the `ToolResult` or raises `ToolError`. Whatever happens — success,
    refusal, timeout, crash — a `ToolCallAudit` row is written first. Passing
    `scan_id=None` is for privileged non-scan callers (an admin probe); the
    audit row still records the call with a synthetic id.

    On success the data passes through `_egress` before it is returned: no
    caller of this function - model, scan, dashboard, test - can observe a raw
    row. The per-run salt and the redaction count go into the audit row's
    `egress` key (formal columns land in the Phase 4 migration).
    """
    resolved_scan_id = scan_id or f"manual-{uuid.uuid4().hex[:12]}"

    started = time.monotonic()
    ok, error, value, rows, metric_key = False, None, None, 0, None
    egress_meta: dict[str, Any] | None = None
    held_pool = True  # cleared on timeout: the worker must not wait on a wedged tool
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mcp-tool")
    try:
        spec, fn = registry.resolve(name)  # subsection scoping checked next
        spec.permitted_for(subsection)
        future = pool.submit(fn, session, **(args or {}))
        try:
            result = future.result(timeout=timeout_s)
        except FutureTimeoutError:
            # A wedge must not hold the scan worker (SCAN-AGENT.md rule 2). The
            # abandoned thread drains in the background - tools must be pure
            # reads, so at worst it re-reads what it was about to read anyway -
            # but control returns to the caller now and the audit records the
            # call as failed.
            held_pool = False
            raise ToolTimeout(f"tool {name!r} exceeded {timeout_s}s budget") from None
        result, egress_meta = _egress(result, _salt_for(resolved_scan_id))
        value, rows, metric_key = result.data, result.row_count, result.metric_key
        ok = True
        return result
    except ToolError as exc:
        error = str(exc)
        raise
    except Exception as exc:  # noqa: BLE001 - the tool can raise anything
        error = f"{type(exc).__name__}: {exc}"
        raise ToolError(f"tool {name!r} failed: {error}") from exc
    finally:
        pool.shutdown(wait=held_pool, cancel_futures=True)
        duration_ms = int((time.monotonic() - started) * 1000)
        audit_args: dict[str, Any] = dict(args or {})
        if egress_meta is not None:
            audit_args["egress"] = egress_meta
        _audit(
            session,
            scan_id=resolved_scan_id,
            tool=name,
            args=audit_args,
            metric_key=metric_key,
            row_count=rows,
            duration_ms=duration_ms,
            ok=ok,
            error=error,
        )


def _audit(
    session: Session,
    *,
    scan_id: str,
    tool: str,
    args: dict[str, Any],
    metric_key: str | None,
    row_count: int,
    duration_ms: int,
    ok: bool,
    error: str | None,
) -> None:
    """Write the audit row, then commit. Written even when the tool refused.

    `args` is deliberately reduced to JSON-safe values: a caller passing a
    datetime or any other object must not be able to crash the audit trail —
    the row has to exist for the reconciler's read-only claim to stand.
    """
    import json

    session.add(
        ToolCallAudit(
            scan_id=scan_id,
            tool=tool,
            args=json.loads(json.dumps(args, default=str)),
            metric_key=metric_key,
            row_count=row_count,
            duration_ms=duration_ms,
            ok=ok,
            error=error,
        )
    )
    session.commit()
