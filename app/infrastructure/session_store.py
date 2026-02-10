
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import time

from app.domain.models import FormatChoice


@dataclass(slots=True)
class UserSession:
    url: str
    platform_key: str
    version: int
    choices: Dict[str, FormatChoice]
    warned_risky_once: bool
    created_mono: float


class SessionStore:
    """
    In-memory user/session context.

    Responsibility:
      - store extracted choices for a user for a short-lived session
      - keep a "warned once" flag for risky format selection UX
    """

    def __init__(self, *, ttl_sec: int) -> None:
        self._sessions: Dict[int, UserSession] = {}
        self._ttl_sec = int(ttl_sec)

    def _prune_expired(self) -> None:
        if self._ttl_sec <= 0:
            return
        now = time.monotonic()
        expired_user_ids = [
            user_id
            for user_id, session in self._sessions.items()
            if (now - session.created_mono) > self._ttl_sec
        ]
        for user_id in expired_user_ids:
            self._sessions.pop(user_id, None)

    def new_session(self, *, user_id: int, url: str, platform_key: str, choices: list[FormatChoice]) -> int:
        self._prune_expired()
        version = (self._sessions[user_id].version + 1) if user_id in self._sessions else 1
        self._sessions[user_id] = UserSession(
            url=url,
            platform_key=platform_key,
            version=version,
            choices={c.choice_id: c for c in choices},
            warned_risky_once=False,
            created_mono=time.monotonic(),
        )
        return version

    def get_choice(self, *, user_id: int, version: int, choice_id: str) -> FormatChoice:
        self._prune_expired()
        session = self._sessions.get(user_id)
        if session is None or session.version != version:
            raise KeyError("session expired")
        return session.choices[choice_id]

    def get_session_meta(self, *, user_id: int, version: int) -> tuple[str, str]:
        self._prune_expired()
        session = self._sessions.get(user_id)
        if session is None or session.version != version:
            raise KeyError("session expired")
        return session.url, session.platform_key

    def warned_risky_once(self, *, user_id: int, version: int) -> bool:
        self._prune_expired()
        session = self._sessions.get(user_id)
        if session is None or session.version != version:
            raise KeyError("session expired")
        return session.warned_risky_once

    def mark_warned_risky_once(self, *, user_id: int, version: int) -> None:
        self._prune_expired()
        session = self._sessions.get(user_id)
        if session is None or session.version != version:
            raise KeyError("session expired")
        session.warned_risky_once = True

    def clear(self, *, user_id: int) -> None:
        self._sessions.pop(user_id, None)
