
from __future__ import annotations

from app.domain.errors import ValidationError
from app.domain.policies import TelegramLimits, build_format_choices
from app.infrastructure.yt import YdlClient


class YouTubeAdapter:
    """
    YouTube platform adapter.
    """

    def __init__(self, *, ydl: YdlClient, tg_limits: TelegramLimits) -> None:
        self._ydl = ydl
        self._tg_limits = tg_limits

    async def extract_choices(self, url: str):
        result = await self._ydl.extract(url)

        choices = build_format_choices(
            platform_key="youtube",
            raw_formats=result.raw_formats,
            tg_limits=self._tg_limits,
        )
        if not choices:
            raise ValidationError("Не удалось подобрать форматы для YouTube.")

        return choices
