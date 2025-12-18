from __future__ import annotations

from app.domain.policies import build_format_choices
from app.domain.errors import ValidationError
from app.infrastructure.yt import YdlClient


class VkAdapter:
    """
    VK / VK Video adapter.
    """

    def __init__(self, *, ydl: YdlClient) -> None:
        self._ydl = ydl

    async def extract_choices(self, url: str):
        result = await self._ydl.extract(url)

        choices = build_format_choices(
            platform_key="vk",
            raw_formats=result.raw_formats,
        )
        if not choices:
            raise ValidationError("Не удалось подобрать форматы для VK.")

        return choices