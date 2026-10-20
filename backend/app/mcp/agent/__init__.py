"""The scan agent: tools in, a reconciled verdict out.

`runtime` runs a subsection's scan (tools, model, reconciliation, honest
failure), and `reconcile` is the pass that catches a fabricated number by
checking every cited value against the audit trail.
"""
from mcp.agent.reconcile import ReconcileError, reconcile
from mcp.agent.runtime import SUBSECTION_TOOLS, run_scan

__all__ = [
    "SUBSECTION_TOOLS",
    "ReconcileError",
    "reconcile",
    "run_scan",
]
