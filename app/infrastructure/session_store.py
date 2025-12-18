from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.domain.models import FormatChoice


@dataclass(slots=True)
class UserSession:
    url: str
    platform_key: str
    version: int
    choices: Dict[str, FormatChoice]


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[int, UserSession] = {}

    def new_session(self, *, user_id: int, url: str, platform_key: str, choices: list[FormatChoice]) -> int:
        version = (self._sessions[user_id].version + 1) if user_id in self._sessions else 1
        self._sessions[user_id] = UserSession(
            url=url,
            platform_key=platform_key,
            version=version,
            choices={c.choice_id: c for c in choices},
        )
        return version

    def get_choice(self, *, user_id: int, version: int, choice_id: str) -> FormatChoice:
        session = self._sessions.get(user_id)
        if session is None or session.version != version:
            raise KeyError("session expired")
        return session.choices[choice_id]

    def get_session_meta(self, *, user_id: int, version: int) -> tuple[str, str]:
        session = self._sessions.get(user_id)
        if session is None or session.version != version:
            raise KeyError("session expired")
        return session.url, session.platform_key

    def clear(self, *, user_id: int) -> None:
        self._sessions.pop(user_id, None)