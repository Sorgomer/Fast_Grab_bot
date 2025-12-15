from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List

from app.domain.models import FormatOption, Platform, UserId


@dataclass
class UserSession:
    url: str
    platform: Platform
    options: List[FormatOption]
    created_at: float


class SessionStore:
    def __init__(self, ttl_sec: int = 15 * 60) -> None:
        self._ttl_sec = ttl_sec
        self._sessions: Dict[UserId, UserSession] = {}

    def set(self, user_id: UserId, session: UserSession) -> None:
        self._sessions[user_id] = session

    def get(self, user_id: UserId) -> UserSession | None:
        self._cleanup_expired()
        return self._sessions.get(user_id)

    def clear(self, user_id: UserId) -> None:
        self._sessions.pop(user_id, None)

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [uid for uid, s in self._sessions.items() if now - s.created_at > self._ttl_sec]
        for uid in expired:
            self._sessions.pop(uid, None)