"""User control service: suspend, ban, force logout, revoke tokens, etc."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timedelta
from sqlmodel import Session, select

from models import User, UserControlAction, UserRole, PasskeyCredential


def suspend_user(
    session: Session,
    admin_id: int,
    target_user_id: int,
    reason: Optional[str] = None,
    duration_days: Optional[int] = None,
) -> Optional[UserControlAction]:
    """Suspend a user (prevent login)."""
    target = session.get(User, target_user_id)
    if not target:
        return None
    if target.id == admin_id:
        raise ValueError("Cannot suspend yourself")

    expires_at = datetime.utcnow() + timedelta(days=duration_days) if duration_days else None
    action = UserControlAction(
        admin_id=admin_id,
        target_user_id=target_user_id,
        action="suspend",
        reason=reason,
        expires_at=expires_at,
    )
    session.add(action)
    target.is_suspended = True
    target.suspended_until = expires_at
    session.add(target)
    session.commit()
    session.refresh(action)
    return action


def ban_user(
    session: Session,
    admin_id: int,
    target_user_id: int,
    reason: Optional[str] = None,
) -> Optional[UserControlAction]:
    """Permanently ban a user."""
    target = session.get(User, target_user_id)
    if not target:
        return None
    if target.id == admin_id:
        raise ValueError("Cannot ban yourself")

    action = UserControlAction(
        admin_id=admin_id,
        target_user_id=target_user_id,
        action="ban",
        reason=reason,
    )
    session.add(action)
    target.is_banned = True
    session.add(target)
    session.commit()
    session.refresh(action)
    return action


def force_logout_user(
    session: Session,
    admin_id: int,
    target_user_id: int,
    reason: Optional[str] = None,
) -> Optional[UserControlAction]:
    """Force logout by revoking all sessions/tokens."""
    target = session.get(User, target_user_id)
    if not target:
        return None
    if target.id == admin_id:
        raise ValueError("Cannot force logout yourself")

    action = UserControlAction(
        admin_id=admin_id,
        target_user_id=target_user_id,
        action="force_logout",
        reason=reason,
    )
    session.add(action)
    target.password_changed_at = datetime.utcnow()
    session.add(target)
    session.commit()
    session.refresh(action)
    return action


def revoke_tokens(
    session: Session,
    admin_id: int,
    target_user_id: int,
    reason: Optional[str] = None,
) -> Optional[UserControlAction]:
    """Revoke all passkeys/tokens for a user."""
    target = session.get(User, target_user_id)
    if not target:
        return None
    if target.id == admin_id:
        raise ValueError("Cannot revoke your own tokens")

    # Delete passkeys
    for pk in session.exec(select(PasskeyCredential).where(PasskeyCredential.user_id == target_user_id)).all():
        session.delete(pk)

    action = UserControlAction(
        admin_id=admin_id,
        target_user_id=target_user_id,
        action="revoke_tokens",
        reason=reason,
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


def reset_verification(
    session: Session,
    admin_id: int,
    target_user_id: int,
    reason: Optional[str] = None,
) -> Optional[UserControlAction]:
    """Reset email verification status."""
    target = session.get(User, target_user_id)
    if not target:
        return None
    if target.id == admin_id:
        raise ValueError("Cannot reset your own verification")

    action = UserControlAction(
        admin_id=admin_id,
        target_user_id=target_user_id,
        action="reset_verification",
        reason=reason,
    )
    session.add(action)
    target.is_email_verified = False
    session.add(target)
    session.commit()
    session.refresh(action)
    return action


def start_impersonation(
    session: Session,
    admin_id: int,
    target_user_id: int,
    reason: Optional[str] = None,
) -> Optional[UserControlAction]:
    """Start impersonation session (read-only view as target user)."""
    admin = session.get(User, admin_id)
    target = session.get(User, target_user_id)
    if not admin or not target:
        return None
    if admin.role != UserRole.ADMIN:
        raise ValueError("Only admins can impersonate")

    action = UserControlAction(
        admin_id=admin_id,
        target_user_id=target_user_id,
        action="impersonate_start",
        reason=reason,
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


def end_impersonation(
    session: Session,
    admin_id: int,
    target_user_id: int,
) -> Optional[UserControlAction]:
    """End impersonation session."""
    action = session.exec(
        select(UserControlAction).where(
            UserControlAction.admin_id == admin_id,
            UserControlAction.target_user_id == target_user_id,
            UserControlAction.action == "impersonate_start",
        ).order_by(UserControlAction.id.desc())
    ).first()
    if action:
        action.action = "impersonate_end"
        session.add(action)
        session.commit()
        session.refresh(action)
    return action


def bulk_action(
    session: Session,
    admin_id: int,
    user_ids: List[int],
    action_type: str,
    reason: Optional[str] = None,
    duration_days: Optional[int] = None,
) -> List[UserControlAction]:
    """Perform bulk action on multiple users."""
    actions = []
    for uid in user_ids:
        if uid == admin_id:
            continue
        if action_type == "suspend":
            act = suspend_user(session, admin_id, uid, reason, duration_days=duration_days)
        elif action_type == "ban":
            act = ban_user(session, admin_id, uid, reason)
        elif action_type == "force_logout":
            act = force_logout_user(session, admin_id, uid, reason)
        elif action_type == "revoke_tokens":
            act = revoke_tokens(session, admin_id, uid, reason)
        elif action_type == "reset_verification":
            act = reset_verification(session, admin_id, uid, reason)
        else:
            continue
        if act:
            actions.append(act)
    return actions


def list_user_actions(
    session: Session,
    target_user_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    action: Optional[str] = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[UserControlAction], int]:
    stmt = select(UserControlAction)
    if target_user_id:
        stmt = stmt.where(UserControlAction.target_user_id == target_user_id)
    if admin_id:
        stmt = stmt.where(UserControlAction.admin_id == admin_id)
    if action:
        stmt = stmt.where(UserControlAction.action == action)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(UserControlAction.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def to_public(action: UserControlAction) -> dict:
    return {
        "id": action.id,
        "admin_id": action.admin_id,
        "target_user_id": action.target_user_id,
        "action": action.action,
        "reason": action.reason,
        "expires_at": action.expires_at.isoformat() if action.expires_at else None,
        "created_at": action.created_at.isoformat() if action.created_at else None,
    }