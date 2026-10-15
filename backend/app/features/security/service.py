"""Security events service."""
from __future__ import annotations
from typing import Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select
from sqlalchemy import desc, func

from models import SecurityEvent, SecurityFeed
from core.config import settings


def log_security_event(
    session: Session,
    event_type: str,
    severity: str,
    actor_email: Optional[str] = None,
    actor_id: Optional[int] = None,
    details: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> object:
    """Log a security event and update aggregated feed."""
    import hashlib
    ip_hash = hashlib.sha256(f"{settings.telemetry_pepper}{ip}".encode()).hexdigest()[:64] if ip else None
    ua_hash = hashlib.sha256(f"{settings.telemetry_pepper}{user_agent}".encode()).hexdigest()[:64] if user_agent else None

    event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        actor_email=actor_email,
        actor_id=actor_id,
        details=details,
        ip_hash=ip_hash,
        user_agent_hash=ua_hash,
        request_id=request_id,
    )
    session.add(event)

    # Update aggregated feed
    feed = session.exec(
        select(SecurityFeed).where(SecurityFeed.event_type == event_type, SecurityFeed.severity == severity)
    ).first()

    now = datetime.utcnow()
    if feed:
        feed.count += 1
        feed.last_seen = now
        feed.updated_at = datetime.utcnow()
    else:
        feed = SecurityFeed(
            event_type=event_type,
            severity=severity,
            count=1,
            first_seen=datetime.utcnow(),
            last_seen=now,
            description=f"{event_type} ({severity})",
        )
        session.add(feed)

    session.commit()
    return SecurityEvent(
        id=0,
        event_type=event_type,
        severity=severity,
        actor_email=actor_email,
        actor_id=actor_id,
        details=details,
        ip_hash=ip_hash,
        user_agent_hash=ua_hash,
        request_id=request_id,
        created_at=datetime.utcnow(),
    )


def get_security_feed(
    session: Session,
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    days: int = 7,
    page: int = 1,
    size: int = 50,
) -> tuple[list, int]:
    since = datetime.utcnow() - timedelta(days=days)
    stmt = select(SecurityFeed).where(SecurityFeed.first_seen >= since)
    if severity:
        stmt = stmt.where(SecurityFeed.severity == severity)
    if event_type:
        stmt = stmt.where(SecurityFeed.event_type == event_type)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(SecurityFeed.last_seen.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def get_recent_events(
    session: Session,
    hours: int = 24,
    limit: int = 100,
) -> list:
    since = datetime.utcnow() - timedelta(hours=hours)
    stmt = select(SecurityEvent).where(SecurityEvent.created_at >= since).order_by(desc(SecurityEvent.created_at)).limit(limit)
    events = session.exec(stmt).all()
    return [
        {
            "event_type": e.event_type,
            "severity": e.severity,
            "actor_email": e.actor_email,
            "actor_id": e.actor_id,
            "details": e.details,
            "ip_hash": e.ip_hash,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


def detect_anomalies(session: Session, hours: int = 24) -> list:
    """Detect security anomalies in recent events."""
    # NOTE: `hours` is currently unused - both checks below use a fixed
    # 1-hour window. Kept in the signature for API compatibility.

    # Failed login spikes
    failed_logins = session.exec(
        select(SecurityEvent)
        .where(SecurityEvent.event_type == "failed_login")
        .where(SecurityEvent.created_at >= datetime.utcnow() - timedelta(hours=1))
    ).all()
    if len(failed_logins) > 50:
        log_security_event(
            session,
            "failed_login_spike",
            "high",
            details=f"Failed login spike: {len(failed_logins)} in last hour",
        )

    # Brute force by IP
    ip_counts = session.exec(
        select(SecurityEvent.ip_hash, func.count(SecurityEvent.id))
        .where(SecurityEvent.event_type == "failed_login")
        .where(SecurityEvent.created_at >= datetime.utcnow() - timedelta(hours=1))
        .group_by(SecurityEvent.ip_hash)
        .having(func.count(SecurityEvent.id) > 10)
    ).all()
    for ip_hash, count in ip_counts:
        log_security_event(
            session,
            "brute_force",
            "high",
            details=f"Potential brute force from IP hash {ip_hash[:16]}: {count} attempts",
        )

    # New admin creation
    new_admins = session.exec(
        select(SecurityEvent)
        .where(SecurityEvent.event_type == "new_admin")
        .where(SecurityEvent.created_at >= datetime.utcnow() - timedelta(hours=24))
    ).all()
    for admin in new_admins:
        log_security_event(
            session,
            "new_admin",
            "medium",
            actor_email=admin.actor_email,
            actor_id=admin.actor_id,
            details=f"New admin created: {admin.actor_email}",
        )

    return []