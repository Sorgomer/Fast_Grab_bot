from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.domain.errors import UnsupportedPlatformError
from app.domain.models import Platform


@dataclass(frozen=True)
class PlatformDetector:
    def detect(self, url: str) -> Platform:
        parsed = urlparse(url.strip())
        host = (parsed.netloc or "").lower()

        host = host.removeprefix("www.")
        host = host.removeprefix("m.")

        if host.endswith("youtube.com") or host == "youtu.be":
            return Platform.YOUTUBE

        if host.endswith("vk.com") or host.endswith("vk.ru") or host.endswith("vkvideo.ru"):
            return Platform.VK

        if host.endswith("rutube.ru"):
            return Platform.RUTUBE

        raise UnsupportedPlatformError("Поддерживаются только YouTube и VK/VK Video.")