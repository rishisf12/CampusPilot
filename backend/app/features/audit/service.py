"""Audit log service."""
from __future__ import annotations
from typing import Optional
from sqlmodel import Session, select
from sqlalchemy import or_

from features.audit.models import AuditLog


def list_audit_logs(
    session: Session,
    search: Optional[str],
    action: Optional[str],
    actor_id: Optional[int],
    target_type: Optional[str],
    target_id: Optional[str],
    page: int,
    size: int,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(
            AuditLog.actor_email.ilike(like),
            AuditLog.action.ilike(like),
            AuditLog.target_type.ilike(like),
            AuditLog.target_id.ilike(like),
        ))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)

    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def export_audit_logs(
    session: Session,
    search: Optional[str],
    action: Optional[str],
    actor_id: Optional[int],
    target_type: Optional[str],
    target_id: Optional[str],
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(
            AuditLog.actor_email.ilike(like),
            AuditLog.action.ilike(like),
            AuditLog.target_type.ilike(like),
            AuditLog.target_id.ilike(like),
        ))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)

    return session.exec(stmt.order_by(AuditLog.created_at.desc())).all()


def to_public(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "actor_id": log.actor_id,
        "actor_email": log.actor_email,
        "actor_role": log.actor_role,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "before_json": log.before_json,
        "after_json": log.after_json,
        "ip_hash": log.ip_hash,
        "user_agent_hash": log.user_agent_hash,
        "request_id": log.request_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }