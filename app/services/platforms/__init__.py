from typing import Dict

from app.utils.url_tools import Platform
from .base import YtDlpPlatformDownloader, BasePlatformDownloader


_downloaders: Dict[Platform, BasePlatformDownloader] = {
    Platform.YOUTUBE: YtDlpPlatformDownloader(Platform.YOUTUBE),
    Platform.PORNHUB: YtDlpPlatformDownloader(Platform.PORNHUB),
    Platform.VK: YtDlpPlatformDownloader(Platform.VK),
    Platform.VK_VIDEO: YtDlpPlatformDownloader(Platform.VK_VIDEO),
    Platform.FACEBOOK: YtDlpPlatformDownloader(Platform.FACEBOOK),
    Platform.DAILYMOTION: YtDlpPlatformDownloader(Platform.DAILYMOTION),
    Platform.TWITTER: YtDlpPlatformDownloader(Platform.TWITTER),
    Platform.INSTAGRAM: YtDlpPlatformDownloader(Platform.INSTAGRAM),
    Platform.RUTUBE: YtDlpPlatformDownloader(Platform.RUTUBE),
    Platform.TIKTOK: YtDlpPlatformDownloader(Platform.TIKTOK),
    Platform.SOUNDCLOUD: YtDlpPlatformDownloader(Platform.SOUNDCLOUD),
    Platform.SPOTIFY: YtDlpPlatformDownloader(Platform.SPOTIFY),
}


def get_downloader(platform: Platform) -> BasePlatformDownloader:
    return _downloaders[platform]