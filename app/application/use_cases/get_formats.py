from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

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
        logger.info(
            "[GET_FORMATS] start user_id=%s platform=%s url=%s",
            user_id,
            platform,
            url,
        )
        
        adapter = self._registry.get(platform)
        logger.info(
            "[GET_FORMATS] adapter resolved: %s",
            adapter.__class__.__name__,
        )

        choices = await adapter.extract_choices(url)
        logger.info(
            "[GET_FORMATS] choices extracted: %d",
            len(choices),
        )

        version = self._sessions.new_session(
            user_id=user_id,
            url=url,
            platform_key=platform.value,
            choices=choices,
        )
        logger.info(
            "[GET_FORMATS] session stored user_id=%s version=%s",
            user_id,
            version,
        )

        return FormatListDTO(
            platform=platform,
            choices=choices,
            session_version=version,
        )