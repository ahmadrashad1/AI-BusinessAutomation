import time

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.exceptions import RateLimitError


async def check_rate_limit(
    redis: aioredis.Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """
    Sliding-window rate limiter backed by Redis sorted sets.

    Raises RateLimitError (429) when `limit` requests have been made within
    `window_seconds`. The key should include an identifier (IP, user_id, etc.)
    to scope the limit appropriately.

    No-ops when RATE_LIMIT_ENABLED=False (for test environments).
    """
    if not get_settings().RATE_LIMIT_ENABLED:
        return

    now = time.time()
    window_start = now - window_seconds
    full_key = f"rate_limit:{key}"

    pipe = redis.pipeline()
    pipe.zremrangebyscore(full_key, "-inf", window_start)
    pipe.zadd(full_key, {str(now): now})
    pipe.zcard(full_key)
    pipe.expire(full_key, window_seconds)
    results = await pipe.execute()

    count: int = results[2]
    if count > limit:
        retry_after = window_seconds
        raise RateLimitError(retry_after=retry_after)
