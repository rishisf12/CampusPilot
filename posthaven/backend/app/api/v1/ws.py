from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
import json
import asyncio

from app.db.session import get_session
from app.core.security import decode_token
from app.models.user import User
from app.core.config import settings

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        self.active.pop(user_id, None)

    async def send_personal(self, user_id: str, message: dict) -> None:
        ws = self.active.get(user_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                self.disconnect(user_id)


manager = ConnectionManager()


async def _redis_forwarder(websocket: WebSocket, user_id: str, r) -> None:
    """Forward Redis pub/sub messages to the WebSocket."""
    pubsub = r.pubsub()
    await pubsub.subscribe(f"user:{user_id}")
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                try:
                    event = json.loads(msg["data"])
                except Exception:
                    event = {"type": "raw", "data": msg["data"]}
                await websocket.send_text(json.dumps(event))
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(f"user:{user_id}")
        await pubsub.close()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session: AsyncSession = Depends(get_session),
):
    # Read access token from httpOnly cookie (browser sends automatically)
    token = websocket.cookies.get("access_token")
    user = None
    if token:
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user = await session.get(User, payload["sub"])
    if not user or not user.is_active:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    await manager.connect(websocket, str(user.id))

    import redis.asyncio as redis

    r = redis.from_url(settings.REDIS_URL, decode_responses=True)

    forwarder = asyncio.create_task(_redis_forwarder(websocket, str(user.id), r))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await websocket.send_text(
                    json.dumps({"type": "pong", "ts": msg.get("ts")})
                )
            elif mtype == "subscribe":
                account_ids = msg.get("account_ids", [])
                await websocket.send_text(
                    json.dumps({"type": "subscribed", "account_ids": account_ids})
                )
    except WebSocketDisconnect:
        pass
    finally:
        forwarder.cancel()
        await r.aclose()
        manager.disconnect(str(user.id))
