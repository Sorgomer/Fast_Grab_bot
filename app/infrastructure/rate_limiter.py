from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict
from dataclasses import dataclass
@dataclass(slots=True)
class _RateBucket:
    q: Deque[float]
    last_seen_mono: float


class RateLimiter:
    """
    Simple sliding-window rate limiter.
    Architectural component, not UX sugar.
    """

    def __init__(self, *, limit: int, window_sec: int, idle_ttl_sec: int) -> None:
        self._limit = limit
        self._window = window_sec
        self._idle_ttl = int(idle_ttl_sec)
        self._events: Dict[int, _RateBucket] = {}

    def _prune_idle(self, now: float) -> None:
        if self._idle_ttl <= 0:
            return
        stale_user_ids = [
            user_id
            for user_id, bucket in self._events.items()
            if (now - bucket.last_seen_mono) > self._idle_ttl
        ]
        for user_id in stale_user_ids:
            self._events.pop(user_id, None)

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        self._prune_idle(now)

        bucket = self._events.get(user_id)
        if bucket is None:
            bucket = _RateBucket(q=deque(), last_seen_mono=now)
            self._events[user_id] = bucket
        else:
            bucket.last_seen_mono = now

        q = bucket.q

        while q and now - q[0] > self._window:
            q.popleft()

        # Drop empty buckets to prevent unbounded growth.
        if not q:
            # Keep bucket only if we are going to accept and append below.
            if self._limit <= 0:
                self._events.pop(user_id, None)
                return False

        if len(q) >= self._limit:
            return False

        q.append(now)
        return True