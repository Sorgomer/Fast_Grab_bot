from __future__ import annotations

from .base import AbstractPlatformAdapter
from .youtube import YouTubeAdapter
from .vk import VkAdapter
from .registry import PlatformRegistry

__all__ = [
    "AbstractPlatformAdapter",
    "YouTubeAdapter",
    "VkAdapter",
    "PlatformRegistry",
]