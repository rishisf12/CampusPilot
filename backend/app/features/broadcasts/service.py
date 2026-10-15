"""Broadcast service."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import or_, and_

from models import Broadcast, BroadcastDelivery, User
from core.database import engine


def list_broadcasts(
    session: Session,
    page: int = 1,
    size: int = 20,
) -> tuple[list, int]:
    stmt = select(Broadcast)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(Broadcast.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def create_broadcast(
    session: Session,
    title: str,
    body: str,
    channel: str,
    target_roles: Optional[list] = None,
    target_user_ids: Optional[list] = None,
    target_branches: Optional[list] = None,
    target_semesters: Optional[list] = None,
    target_segments: Optional[list] = None,
    scheduled_at: Optional[datetime] = None,
    created_by: int = None,
) -> object:
    broadcast = Broadcast(
        title=title,
        body=body,
        channel=channel,
        target_roles=target_roles,
        target_user_ids=target_user_ids,
        target_branches=target_branches,
        target_semesters=target_semesters,
        target_segments=target_segments,
        scheduled_at=scheduled_at,
        created_by=created_by,
    )
    session.add(broadcast)
    session.commit()
    session.refresh(broadcast)
    return broadcast


def get_broadcast(session: Session, broadcast_id: int):
    return session.get(Broadcast, broadcast_id)


def update_broadcast(session: Session, broadcast_id: int, data: dict) -> Optional[object]:
    broadcast = session.get(Broadcast, broadcast_id)
    if not broadcast:
        return None
    for field, value in data.items():
        if hasattr(broadcast, field) and value is not None:
            setattr(broadcast, field, value)
    broadcast.updated_at = datetime.utcnow()
    session.add(broadcast)
    session.commit()
    session.refresh(broadcast)
    return broadcast


def delete_broadcast(session: Session, broadcast_id: int) -> bool:
    broadcast = session.get(Broadcast, broadcast_id)
    if not broadcast:
        return False
    session.delete(broadcast)
    session.commit()
    return True


def send_broadcast(session: Session, broadcast_id: int) -> dict:
    """Send a broadcast immediately."""
    broadcast = session.get(Broadcast, broadcast_id)
    if not broadcast:
        raise ValueError("Broadcast not found")

    # Determine target users
    user_ids = set()
    if broadcast.target_user_ids:
        user_ids.update(broadcast.target_user_ids)
    if broadcast.target_roles:
        from models import User, UserRole
        for role in broadcast.target_roles:
            role_users = session.exec(
                select(User.id).where(User.role == role)
            ).all()
            user_ids.update(role_users)
    if broadcast.target_branches:
        from models import UserProfile
        branch_users = session.exec(
            select(User.id).join(UserProfile, User.id == UserProfile.user_id)
            .where(UserProfile.branch.in_(broadcast.target_branches))
        ).all()
        user_ids.update(branch_users)
    if broadcast.target_semesters:
        from models import UserProfile
        sem_users = session.exec(
            select(User.id).join(UserProfile, User.id == UserProfile.user_id)
            .where(UserProfile.semester.in_(broadcast.target_semesters))
        ).all()
        user_ids.update(sem_users)

    # Create delivery records
    for uid in user_ids:
        delivery = BroadcastDelivery(
            broadcast_id=broadcast.id,
            user_id=uid,
            channel=broadcast.channel,
            status="pending",
        )
        session.add(delivery)
    session.commit()

    # TODO: Actually send via FCM/APNs/WebPush here
    # For now, mark as sent
    for delivery in session.exec(
        select(BroadcastDelivery).where(BroadcastDelivery.broadcast_id == broadcast.id)
    ).all():
        delivery.status = "sent"
        delivery.sent_at = datetime.utcnow()
        session.add(delivery)
    session.commit()

    broadcast.sent_at = datetime.utcnow()
    session.add(broadcast)
    session.commit()

    return {"sent_to": len(user_ids), "broadcast_id": broadcast.id}


def list_deliveries(
    session,
    broadcast_id: int,
    page: int = 1,
    size: int = 50,
) -> tuple[list, int]:
    stmt = select(BroadcastDelivery).where(BroadcastDelivery.broadcast_id == broadcast_id)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(BroadcastDelivery.sent_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def to_public(broadcast: Broadcast) -> dict:
    return {
        "id": broadcast.id,
        "title": broadcast.title,
        "body": broadcast.body,
        "channel": broadcast.channel,
        "target_roles": broadcast.target_roles if isinstance(broadcast.target_roles, list) else [],
        "target_user_ids": broadcast.target_user_ids if isinstance(broadcast.target_user_ids, list) else [],
        "target_branches": broadcast.target_branches if isinstance(broadcast.target_branches, list) else [],
        "target_semesters": broadcast.target_semesters if isinstance(broadcast.target_semesters, list) else [],
        "target_segments": broadcast.target_segments if isinstance(broadcast.target_segments, list) else [],
        "scheduled_at": broadcast.scheduled_at.isoformat() if broadcast.scheduled_at else None,
        "sent_at": broadcast.sent_at.isoformat() if broadcast.sent_at else None,
        "created_at": broadcast.created_at.isoformat() if broadcast.created_at else None,
        "created_by": broadcast.created_by,
    }


def delivery_to_public(delivery: BroadcastDelivery) -> dict:
    return {
        "id": delivery.id,
        "broadcast_id": delivery.broadcast_id,
        "user_id": delivery.user_id,
        "channel": delivery.channel,
        "status": delivery.status,
        "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
        "read_at": delivery.read_at.isoformat() if delivery.read_at else None,
        "error_message": delivery.error_message,
    }