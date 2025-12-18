from __future__ import annotations

from app.domain.models import Platform
from app.domain.errors import UnsupportedPlatformError
from .base import AbstractPlatformAdapter


class PlatformRegistry:
    """
    Maps Platform -> Adapter.
    """

    def __init__(self, *, youtube: AbstractPlatformAdapter, vk: AbstractPlatformAdapter) -> None:
        self._adapters = {
            Platform.YOUTUBE: youtube,
            Platform.VK: vk,
        }

    def get(self, platform: Platform) -> AbstractPlatformAdapter:
        try:
            return self._adapters[platform]
        except KeyError as exc:
            raise UnsupportedPlatformError("Платформа не поддерживается.") from exc