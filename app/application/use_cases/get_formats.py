from __future__ import annotations

from app.application.dto import FormatListDTO
from app.infrastructure.platforms.registry import PlatformRegistry
from app.infrastructure.session_store import SessionStore
from app.domain.models import Platform


class GetFormatsUseCase:
    def __init__(
        self,
        *,
        registry: PlatformRegistry,
        sessions: SessionStore,
    ) -> None:
        self._registry = registry
        self._sessions = sessions

    async def execute(self, *, user_id: int, url: str, platform: Platform) -> FormatListDTO:
        adapter = self._registry.get(platform)
        choices = await adapter.extract_choices(url)

        version = self._sessions.new_session(
            user_id=user_id,
            url=url,
            platform_key=platform.value,
            choices=choices,
        )

        return FormatListDTO(
            platform=platform,
            choices=choices,
            session_version=version,
        )