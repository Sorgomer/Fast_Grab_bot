from __future__ import annotations

import logging

from app.domain.errors import ValidationError
from app.domain.policies import TelegramLimits, build_format_choices
from app.infrastructure.yt import YdlClient
from app.infrastructure.yt.ydl_client import YdlError

logger = logging.getLogger(__name__)

class RutubeAdapter:
    def __init__(self, *, ydl: YdlClient, tg_limits: TelegramLimits) -> None:
        self._ydl = ydl
        self._tg_limits = tg_limits

    async def extract_choices(self, url: str):
        logger.info("[RUTUBE] extract_choices url=%s", url)
        
        try:
            result = await self._ydl.extract(
                url,
                extra_opts={
                    "format": "bestvideo+bestaudio/best",
                    "skip_download": True,
                },
            )
        except YdlError as exc:
            logger.warning("[RUTUBE] primary extract failed: %s", exc)
            logger.info("[RUTUBE] retry with fallback format=best")

            try:
                result = await self._ydl.extract(
                    url,
                    extra_opts={
                        "format": "best",
                        "skip_download": True,
                    },
                )
            except YdlError as exc:
                logger.warning("[RUTUBE] fallback extract failed: %s", exc)
                raise ValidationError(
                    "RuTube временно не отвечает. Попробуйте позже или другое видео."
                ) from exc

        logger.info(
            "[RUTUBE] raw formats count=%d",
            len(result.raw_formats),
        )

        choices = build_format_choices(
            platform_key="rutube", 
            raw_formats=result.raw_formats, 
            tg_limits=self._tg_limits
        )
        if not choices:
            raise ValidationError("Не удалось подобрать форматы для RuTube.")
        
        return choices