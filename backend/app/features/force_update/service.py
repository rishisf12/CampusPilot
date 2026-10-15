"""Force/Soft update service."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import select

from models import ForceUpdateRule


def get_rule_for_client(session, platform: str, current_version: str) -> Optional[dict]:
    """Check if update is required for a client."""
    rule = session.exec(
        select(ForceUpdateRule).where(
            ForceUpdateRule.platform == platform,
            ForceUpdateRule.is_active,
        )
    ).first()

    if not rule:
        return None

    from packaging import version
    current = version.parse(current_version)
    min_ver = version.parse(rule.min_version)
    recommended = version.parse(rule.recommended_version)

    if current < min_ver:
        return {
            "required": True,
            "type": "force",
            "min_version": rule.min_version,
            "recommended_version": rule.recommended_version,
            "store_url": rule.store_url,
            "message": rule.message or "A mandatory update is required.",
        }
    if current < recommended:
        return {
            "required": False,
            "type": "soft",
            "min_version": rule.min_version,
            "recommended_version": rule.recommended_version,
            "store_url": rule.store_url,
            "message": rule.message or "An update is available.",
        }
    return None


def list_rules(session, page: int = 1, size: int = 20) -> tuple[list, int]:
    stmt = select(ForceUpdateRule).order_by(ForceUpdateRule.platform)
    total = len(session.exec(stmt).all())
    rows = session.exec(stmt.offset((page - 1) * size).limit(size)).all()
    return rows, total


def create_rule(session, platform: str, min_version: str, recommended_version: str, store_url: str,
                message: Optional[str] = None, is_active: bool = True, created_by: Optional[int] = None):
    rule = ForceUpdateRule(
        platform=platform,
        min_version=min_version,
        recommended_version=recommended_version,
        store_url=store_url,
        message=message,
        is_active=is_active,
        created_by=created_by,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def get_rule(session, platform: str) -> Optional[object]:
    return session.exec(select(ForceUpdateRule).where(ForceUpdateRule.platform == platform)).first()


def update_rule(session, rule_id: int, data: dict) -> Optional[object]:
    rule = session.get(ForceUpdateRule, rule_id)
    if not rule:
        return None
    update_data = data.get("rule") if "rule" in data else data
    for field, value in update_data.items():
        if hasattr(rule, field) and value is not None:
            setattr(rule, field, value)
    rule.updated_at = datetime.utcnow()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_rule(session, rule_id: int) -> bool:
    rule = session.get(ForceUpdateRule, rule_id)
    if not rule:
        return False
    session.delete(rule)
    session.commit()
    return True


def to_public(rule) -> dict:
    return {
        "id": rule.id,
        "platform": rule.platform,
        "min_version": rule.min_version,
        "recommended_version": rule.recommended_version,
        "store_url": rule.store_url,
        "message": rule.message,
        "is_active": rule.is_active,
        "created_by": rule.created_by,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }