from typing import Optional

from loguru import logger
from redis.asyncio import Redis

from app.config.settings import get_settings

_redis: Optional[Redis] = None


async def init_redis() -> Optional[Redis]:
    global _redis
    settings = get_settings()
    if not settings.redis_dsn:
        logger.warning("REDIS_DSN is not set, running without Redis")
        _redis = None
        return None
    _redis = Redis.from_url(settings.redis_dsn, decode_responses=True)
    try:
        await _redis.ping()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e!r}")
        _redis = None
    return _redis


def get_redis() -> Optional[Redis]:
    return _redis