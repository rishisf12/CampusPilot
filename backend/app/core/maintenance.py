"""Maintenance mode middleware and utilities."""
from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from sqlmodel import Session, select
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class MaintenanceWindow:
    id: int
    name: str
    enabled: bool
    global_maintenance: bool
    target_features: list[str]
    message: Optional[str]
    allow_list_user_ids: list[int]
    bypass_roles: list[str]
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]


class MaintenanceMode:
    """In-memory maintenance mode state."""

    def __init__(self) -> None:
        self._windows: list[MaintenanceWindow] = []
        self._loaded = False

    def load(self, session: Session) -> None:
        """Load maintenance windows from database."""
        from models import MaintenanceWindow as MWModel

        windows = session.exec(
            select(MWModel).where(MWModel.enabled == True)
        ).all()

        self._windows = [
            MaintenanceWindow(
                id=w.id,
                name=w.name,
                enabled=w.enabled,
                global_maintenance=w.global_maintenance,
                target_features=w.target_features if isinstance(w.target_features, list) else [],
                message=w.message,
                allow_list_user_ids=w.allow_list_user_ids if isinstance(w.allow_list_user_ids, list) else [],
                bypass_roles=w.bypass_roles if isinstance(w.bypass_roles, list) else [],
                scheduled_start=w.scheduled_start,
                scheduled_end=w.scheduled_end,
            )
            for w in windows
        ]
        self._loaded = True

    def is_active(
        self,
        *,
        user_id: Optional[int] = None,
        user_role: Optional[str] = None,
        feature: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Optional[MaintenanceWindow]:
        """Check if maintenance mode is active for the given context.

        Returns the active window if maintenance applies, None otherwise.
        """
        if not self._loaded:
            return None

        now = datetime.utcnow()

        for window in self._windows:
            # Check schedule
            if window.scheduled_start and now < window.scheduled_start:
                continue
            if window.scheduled_end and now > window.scheduled_end:
                continue

            # Check allow list (bypass)
            if user_id and user_id in window.allow_list_user_ids:
                continue

            # Check bypass roles
            if user_role and user_role in window.bypass_roles:
                continue

            # Global maintenance affects everything
            if window.global_maintenance:
                return window

            # Feature-specific maintenance
            if feature and feature in window.target_features:
                return window

        return None


maintenance_mode = MaintenanceMode()


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce maintenance mode."""

    async def dispatch(self, request: Request, call_next):
        # Skip health checks
        if request.url.path in ("/health", "/health/live", "/health/ready"):
            return await call_next(request)

        # Get user context if available
        user_id = getattr(request.state, "user_id", None)
        user_role = getattr(request.state, "user_role", None)

        # Determine feature from path
        feature = None
        if request.url.path.startswith("/admin"):
            feature = "admin"
        elif request.url.path.startswith("/timetable"):
            feature = "timetable"
        elif request.url.path.startswith("/exam"):
            feature = "exam"
        elif request.url.path.startswith("/ocr"):
            feature = "ocr"
        elif request.url.path.startswith("/reinforcement"):
            feature = "reinforcement"
        elif request.url.path.startswith("/monitoring"):
            feature = "monitoring"

        window = maintenance_mode.is_active(
            user_id=user_id,
            user_role=user_role,
            feature=feature,
            path=request.url.path,
        )

        if window:
            return Response(
                content=f'{{"detail": "Service under maintenance", "message": "{window.message or "Service temporarily unavailable. Please try again later."}", "window": "{window.name}"}}',
                status_code=503,
                media_type="application/json",
                headers={"Retry-After": "300"},
            )

        return await call_next(request)


def get_maintenance_status(
    *,
    user_id: Optional[int] = None,
    user_role: Optional[str] = None,
    feature: Optional[str] = None,
) -> Optional[dict]:
    """Get maintenance status for UI display."""
    window = maintenance_mode.is_active(
        user_id=user_id, user_role=user_role, feature=feature
    )
    if not window:
        return None
    return {
        "active": True,
        "window_id": window.id,
        "name": window.name,
        "message": window.message,
        "global": window.global_maintenance,
        "features": window.target_features,
    }