"""
Redis client — used for:
  - Leaderboard cache (sorted sets)
  - WebSocket pub/sub channels
  - Rate limiting
  - Session storage
"""
import json
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

# Singleton Redis client
_redis: Optional[Redis] = None


async def get_redis() -> Redis:
    """Return the shared Redis connection pool."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── Pub/Sub channel names ─────────────────────────────────────
CHANNEL_LEADERBOARD = "arena:leaderboard"
CHANNEL_TRADES = "arena:trades"
CHANNEL_NOTIFY_PREFIX = "arena:notify:"  # + user_id


async def publish(channel: str, message: dict):
    """Publish a JSON message to a Redis pub/sub channel."""
    r = await get_redis()
    await r.publish(channel, json.dumps(message))


async def set_cache(key: str, value: Any, expire_seconds: int = 60):
    r = await get_redis()
    await r.setex(key, expire_seconds, json.dumps(value))


async def get_cache(key: str) -> Optional[Any]:
    r = await get_redis()
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None


async def delete_cache(key: str):
    r = await get_redis()
    await r.delete(key)
