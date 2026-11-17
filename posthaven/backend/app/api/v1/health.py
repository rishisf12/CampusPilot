from fastapi import APIRouter, Depends
from app.db.session import get_session, engine
from app.core.config import settings
from sqlmodel import text
import redis.asyncio as redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(session=Depends(get_session)) -> dict:
    """Liveness probe — returns ok if the app is up."""
    return {"status": "ok", "service": "posthaven-backend"}


@router.get("/ready")
async def ready(session=Depends(get_session)) -> dict:
    """Readiness probe — checks DB and Redis connectivity."""
    # DB check
    await session.execute(text("SELECT 1"))
    # Redis check
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.ping()
    await r.close()
    return {"status": "ok", "db": "up", "redis": "up"}
