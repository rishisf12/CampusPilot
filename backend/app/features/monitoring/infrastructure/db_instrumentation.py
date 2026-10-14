"""Time every SQL statement into the Prometheus DB instruments.

`DB_QUERY_DURATION` and `DB_QUERIES` are declared in `metrics.py` and were
never incremented by anything, so the "DB performance" figures the Health
subsection is documented to read from them were permanently empty - the same
gap as `health_metric` having no writer.

Timing is done with SQLAlchemy's cursor events rather than by wrapping
`Session.exec`, because a wrapper only sees calls that go through it and would
miss anything using `session.execute` or a raw connection.

Three details that matter:

* **Nested statements use a stack, not a single slot.** A statement that itself
  emits SQL (a cascade, an event hook) would otherwise overwrite the outer
  start time and attribute the inner duration to the outer statement.
* **Failures are still counted.** A statement that raises is exactly the slow
  statement an admin needs to see, so the `after` hook is not the only place
  that observes; the outcome label comes from the exception handler.
* **Parameter values are never read.** Only the statement's SQL text decides the
  `operation` label, because a value-derived label would carry user data into a
  metrics store and blow up cardinality.
"""

from __future__ import annotations

import logging
import re
import time

from sqlalchemy import event
from sqlalchemy.engine import Engine

from features.monitoring.infrastructure import metrics as M

logger = logging.getLogger(__name__)

_attached = False

#: Leading keyword -> coarse operation label. Deliberately coarse: the number of
#: distinct labels is the cardinality, and `route` already provides the detail.
_LEADING = re.compile(r"^\s*(?:/\*.*?\*/\s*)?(\w+)", re.DOTALL)


def classify(sql: str) -> str:
    """Map a statement to a small, bounded set of operation labels."""
    match = _LEADING.match(sql or "")
    verb = (match.group(1).lower() if match else "other")
    if verb in ("select",):
        return "select"
    if verb in ("insert",):
        return "insert"
    if verb in ("update",):
        return "update"
    if verb in ("delete",):
        return "delete"
    if verb == "with":
        return "select"
    return verb or "other"


def attach() -> None:
    """Install the listeners once. Safe to call repeatedly."""
    global _attached
    if _attached:
        return

    @event.listens_for(Engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        # A stack, so a nested statement cannot clobber the outer start time.
        conn.info.setdefault("_cp_query_stack", []).append(time.perf_counter())

    @event.listens_for(Engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        stack = conn.info.get("_cp_query_stack")
        if not stack:
            return
        elapsed = time.perf_counter() - stack.pop()
        operation = classify(statement)
        M.DB_QUERY_DURATION.labels(operation).observe(elapsed)
        M.DB_QUERIES.labels(operation, "ok").inc()

    @event.listens_for(Engine, "handle_error")
    def _error(ctx):  # noqa: ANN001
        # `ctx.connection` is the Connection the failing statement ran on.
        try:
            stack = ctx.connection.info.get("_cp_query_stack")
            if not stack:
                return
            elapsed = time.perf_counter() - stack.pop()
            operation = classify(ctx.statement or "")
            M.DB_QUERY_DURATION.labels(operation).observe(elapsed)
            M.DB_QUERIES.labels(operation, "error").inc()
        except Exception:
            # An instrumentation failure must never mask the original error.
            logger.debug("db query instrumentation failed", exc_info=True)

    _attached = True
    logger.info("database query instrumentation attached")