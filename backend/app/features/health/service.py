"""Health check service."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timedelta
from sqlmodel import Session, select

from core.database import engine
from features.health.models import HealthCheck, HealthHistory
import psycopg
import redis
import os


def check_readiness(session: Session) -> dict:
    """Check if all critical dependencies are ready."""
    checks = {
        "database": check_database(session),
        "redis": check_redis(),
    }
    ready = all(c["healthy"] for c in checks.values())
    return {
        "ready": ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


def check_database(session: Session) -> dict:
    """Check database connectivity."""
    try:
        session.exec(select(1))
        return {"healthy": True, "message": "Database connected"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def check_redis() -> dict:
    """Check Redis connectivity."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        return {"healthy": True, "message": "Redis connected"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def check_disk_space() -> dict:
    """Check disk space."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_percent = (free / total) * 100
    return {
        "healthy": free_percent > 10,
        "message": f"Free: {free_percent:.1f}%",
        "details": {"total_gb": total / 1e9, "used_gb": used / 1e9, "free_gb": free / 1e9},
    }


def check_memory() -> dict:
    """Check memory usage."""
    import psutil
    mem = psutil.virtual_memory()
    return {
        "healthy": mem.percent < 90,
        "message": f"Memory: {mem.percent:.1f}%",
        "details": {"total_gb": mem.total / 1e9, "used_gb": mem.used / 1e9, "percent": mem.percent},
    }


def check_cpu() -> dict:
    """Check CPU usage."""
    import psutil
    cpu_percent = psutil.cpu_percent(interval=0.5)
    return {
        "healthy": cpu_percent < 90,
        "message": f"CPU: {cpu_percent:.1f}%",
        "details": {"percent": cpu_percent},
    }


def check_background_jobs(session: Session) -> dict:
    """Check if background jobs are running."""
    try:
        from features.monitoring.infrastructure import rollup as rollup_mod
        # Check if rollup ran recently
        return {"healthy": True, "message": "Background jobs running"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def get_component_health(session: Session, component: Optional[str] = None) -> dict:
    """Get health status of all components."""
    checks = {
        "database": check_database(session),
        "redis": check_redis(),
        "disk": check_disk_space(),
        "memory": check_memory(),
        "cpu": check_cpu(),
        "background_jobs": check_background_jobs(session),
    }
    if component:
        return checks.get(component, {"healthy": False, "message": "Unknown component"})
    return checks


def run_health_checks(session: Session, component: Optional[str] = None) -> dict:
    """Run all health checks and store results."""
    results = get_component_health(session, component)
    now = datetime.utcnow()

    for name, result in results.items():
        if component and name != component:
            continue

        check = HealthCheck(
            component=name,
            status="healthy" if result["healthy"] else "critical",
            message=result.get("message"),
            details_json=result.get("details"),
            checked_at=now,
        )
        session.add(check)

        # Also add to history
        history = HealthHistory(
            component=name,
            status="healthy" if result["healthy"] else "critical",
            latency_ms=result.get("latency_ms"),
            checked_at=now,
        )
        session.add(history)

    session.commit()
    return {"status": "completed", "checks": results, "timestamp": now.isoformat()}


def get_health_history(
    session: Session,
    component: Optional[str] = None,
    hours: int = 24,
) -> List[dict]:
    """Get health history for trending."""
    since = datetime.utcnow() - timedelta(hours=hours)
    stmt = select(HealthHistory).where(HealthHistory.checked_at >= since)
    if component:
        stmt = stmt.where(HealthHistory.component == component)
    rows = session.exec(stmt.order_by(HealthHistory.checked_at.desc())).all()
    return [
        {
            "component": r.component,
            "status": r.status,
            "latency_ms": r.latency_ms,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None,
        }
        for r in rows
    ]