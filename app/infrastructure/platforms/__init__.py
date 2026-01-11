from __future__ import annotations

from .base import AbstractPlatformAdapter
from .youtube import YouTubeAdapter
from .vk import VkAdapter
from .rutube import RutubeAdapter
from .registry import PlatformRegistry

__all__ = [
    "AbstractPlatformAdapter",
    "YouTubeAdapter",
    "VkAdapter",
    'RutubeAdapter'
    "PlatformRegistry",
]