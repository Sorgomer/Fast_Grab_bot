from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict


class RateLimiter:
    """
    Simple sliding-window rate limiter.
    Architectural component, not UX sugar.
    """

    def __init__(self, *, limit: int, window_sec: int) -> None:
        self._limit = limit
        self._window = window_sec
        self._events: Dict[int, Deque[float]] = {}

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        q = self._events.setdefault(user_id, deque())

        while q and now - q[0] > self._window:
            q.popleft()

        if len(q) >= self._limit:
            return False

        q.append(now)
        return True