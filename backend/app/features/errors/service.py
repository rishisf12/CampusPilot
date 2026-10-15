"""Error tracking service."""
from __future__ import annotations
from typing import Optional, List
from sqlmodel import Session, select
from sqlalchemy import or_, desc

from features.errors.models import ErrorFingerprint, ErrorEvent


def list_fingerprints(
    session: Session,
    search: Optional[str],
    status: Optional[str],
    platform: Optional[str],
    page: int,
    size: int,
) -> tuple[list[ErrorFingerprint], int]:
    stmt = select(ErrorFingerprint)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(
            ErrorFingerprint.error_type.ilike(like),
            ErrorFingerprint.message.ilike(like),
            ErrorFingerprint.fingerprint.ilike(like),
        ))
    if status:
        stmt = stmt.where(ErrorFingerprint.status == status)
    if platform:
        stmt = stmt.where(ErrorFingerprint.platform == platform)

    total = len(session.exec(stmt).all())
    rows = session.exec(stmt.order_by(desc(ErrorFingerprint.last_seen)).offset((page - 1) * size).limit(size)).all()
    return rows, total


def get_fingerprint(session: Session, fingerprint_id: int) -> Optional[ErrorFingerprint]:
    return session.get(ErrorFingerprint, fingerprint_id)


def update_fingerprint(session: Session, fingerprint_id: int, status: str, assignee_id: Optional[int]) -> Optional[ErrorFingerprint]:
    fp = session.get(ErrorFingerprint, fingerprint_id)
    if not fp:
        return None
    if status:
        fp.status = status
    if assignee_id is not None:
        fp.assignee_id = assignee_id
    session.add(fp)
    session.commit()
    session.refresh(fp)
    return fp


def list_events(
    session: Session,
    fingerprint_id: int,
    page: int,
    size: int,
) -> tuple[list[ErrorEvent], int]:
    stmt = select(ErrorEvent).where(ErrorEvent.fingerprint_id == fingerprint_id)
    total = len(session.exec(stmt).all())
    rows = session.exec(stmt.order_by(desc(ErrorEvent.created_at)).offset((page - 1) * size).limit(size)).all()
    return rows, total


def fingerprint_to_public(fp: ErrorFingerprint) -> dict:
    return {
        "id": fp.id,
        "fingerprint": fp.fingerprint,
        "error_type": fp.error_type,
        "message": fp.message,
        "first_seen": fp.first_seen.isoformat() if fp.first_seen else None,
        "last_seen": fp.last_seen.isoformat() if fp.last_seen else None,
        "count": fp.count,
        "status": fp.status,
        "assignee_id": fp.assignee_id,
        "affected_users": fp.affected_users,
    }


def ingest_error(session: Session, data: dict) -> ErrorFingerprint:
    """Ingest error from client, group by fingerprint."""
    import hashlib
    import json

    # Create fingerprint from error type + message + stack trace hash
    error_type = data.get("error_type", "Error")
    message = data.get("message", "")[:500]
    stack_trace = data.get("stack_trace", "")

    # Create fingerprint hash
    fingerprint_input = f"{error_type}:{message}:{stack_trace[:1000]}"
    fingerprint_hash = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:64]

    # Look for existing fingerprint
    fp = session.exec(
        select(ErrorFingerprint).where(ErrorFingerprint.fingerprint == fingerprint_hash)
    ).first()

    if fp:
        # Update existing
        fp.count += 1
        fp.last_seen = __import__('datetime').datetime.utcnow()
        if data.get("platform"):
            platforms = fp.affected_releases if isinstance(fp.affected_releases, list) else []
            if data.get("platform") not in platforms:
                platforms.append(data.get("platform"))
                fp.affected_releases = platforms
        session.add(fp)
        session.commit()
        session.refresh(fp)
    else:
        # Create new
        stack_trace_hash = hashlib.sha256(data.get("stack_trace", "").encode()).hexdigest()[:64]
        fp = ErrorFingerprint(
            fingerprint=fingerprint_hash,
            error_type=data.get("error_type", "Error"),
            message=data.get("message", "")[:500],
            stack_trace_hash=stack_trace_hash,
            platform=data.get("platform", "web"),
            affected_releases=[data.get("app_version")] if data.get("app_version") else [],
        )
        session.add(fp)
        session.commit()
        session.refresh(fp)

    # Create event
    event = ErrorEvent(
        fingerprint_id=fp.id,
        request_id=data.get("request_id"),
        user_id=data.get("user_id"),
        platform=data.get("platform", "web"),
        app_version=data.get("app_version"),
        url=data.get("url"),
        user_agent=data.get("user_agent"),
        stack_trace=data.get("stack_trace"),
        context_json=data.get("context"),
    )
    session.add(event)
    session.commit()

    return fp