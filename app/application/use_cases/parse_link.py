from __future__ import annotations

from app.application.dto import ParsedLinkDTO
from app.domain.validators import validate_url
from app.infrastructure.platform_detector import PlatformDetector


class ParseLinkUseCase:
    def __init__(self, *, detector: PlatformDetector) -> None:
        self._detector = detector

    async def execute(self, raw_text: str) -> ParsedLinkDTO:
        url = raw_text.strip()
        validate_url(url)
        platform = self._detector.detect(url)
        return ParsedLinkDTO(url=url, platform=platform)