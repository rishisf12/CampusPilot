"""Maintenance mode service."""
from __future__ import annotations
from typing import Optional
from sqlmodel import Session, select

from features.maintenance.models import MaintenanceWindow


def list_maintenance_windows(
    session: Session,
    page: int,
    size: int,
) -> tuple[list[MaintenanceWindow], int]:
    stmt = select(MaintenanceWindow)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(MaintenanceWindow.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def create_maintenance_window(session: Session, body, created_by: int) -> MaintenanceWindow:
    window = MaintenanceWindow(
        name=body.name,
        description=body.description,
        global_maintenance=body.global_maintenance,
        target_features=body.target_features,
        message=body.message,
        allow_list_user_ids=body.allow_list_user_ids,
        bypass_roles=body.bypass_roles,
        scheduled_start=__import__('datetime').datetime.fromisoformat(body.scheduled_start) if body.scheduled_start else None,
        scheduled_end=__import__('datetime').datetime.fromisoformat(body.scheduled_end) if body.scheduled_end else None,
        created_by=created_by,
    )
    session.add(window)
    session.commit()
    session.refresh(window)
    return window


def get_maintenance_window(session: Session, window_id: int) -> Optional[MaintenanceWindow]:
    return session.get(MaintenanceWindow, window_id)


def update_maintenance_window(session: Session, window_id: int, body, updated_by: int) -> Optional[MaintenanceWindow]:
    window = session.get(MaintenanceWindow, window_id)
    if not window:
        return None

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in ("scheduled_start", "scheduled_end") and value:
            value = __import__('datetime').datetime.fromisoformat(value)
        setattr(window, field, value)

    window.updated_at = __import__('datetime').datetime.utcnow()
    session.add(window)
    session.commit()
    session.refresh(window)
    return window


def delete_maintenance_window(session: Session, window_id: int) -> bool:
    window = session.get(MaintenanceWindow, window_id)
    if not window:
        return False
    session.delete(window)
    session.commit()
    return True


def to_public(window: MaintenanceWindow) -> dict:
    return {
        "id": window.id,
        "name": window.name,
        "description": window.description,
        "enabled": window.enabled,
        "global_maintenance": window.global_maintenance,
        "target_features": window.target_features if isinstance(window.target_features, list) else [],
        "message": window.message,
        "allow_list_user_ids": window.allow_list_user_ids if isinstance(window.allow_list_user_ids, list) else [],
        "bypass_roles": window.bypass_roles if isinstance(window.bypass_roles, list) else [],
        "scheduled_start": window.scheduled_start.isoformat() if window.scheduled_start else None,
        "scheduled_end": window.scheduled_end.isoformat() if window.scheduled_end else None,
        "created_at": window.created_at.isoformat() if window.created_at else None,
        "updated_at": window.updated_at.isoformat() if window.updated_at else None,
    }