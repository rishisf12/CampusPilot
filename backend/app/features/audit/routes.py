"""Audit log routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.audit import service

router = APIRouter(prefix="/admin/audit", tags=["Admin - Audit"])


class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int]
    actor_email: Optional[str]
    actor_role: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    before_json: Optional[dict]
    after_json: Optional[dict]
    ip_hash: Optional[str]
    user_agent_hash: Optional[str]
    request_id: Optional[str]
    created_at: str


class AuditListResponse(BaseModel):
    total: int
    page: int
    size: int
    logs: list[AuditLogResponse]


@router.get("", response_model=AuditListResponse)
def admin_list_audit_logs(
    search: Optional[str] = None,
    action: Optional[str] = None,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 200))
    rows, total = service.list_audit_logs(
        session, search, action, actor_id, target_type, target_id, page, size
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "logs": [service.to_public(r) for r in rows],
    }


@router.get("/export")
def admin_export_audit_logs(
    search: Optional[str] = None,
    action: Optional[str] = None,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    from fastapi.responses import StreamingResponse
    import io

    logs = service.export_audit_logs(session, search, action, actor_id, target_type, target_id)

    if format == "csv":
        output = io.StringIO()
        output.write("id,actor_id,actor_email,actor_role,action,target_type,target_id,before_json,after_json,ip_hash,user_agent_hash,request_id,created_at\n")
        for log in logs:
            output.write(
                f"{log.id},{log.actor_id or ''},{log.actor_email or ''},{log.actor_role or ''},{log.action},"
                f"{log.target_type or ''},{log.target_id or ''},{log.before_json or ''},{log.after_json or ''},"
                f"{log.ip_hash or ''},{log.user_agent_hash or ''},{log.request_id or ''},{log.created_at}\n"
            )
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )
    else:
        return StreamingResponse(
            io.BytesIO(str(logs).encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_log.json"},
        )