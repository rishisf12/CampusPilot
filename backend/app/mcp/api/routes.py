"""The optional HTTP MCP endpoint.

An operator console can list the scan tools and call them - but only an
admin, and only when the endpoint is switched on (`ENABLE_ADMIN_MCP=true`,
off by default). The rules:

- **Off by default.** With the flag false the router is not mounted at all,
  so the paths do not exist rather than existing and refusing.
- **A student token sees nothing.** The tool list is empty for anyone who
  is not an admin: no names, no parameters, no hint that tools exist. A
  student who guesses the path still cannot call one.
- **The same contract as the scan.** Calls go through `run_tool`, so the
  subsection scoping, the timeout, the row cap and the egress gate all
  apply, and every call is audited.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.deps import get_current_user
from core.database import get_session
from mcp.core.registry import SUBSECTIONS, ToolError, run_tool

router = APIRouter()


class ToolCallRequest(BaseModel):
    """One tool call, as an operator console would make it."""

    tool: str = Field(min_length=1, max_length=64)
    #: The scan subsection asking. The registry refuses a tool that belongs
    #: to another subsection, so this is not a privilege - it is a filter.
    subsection: str = Field(min_length=1, max_length=16)
    args: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    ok: bool
    data: Optional[Any] = None
    row_count: int = 0
    metric_key: Optional[str] = None
    error: Optional[str] = None


def _is_admin(user: Any) -> bool:
    return (getattr(user, "role", None) or "student") == "admin"


@router.get("/tools")
def list_tools(_user=Depends(get_current_user)) -> dict[str, Any]:
    """The tools this caller may use. Empty for anyone who is not an admin."""
    from mcp.monitoring import REGISTRY

    user = _user
    if not _is_admin(user):
        # Not a 403: a student is not told that a toolbox exists.
        return {"tools": []}
    tools = []
    for name in REGISTRY.names():
        spec, _fn = REGISTRY.resolve(name)
        tools.append({"name": name, "subsections": sorted(spec.subsections)})
    return {"tools": tools}


@router.post("/call", response_model=ToolCallResponse)
def call_tool(
    payload: ToolCallRequest,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> ToolCallResponse:
    """Run one tool. Admin only; every call is audited like any other."""
    from mcp.monitoring import REGISTRY

    user = _user
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    if payload.subsection not in SUBSECTIONS:
        raise HTTPException(status_code=400, detail="Unknown scan subsection")
    try:
        result = run_tool(
            session,
            REGISTRY,
            scan_id=f"mcp-console-{payload.subsection}",
            subsection=payload.subsection,
            name=payload.tool,
            args=payload.args,
        )
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ToolCallResponse(
        ok=True,
        data=result.data,
        row_count=result.row_count,
        metric_key=result.metric_key,
    )
