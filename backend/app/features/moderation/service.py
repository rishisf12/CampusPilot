"""Moderation service."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import Session, select

from models import ModerationQueue, User


def list_moderation(
    session: Session,
    status: Optional[str] = None,
    content_type: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list, int]:
    stmt = select(ModerationQueue)
    if status:
        stmt = stmt.where(ModerationQueue.status == status)
    if content_type:
        stmt = stmt.where(ModerationQueue.content_type == content_type)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(ModerationQueue.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def get_moderation(session: Session, moderation_id: int):
    return session.get(ModerationQueue, moderation_id)


def review_moderation(
    session: Session,
    moderation_id: int,
    reviewer_id: int,
    action: str,  # approve, remove, warn
    reason: Optional[str] = None,
) -> Optional[object]:
    from models import ModerationQueue
    item = session.get(ModerationQueue, moderation_id)
    if not item:
        return None
    if item.status != "pending":
        return None

    item.status = "approved" if action == "approve" else ("removed" if action == "remove" else "warned")
    item.reviewer_id = reviewer_id
    item.reviewed_at = datetime.utcnow()
    item.action_taken = action
    item.action_reason = reason
    session.add(item)
    # TODO: notify original reporter and content owner
    session.commit()
    session.refresh(item)
    return item


def list_moderation(
    session: Session,
    status: Optional[str] = None,
    content_type: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list, int]:
    from sqlmodel import select
    from sqlalchemy import or_
    stmt = select(ModerationQueue)
    if status:
        stmt = stmt.where(ModerationQueue.status == status)
    if content_type:
        stmt = stmt.where(ModerationQueue.content_type == content_type)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(ModerationQueue.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def get_moderation(session: Session, moderation_id: int):
    return session.get(ModerationQueue, moderation_id)


def review_moderation(
    session: Session,
    moderation_id: int,
    reviewer_id: int,
    action: str,
    reason: Optional[str] = None,
) -> Optional[object]:
    item = session.get(ModerationQueue, moderation_id)
    if not item:
        return None
    if item.status != "pending":
        return None

    if action == "approve":
        item.status = "approved"
    elif action == "remove":
        item.status = "removed"
    elif action == "warn":
        item.status = "warned"
    else:
        return None

    item.reviewer_id = reviewer_id
    item.reviewed_at = datetime.utcnow()
    item.action_taken = action
    item.action_reason = reason
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def to_public(item) -> dict:
    return {
        "id": item.id,
        "content_type": item.content_type,
        "content_id": item.content_id,
        "reporter_id": item.reporter_id,
        "reason": item.reason,
        "details": item.details,
        "status": item.status,
        "reviewer_id": item.reviewer_id,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "action_taken": item.action_taken,
        "action_reason": item.action_reason,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }