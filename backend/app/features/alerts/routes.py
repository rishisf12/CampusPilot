"""Alert rules routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.alerts import service

router = APIRouter(prefix="/admin/alerts", tags=["Admin - Alerts"])


class AlertChannelCreate(BaseModel):
    name: str
    channel_type: str
    config_json: dict
    enabled: bool = True


class AlertChannelResponse(BaseModel):
    id: int
    name: str
    channel_type: str
    config_json: dict
    enabled: bool
    created_at: str


class AlertRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    metric: str
    condition: str
    threshold: float
    window_minutes: int = 5
    severity: str = "warning"
    channels: list[int] = []
    cooldown_minutes: int = 15
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    metric: Optional[str] = None
    condition: Optional[str] = None
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    severity: Optional[str] = None
    channels: Optional[list[int]] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None


class AlertRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    metric: str
    condition: str
    threshold: float
    window_minutes: int
    severity: str
    channels: list[int]
    cooldown_minutes: int
    enabled: bool
    created_at: str
    updated_at: str


class AlertIncidentResponse(BaseModel):
    id: int
    rule_id: int
    status: str
    value: float
    threshold: float
    started_at: str
    acknowledged_at: Optional[str]
    acknowledged_by: Optional[int]
    resolved_at: Optional[str]


class AlertIncidentUpdate(BaseModel):
    status: str  # acknowledged, resolved
    acknowledged_by: Optional[int] = None


# Channels
@router.get("/channels")
def admin_list_channels(
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    channels = service.list_channels(session)
    return {"channels": [{"id": c.id, "name": c.name, "channel_type": c.channel_type, "config_json": c.config_json, "enabled": c.enabled, "created_at": c.created_at.isoformat() if c.created_at else None} for c in channels]}


@router.post("/channels", status_code=201)
def admin_create_channel(
    body: AlertChannelCreate,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    channel = service.create_channel(session, body.name, body.channel_type, body.config_json, body.enabled)
    return {"id": channel.id, "name": channel.name, "channel_type": channel.channel_type, "config_json": channel.config_json, "enabled": channel.enabled, "created_at": channel.created_at.isoformat() if channel.created_at else None}


@router.delete("/channels/{channel_id}", status_code=204)
def admin_delete_channel(
    channel_id: int,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    if not service.delete_channel(session, channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")


# Rules
@router.get("/rules")
def admin_list_rules(
    enabled: Optional[bool] = None,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    rules = service.list_rules(session, enabled)
    return {"rules": [{"id": r.id, "name": r.name, "description": r.description, "metric": r.metric, "condition": r.condition, "threshold": r.threshold, "window_minutes": r.window_minutes, "severity": r.severity, "channels": r.channels, "cooldown_minutes": r.cooldown_minutes, "enabled": r.enabled, "created_at": r.created_at.isoformat() if r.created_at else None, "updated_at": r.updated_at.isoformat() if r.updated_at else None} for r in rules]}


@router.post("/rules", status_code=201)
def admin_create_rule(
    body: AlertRuleCreate,
    session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    rule = service.create_rule(session, body, admin.id)
    return {"id": rule.id, "name": rule.name, "description": rule.description, "metric": rule.metric, "condition": rule.condition, "threshold": rule.threshold, "window_minutes": rule.window_minutes, "severity": rule.severity, "channels": rule.channels, "cooldown_minutes": rule.cooldown_minutes, "enabled": rule.enabled, "created_at": rule.created_at.isoformat() if rule.created_at else None, "updated_at": rule.updated_at.isoformat() if rule.updated_at else None}


@router.get("/rules/{rule_id}")
def admin_get_rule(
    rule_id: int,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    rule = service.get_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"id": rule.id, "name": rule.name, "description": rule.description, "metric": rule.metric, "condition": rule.condition, "threshold": rule.threshold, "window_minutes": rule.window_minutes, "severity": rule.severity, "channels": rule.channels, "cooldown_minutes": rule.cooldown_minutes, "enabled": rule.enabled, "created_at": rule.created_at.isoformat() if rule.created_at else None, "updated_at": rule.updated_at.isoformat() if rule.updated_at else None}


@router.patch("/rules/{rule_id}")
def admin_update_rule(
    rule_id: int,
    body: AlertRuleUpdate,
    session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    rule = service.update_rule(session, rule_id, body)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"id": rule.id, "name": rule.name, "description": rule.description, "metric": rule.metric, "condition": rule.condition, "threshold": rule.threshold, "window_minutes": rule.window_minutes, "severity": rule.severity, "channels": rule.channels, "cooldown_minutes": rule.cooldown_minutes, "enabled": rule.enabled, "created_at": rule.created_at.isoformat() if rule.created_at else None, "updated_at": rule.updated_at.isoformat() if rule.updated_at else None}


@router.delete("/rules/{rule_id}", status_code=204)
def admin_delete_rule(
    rule_id: int,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    if not service.delete_rule(session, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")


@router.get("/incidents")
def admin_list_incidents(
    status: Optional[str] = None,
    rule_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    incidents, total = service.list_incidents(session, status, rule_id, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "incidents": [{"id": i.id, "rule_id": i.rule_id, "status": i.status, "value": i.value, "threshold": i.threshold, "started_at": i.started_at.isoformat() if i.started_at else None, "acknowledged_at": i.acknowledged_at.isoformat() if i.acknowledged_at else None, "acknowledged_by": i.acknowledged_by, "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None} for i in incidents],
    }


@router.patch("/incidents/{incident_id}")
def admin_update_incident(
    incident_id: int,
    body: AlertIncidentUpdate,
    session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    incident = service.update_incident(session, incident_id, body.status, admin.id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"id": incident.id, "status": incident.status, "acknowledged_at": incident.acknowledged_at.isoformat() if incident.acknowledged_at else None, "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None}