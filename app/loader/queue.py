from typing import Optional

from redis.asyncio import Redis

from app.config.settings import get_settings
from app.services.download_manager import DownloadManager
from app.services.rate_limiter import RateLimiter


_download_manager: Optional[DownloadManager] = None
_rate_limiter: Optional[RateLimiter] = None


def create_download_infrastructure(bot, redis: Optional[Redis]) -> DownloadManager:
    global _download_manager, _rate_limiter
    settings = get_settings()
    _rate_limiter = RateLimiter(
        redis=redis,
        user_rate_limit=settings.user_rate_limit,
        user_rate_interval=settings.user_rate_interval_sec,
        max_parallel_downloads_per_user=settings.max_parallel_downloads_per_user,
        max_global_downloads=settings.max_global_downloads,
    )
    _download_manager = DownloadManager(
        bot=bot,
        rate_limiter=_rate_limiter,
    )
    return _download_manager


def get_download_manager() -> DownloadManager:
    if _download_manager is None:
        raise RuntimeError("DownloadManager is not initialized")
    return _download_manager


def get_rate_limiter() -> RateLimiter:
    if _rate_limiter is None:
        raise RuntimeError("RateLimiter is not initialized")
    return _rate_limiter