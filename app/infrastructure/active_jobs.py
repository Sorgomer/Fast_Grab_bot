
from __future__ import annotations

from typing import Dict
import time
from typing import Tuple


class ActiveJobsRegistry:
    """
    Per-user active job limiter.

    Responsibility:
      - track how many active jobs a user has
      - enforce max_active_per_user
    """

    def __init__(self, *, max_active_per_user: int, stale_ttl_sec: int) -> None:
        self._max = max_active_per_user
        self._stale_ttl_sec = int(stale_ttl_sec)
        self._counts: Dict[int, tuple[int, float]] = {}

    def _prune_stale(self) -> None:
        if self._stale_ttl_sec <= 0:
            return
        now = time.monotonic()
        stale_user_ids = [
            user_id
            for user_id, (_cnt, touched) in self._counts.items()
            if (now - touched) > self._stale_ttl_sec
        ]
        for user_id in stale_user_ids:
            self._counts.pop(user_id, None)

    def try_acquire(self, user_id: int) -> bool:
        self._prune_stale()
        cur, _touched = self._counts.get(user_id, (0, 0.0))
        if cur >= self._max:
            return False
        self._counts[user_id] = (cur + 1, time.monotonic())
        return True

    def release(self, user_id: int) -> None:
        cur, _touched = self._counts.get(user_id, (0, 0.0))
        if cur <= 1:
            self._counts.pop(user_id, None)
        else:
            self._counts[user_id] = (cur - 1, time.monotonic())
