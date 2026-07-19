from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import get_settings

_pool: aioredis.ConnectionPool | None = None


def _get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url, decode_responses=True, max_connections=20
        )
    return _pool


def get_redis_client() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=_get_pool())


async def get_redis() -> AsyncGenerator[aioredis.Redis]:
    client = get_redis_client()
    try:
        yield client
    finally:
        pass  # pool manages connections
