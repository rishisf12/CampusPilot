"""Request monitoring middleware - logs every request with timing, user info, etc."""
from __future__ import annotations
import time
import uuid
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.config import settings


class RequestMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to monitor all HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Extract user info if available
        user_id = getattr(request.state, "user_id", None)
        user_role = getattr(request.state, "user_role", None)
        app_version = request.headers.get("X-App-Version", "unknown")
        platform = request.headers.get("X-Platform", "web")

        # Start timing
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request (skip health checks and metrics)
            if not self._should_skip_logging(request.url.path):
                self._log_request(
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    user_id=user_id,
                    user_role=user_role,
                    app_version=app_version,
                    platform=platform,
                )

        return response

    def _should_skip_logging(self, path: str) -> bool:
        """Skip logging for health checks, metrics, and static files."""
        skip_paths = ("/health", "/health/live", "/health/ready", "/metrics", "/favicon.ico")
        return any(path.startswith(p) for p in skip_paths)

    def _log_request(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[int],
        user_role: Optional[str],
        app_version: str,
        platform: str,
    ) -> None:
        """Log request to database (async, non-blocking)."""
        # For now, just log to stdout. In production, use a queue.
        log_data = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
            "user_role": user_role,
            "app_version": app_version,
            "platform": platform,
        }
        # TODO: Send to logging service / database
        # For now, just print slow requests
        if duration_ms > settings.health_slow_query_ms:
            print(f"SLOW REQUEST: {log_data}")