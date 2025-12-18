from __future__ import annotations

from urllib.parse import urlparse

from app.domain.models import Platform
from app.domain.errors import UnsupportedPlatformError


class PlatformDetector:
    """
    URL -> Platform.
    Stateless and deterministic.
    """

    def detect(self, url: str) -> Platform:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()

        if not host:
            raise UnsupportedPlatformError("Не удалось определить платформу.")

        if host.startswith("www."):
            host = host[4:]
        if host.startswith("m."):
            host = host[2:]

        if "youtube.com" in host or "youtu.be" in host:
            return Platform.YOUTUBE

        if host.endswith("vk.com") or host.endswith("vk.ru"):
            return Platform.VK

        raise UnsupportedPlatformError("Поддерживаются только YouTube и VK Video.")