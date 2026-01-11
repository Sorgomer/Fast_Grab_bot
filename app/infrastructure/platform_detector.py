from __future__ import annotations

from urllib.parse import urlparse

import logging
logger = logging.getLogger(__name__)

from app.domain.models import Platform
from app.domain.errors import UnsupportedPlatformError


class PlatformDetector:
    """
    URL -> Platform.
    Stateless and deterministic.
    """

    def detect(self, url: str) -> Platform:
        logger.info("[DETECTOR] raw url=%s", url)

        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        logger.info("[DETECTOR] parsed host before normalize=%s", host)


        if not host:
            logger.warning("[DETECTOR] empty host")
            raise UnsupportedPlatformError("Не удалось определить платформу.")

        if host.startswith("www."):
            host = host[4:]
        if host.startswith("m."):
            host = host[2:]

        logger.info("[DETECTOR] normalized host=%s", host)

        if host in {"youtube.com", "youtu.be"}:
            logger.info("[DETECTOR] detected YOUTUBE")
            return Platform.YOUTUBE

        if host in {"vk.com", "vk.ru", "vkvideo.ru"}:
            logger.info("[DETECTOR] detected VK")
            return Platform.VK

        if host == "rutube.ru":
            logger.info("[DETECTOR] detected RUTUBE")
            return Platform.RUTUBE
        logger.error("[DETECTOR] unsupported host=%s", host)
        raise UnsupportedPlatformError("Эта платформа пока не поддерживается")