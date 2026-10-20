"""Shared MCP core: the only code inside `mcp/` that is not one specific MCP.

Carries the read-only contract every tool inherits — permission scoping per
scan subsection, a per-call timeout, a row cap, credential-table refusals and
mandatory `telemetry.tool_call_audit` logging written *before* the tool's
response reaches the caller. A tool that fails tells the audit log; it never
fails silently and never lies afterwards.

On top of that sit the egress rules: `redact` masks and pseudonymizes every
value that leaves a tool, `jobs` decides what kind of work may talk to a model
at all, and `llm` is the one outbound path to a provider.
"""
from mcp.core.jobs import JOB_KINDS, JobContext, JobRefused, validate_job
from mcp.core.queries import ToolNotPermitted, assert_read_query

# NOTE: the `redact` *module* is deliberately not shadowed here. `from mcp.core
# import redact` must keep yielding the module (the callers walk it for
# `redact_value` / `redact_counted`), so the package exports the helpers under
# their own names and leaves the submodule attribute alone.
from mcp.core.redact import pseudonymize_id, redact_value, salt_for
from mcp.core.registry import (
    EGRESS_ROW_CAP,
    TOOL_TIMEOUT_S,
    ToolError,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    ToolTimeout,
    run_tool,
    write_audit,
)

__all__ = [
    "EGRESS_ROW_CAP",
    "JOB_KINDS",
    "TOOL_TIMEOUT_S",
    "JobContext",
    "JobRefused",
    "ToolError",
    "ToolNotPermitted",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "ToolTimeout",
    "assert_read_query",
    "pseudonymize_id",
    "redact_value",
    "run_tool",
    "salt_for",
    "validate_job",
    "write_audit",
]
