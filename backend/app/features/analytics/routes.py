"""Analytics routes."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.analytics import service

router = APIRouter(prefix="/admin/analytics", tags=["Admin - Analytics"])


class EventTrack(BaseModel):
    event_name: str
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    platform: str = "web"
    app_version: Optional[str] = None
    properties: Optional[dict] = None


class EventBatch(BaseModel):
    events: List[EventTrack]


class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    criteria_json: dict


class SegmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    criteria_json: Optional[dict] = None
    is_active: Optional[bool] = None


class SegmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    criteria_json: dict
    is_active: bool
    created_at: str
    updated_at: str


class FunnelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[str]
    window_hours: int = 24


class AnomalyResponse(BaseModel):
    id: int
    metric_name: str
    dimension: Optional[str]
    dimension_value: Optional[str]
    expected_value: float
    actual_value: float
    deviation_pct: float
    severity: str
    description: str
    status: str
    detected_at: str


class AnomalyStatusUpdate(BaseModel):
    status: str


# Event tracking
@router.post("/track")
def track_event(
    body: EventTrack,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    event = service.track_event(
        session,
        body.event_name,
        body.user_id,
        body.session_id,
        body.platform,
        body.app_version,
        body.properties,
    )
    return {"id": event.id, "event_name": event.event_name, "created_at": event.created_at.isoformat()}


@router.post("/track/batch")
def track_batch(
    body: EventBatch,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    events = [
        service.TrackEvent(
            event_name=e.event_name,
            user_id=e.user_id,
            session_id=e.session_id,
            platform=e.platform,
            app_version=e.app_version,
            properties=e.properties,
        )
        for e in body.events
    ]
    result = service.track_batch(session, events)
    return {"tracked": len(result)}


@router.get("/events")
def list_events(
    event_name: Optional[str] = None,
    user_id: Optional[int] = None,
    platform: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    since_dt = datetime.fromisoformat(since) if since else None
    until_dt = datetime.fromisoformat(until) if until else None
    events = service.get_events(session, event_name, user_id, platform, since_dt, until_dt, limit)
    return {"events": [
        {"id": e.id, "event_name": e.event_name, "user_id": e.user_id, "platform": e.platform,
         "app_version": e.app_version, "properties": e.properties_json, "created_at": e.created_at.isoformat()}
        for e in events
    ]}


# Aggregations
@router.post("/aggregate/daily")
def run_daily_aggregation(
    date: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    target_date = datetime.fromisoformat(date) if date else None
    return service.run_daily_aggregation(session, target_date)


@router.get("/overview")
def analytics_overview(
    days: int = 7,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    return service.get_overview(session, days)


@router.get("/feature-usage")
def feature_usage(
    days: int = 7,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    return service.get_feature_usage(session, days)


@router.get("/retention")
def retention(
    days: int = 7,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    return service.get_retention(session, days)


@router.get("/platforms")
def platform_versions(
    days: int = 7,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    return service.get_platform_versions(session, days)


# Segments
@router.get("/segments")
def list_segments(
    is_active: Optional[bool] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    segments = service.list_segments(session, is_active)
    return {"segments": [{"id": s.id, "name": s.name, "description": s.description,
                         "criteria_json": s.criteria_json, "is_active": s.is_active,
                         "created_at": s.created_at.isoformat(), "updated_at": s.updated_at.isoformat()} for s in segments]}


@router.post("/segments", status_code=201)
def create_segment(
    body: SegmentCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    segment = service.create_segment(session, body, admin.id)
    return {"id": segment.id, "name": segment.name, "criteria_json": segment.criteria_json,
            "is_active": segment.is_active, "created_at": segment.created_at.isoformat()}


@router.get("/segments/{segment_id}")
def get_segment(
    segment_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    segment = service.get_segment(session, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return {"id": segment.id, "name": segment.name, "description": segment.description,
            "criteria_json": segment.criteria_json, "is_active": segment.is_active,
            "created_at": segment.created_at.isoformat(), "updated_at": segment.updated_at.isoformat()}


@router.patch("/segments/{segment_id}")
def update_segment(
    segment_id: int,
    body: SegmentUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    segment = service.update_segment(session, segment_id, body)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return {"id": segment.id, "name": segment.name, "criteria_json": segment.criteria_json,
            "is_active": segment.is_active, "updated_at": segment.updated_at.isoformat()}


@router.delete("/segments/{segment_id}", status_code=204)
def delete_segment(
    segment_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    if not service.delete_segment(session, segment_id):
        raise HTTPException(status_code=404, detail="Segment not found")


@router.get("/segments/{segment_id}/users")
def segment_users(
    segment_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    user_ids = service.get_segment_users(session, segment_id)
    return {"segment_id": segment_id, "user_count": len(user_ids), "user_ids": user_ids[:100]}


# Funnels
@router.post("/funnels", status_code=201)
def create_funnel(
    body: FunnelCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    funnel = service.create_funnel(session, body, admin.id)
    return {"id": funnel.id, "name": funnel.name, "steps": funnel.steps_json,
            "window_hours": funnel.window_hours, "created_at": funnel.created_at.isoformat()}


@router.get("/funnels")
def list_funnels(
    is_active: Optional[bool] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    funnels = service.list_funnels(session, is_active)
    return {"funnels": [{"id": f.id, "name": f.name, "steps": f.steps_json,
                         "window_hours": f.window_hours, "is_active": f.is_active,
                         "created_at": f.created_at.isoformat()} for f in funnels]}


@router.get("/funnels/{funnel_id}/analyze")
def analyze_funnel(
    funnel_id: int,
    days: int = 7,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    return service.analyze_funnel(session, funnel_id, days)


# Anomalies
@router.get("/anomalies")
def list_anomalies(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    days: int = 7,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    anomalies = service.list_anomalies(session, status, severity, days)
    return {"anomalies": [
        {"id": a.id, "metric_name": a.metric_name, "dimension": a.dimension,
         "dimension_value": a.dimension_value, "expected_value": a.expected_value,
         "actual_value": a.actual_value, "deviation_pct": a.deviation_pct,
         "severity": a.severity, "description": a.description, "status": a.status,
         "detected_at": a.detected_at.isoformat()}
        for a in anomalies
    ]}


@router.patch("/anomalies/{anomaly_id}")
def update_anomaly(
    anomaly_id: int,
    body: AnomalyStatusUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    # Status comes in the JSON body (`{"status": ...}`), matching what the
    # admin UI sends. An earlier version took it as a query parameter, so every
    # status change from the UI failed validation with 422.
    anomaly = service.update_anomaly(session, anomaly_id, body.status, admin.id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return {"id": anomaly.id, "status": anomaly.status}


# Anomaly detection
@router.post("/anomalies/detect")
def detect_anomalies(
    date: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    target_date = datetime.fromisoformat(date) if date else None
    anomalies = service.detect_anomalies(session, target_date)
    return {"detected": len(anomalies), "anomalies": anomalies}


# User 360
@router.get("/users/{user_id}/360")
def user_360(
    user_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    return service.get_user_360(session, user_id)