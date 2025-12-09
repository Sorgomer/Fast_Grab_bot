from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from redis.asyncio import Redis


class RateLimiter:
    def __init__(
        self,
        redis: Optional[Redis],
        user_rate_limit: int,
        user_rate_interval: int,
        max_parallel_downloads_per_user: int,
        max_global_downloads: int,
    ):
        self.redis = redis
        self.user_rate_limit = user_rate_limit
        self.user_rate_interval = user_rate_interval
        self.max_parallel_downloads_per_user = max_parallel_downloads_per_user
        self.max_global_downloads = max_global_downloads

        # in-memory fallback
        self._message_timestamps: dict[int, list[float]] = defaultdict(list)
        self._active_downloads_per_user: dict[int, int] = defaultdict(int)
        self._active_downloads_global: int = 0

    async def check_and_increment_messages(self, user_id: int) -> bool:
        now = time.time()
        window_start = now - self.user_rate_interval

        timestamps = self._message_timestamps[user_id]
        timestamps = [t for t in timestamps if t >= window_start]
        if len(timestamps) >= self.user_rate_limit:
            self._message_timestamps[user_id] = timestamps
            return False
        timestamps.append(now)
        self._message_timestamps[user_id] = timestamps
        return True

    async def can_start_download(self, user_id: int) -> bool:
        if self._active_downloads_global >= self.max_global_downloads:
            return False
        if self._active_downloads_per_user[user_id] >= self.max_parallel_downloads_per_user:
            return False
        return True

    async def register_download_start(self, user_id: int) -> None:
        self._active_downloads_global += 1
        self._active_downloads_per_user[user_id] += 1

    async def register_download_end(self, user_id: int) -> None:
        self._active_downloads_global = max(0, self._active_downloads_global - 1)
        self._active_downloads_per_user[user_id] = max(
            0, self._active_downloads_per_user[user_id] - 1
        )