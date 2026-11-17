"""Best-effort Redis pub/sub fan-out to a user's WebSocket connections."""
import json

import redis.asyncio as redis

from app.core.config import settings


async def publish_user_event(user_id, payload: dict) -> None:
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.publish(f"user:{user_id}", json.dumps(payload))
        await r.aclose()
    except Exception:
        # WS notification is best-effort; persistence already happened
        pass
