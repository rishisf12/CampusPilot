"""Shared MCP core: the only code inside `mcp/` that is not one specific MCP.

Carries the read-only contract every tool inherits — permission scoping per
scan subsection, a per-call timeout, a row cap, credential-table refusals and
mandatory `telemetry.tool_call_audit` logging written *before* the tool's
response reaches the caller. A tool that fails tells the audit log; it never
fails silently and never lies afterwards.
"""
from mcp.core.queries import ToolNotPermitted, assert_read_query
from mcp.core.registry import (
    TOOL_TIMEOUT_S,
    ToolError,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    ToolTimeout,
    run_tool,
)

__all__ = [
    "TOOL_TIMEOUT_S",
    "ToolError",
    "ToolNotPermitted",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "ToolTimeout",
    "assert_read_query",
    "run_tool",
]
