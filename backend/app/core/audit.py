"""Audit logging utilities."""
from __future__ import annotations
import hashlib
import json
from typing import Any, Optional
from datetime import datetime
from sqlalchemy import text
from sqlmodel import Session

from models import User


def hash_ip(ip: Optional[str]) -> Optional[str]:
    """Hash IP address with salt for privacy."""
    if not ip:
        return None
    salt = "campuspilot_audit_salt_v1"
    return hashlib.sha256(f"{salt}{ip}".encode()).hexdigest()[:64]


def hash_user_agent(ua: Optional[str]) -> Optional[str]:
    """Hash user agent for privacy."""
    if not ua:
        return None
    salt = "campuspilot_ua_salt_v1"
    return hashlib.sha256(f"{salt}{ua}".encode()).hexdigest()[:64]


def log_audit(
    session: Session,
    *,
    actor: Optional[User],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Write an audit log entry. Call this after successful mutations.

    Args:
        session: Database session (will be committed by caller).
        actor: User performing the action (None for system actions).
        action: Short action name (e.g. "user.role.change", "flag.toggle").
        target_type: Type of target (e.g. "user", "feature_flag").
        target_id: ID of target as string.
        before: State before change.
        after: State after change.
        ip: Client IP address (will be hashed).
        user_agent: Client User-Agent (will be hashed).
        request_id: Request correlation ID.
    """
    ip_hash = hash_ip(ip)
    ua_hash = hash_user_agent(user_agent)

    session.execute(
        text("""
            INSERT INTO core.audit_log
            (actor_id, actor_email, actor_role, action, target_type, target_id,
             before_json, after_json, ip_hash, user_agent_hash, request_id, created_at)
            VALUES (:actor_id, :actor_email, :actor_role, :action, :target_type, :target_id,
                    :before_json, :after_json, :ip_hash, :ua_hash, :request_id, :created_at)
        """),  # noqa: E501
        {
            "actor_id": actor.id if actor else None,
            "actor_email": actor.email if actor else None,
            "actor_role": actor.role.value if actor and hasattr(actor.role, 'value') else (actor.role if actor else None),
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "before_json": json.dumps(before) if before is not None else None,
            "after_json": json.dumps(after) if after is not None else None,
            "ip_hash": ip_hash,
            "ua_hash": ua_hash,
            "request_id": request_id,
            "created_at": datetime.utcnow(),
        }
    )
    # Committed here rather than left to the caller.
    #
    # Every admin service function commits its own transaction before returning,
    # so by the time a route calls this the session has already been committed
    # and nothing will commit the audit row afterwards - `get_session` only
    # closes. Without this the INSERT is silently rolled back on close and the
    # audit log stays permanently empty, which looks exactly like "no actions
    # were ever taken".
    session.commit()