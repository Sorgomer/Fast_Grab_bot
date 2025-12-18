
from __future__ import annotations

from typing import Dict


class ActiveJobsRegistry:
    """
    Per-user active job limiter.

    Responsibility:
      - track how many active jobs a user has
      - enforce max_active_per_user
    """

    def __init__(self, *, max_active_per_user: int) -> None:
        self._max = max_active_per_user
        self._counts: Dict[int, int] = {}

    def try_acquire(self, user_id: int) -> bool:
        cur = self._counts.get(user_id, 0)
        if cur >= self._max:
            return False
        self._counts[user_id] = cur + 1
        return True

    def release(self, user_id: int) -> None:
        cur = self._counts.get(user_id, 0)
        if cur <= 1:
            self._counts.pop(user_id, None)
        else:
            self._counts[user_id] = cur - 1
