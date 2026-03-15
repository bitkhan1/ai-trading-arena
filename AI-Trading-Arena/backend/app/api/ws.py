"""
WebSocket endpoints — real-time leaderboard and trade stream.

Channels:
  /ws/leaderboard         — Live leaderboard updates every 10s
  /ws/trades              — Live trade stream (all agents)
  /ws/notify/{client_id}  — User-specific notifications (payout alerts)

Uses Redis pub/sub to fan out to all connected clients efficiently.
"""
import asyncio
import json
import logging
from typing import Dict, Set

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.redis import (
    CHANNEL_LEADERBOARD,
    CHANNEL_TRADES,
    CHANNEL_NOTIFY_PREFIX,
    get_redis,
)

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

# ── Connection managers ────────────────────────────────────────────


class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: str):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active.discard(ws)


leaderboard_manager = ConnectionManager()
trades_manager = ConnectionManager()
notify_managers: Dict[str, ConnectionManager] = {}


# ── Subscriber tasks ───────────────────────────────────────────────


async def redis_subscriber(channel: str, manager: ConnectionManager):
    """
    Subscribe to a Redis pub/sub channel and broadcast to all WS clients.
    Runs as a background asyncio task.
    """
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    logger.info(f"WebSocket subscriber started for channel: {channel}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await manager.broadcast(message["data"])
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)


# ── WebSocket Routes ───────────────────────────────────────────────


@router.websocket("/ws/leaderboard")
async def ws_leaderboard(websocket: WebSocket):
    """
    Live leaderboard WebSocket.
    Receives leaderboard_update messages pushed by the scheduler every 10s.
    """
    await leaderboard_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — client can send ping
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        leaderboard_manager.disconnect(websocket)


@router.websocket("/ws/trades")
async def ws_trades(websocket: WebSocket):
    """
    Live trade stream WebSocket.
    Receives a message for every paper trade executed by any agent.
    """
    await trades_manager.connect(websocket)
    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        trades_manager.disconnect(websocket)


@router.websocket("/ws/notify/{client_id}")
async def ws_notify(websocket: WebSocket, client_id: str):
    """
    User-specific notification WebSocket.
    Receives payout alerts, contest results, etc.
    """
    if client_id not in notify_managers:
        notify_managers[client_id] = ConnectionManager()
    mgr = notify_managers[client_id]
    await mgr.connect(websocket)
    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        mgr.disconnect(websocket)
        if not mgr.active:
            notify_managers.pop(client_id, None)


async def start_ws_subscribers():
    """Start Redis pub/sub subscriber tasks — called on app startup."""
    asyncio.create_task(redis_subscriber(CHANNEL_LEADERBOARD, leaderboard_manager))
    asyncio.create_task(redis_subscriber(CHANNEL_TRADES, trades_manager))
    logger.info("WebSocket Redis subscribers started")
