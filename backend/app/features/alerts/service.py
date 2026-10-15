"""Alert rules service."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import or_

from features.alerts.models import AlertChannel, AlertRule, AlertIncident


# Channels
def list_channels(session: Session) -> List[AlertChannel]:
    return session.exec(select(AlertChannel).order_by(AlertChannel.created_at.desc())).all()


def create_channel(session: Session, name: str, channel_type: str, config_json: dict, enabled: bool) -> AlertChannel:
    channel = AlertChannel(
        name=name,
        channel_type=channel_type,
        config_json=config_json,
        enabled=enabled,
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


def delete_channel(session: Session, channel_id: int) -> bool:
    channel = session.get(AlertChannel, channel_id)
    if not channel:
        return False
    session.delete(channel)
    session.commit()
    return True


# Rules
def list_rules(session: Session, enabled: Optional[bool] = None) -> List[AlertRule]:
    stmt = select(AlertRule)
    if enabled is not None:
        stmt = stmt.where(AlertRule.enabled == enabled)
    return session.exec(stmt.order_by(AlertRule.created_at.desc())).all()


def get_rule(session: Session, rule_id: int) -> Optional[AlertRule]:
    return session.get(AlertRule, rule_id)


def create_rule(session: Session, body, created_by: int) -> AlertRule:
    rule = AlertRule(
        name=body.name,
        description=body.description,
        metric=body.metric,
        condition=body.condition,
        threshold=body.threshold,
        window_minutes=body.window_minutes,
        severity=body.severity,
        channels=body.channels,
        cooldown_minutes=body.cooldown_minutes,
        enabled=body.enabled,
        created_by=created_by,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def update_rule(session: Session, rule_id: int, body) -> Optional[AlertRule]:
    rule = session.get(AlertRule, rule_id)
    if not rule:
        return None
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    rule.updated_at = __import__('datetime').datetime.utcnow()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: int) -> bool:
    rule = session.get(AlertRule, rule_id)
    if not rule:
        return False
    session.delete(rule)
    session.commit()
    return True


# Incidents
def list_incidents(
    session: Session,
    status: Optional[str] = None,
    rule_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
) -> tuple[List, int]:
    stmt = select(AlertIncident)
    if status:
        stmt = stmt.where(AlertIncident.status == status)
    if rule_id:
        stmt = stmt.where(AlertIncident.rule_id == rule_id)
    total = len(session.exec(stmt).all())
    rows = session.exec(stmt.order_by(AlertIncident.started_at.desc()).offset((page - 1) * size).limit(size)).all()
    return rows, total


def update_incident(session: Session, incident_id: int, status: str, user_id: int) -> Optional[AlertIncident]:
    incident = session.get(AlertIncident, incident_id)
    if not incident:
        return None
    if status == "acknowledged" and incident.status == "firing":
        incident.status = "acknowledged"
        incident.acknowledged_at = datetime.utcnow()
        incident.acknowledged_by = user_id
    elif status == "resolved" and incident.status in ("firing", "acknowledged"):
        incident.status = "resolved"
        incident.resolved_at = datetime.utcnow()
        incident.resolved_by = user_id
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident