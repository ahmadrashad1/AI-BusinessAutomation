from collections.abc import AsyncGenerator
import redis.asyncio as aioredis

from app.core.config import get_settings

_pool: aioredis.ConnectionPool | None = None


def get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=50,
            decode_responses=True,
        )
    return _pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency that yields a Redis connection from the shared pool."""
    client: aioredis.Redis = aioredis.Redis(connection_pool=get_pool())
    try:
        yield client
    finally:
        await client.aclose()
