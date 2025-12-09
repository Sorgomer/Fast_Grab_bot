import re
from enum import Enum
from urllib.parse import urlparse

from app.utils.exceptions import ValidationError, UnsupportedPlatformError


class Platform(str, Enum):
    YOUTUBE = "youtube"
    PORNHUB = "pornhub"
    VK = "vk"
    VK_VIDEO = "vk_video"
    FACEBOOK = "facebook"
    DAILYMOTION = "dailymotion"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    RUTUBE = "rutube"
    TIKTOK = "tiktok"
    SOUNDCLOUD = "soundcloud"
    SPOTIFY = "spotify"


URL_REGEX = re.compile(
    r"(https?://[^\s]+)",
    flags=re.IGNORECASE,
)


def extract_first_url(text: str | None) -> str | None:
    if not text:
        return None
    m = URL_REGEX.search(text)
    if not m:
        return None
    return m.group(1)


def validate_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValidationError("Некорректная ссылка")

    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Ссылка должна начинаться с http:// или https://")

    host = parsed.hostname or ""
    # запретим локальные
    forbidden_hosts = (
        "localhost",
        "127.",
        "10.",
        "192.168.",
        "172.16.",
    )
    if any(host.startswith(h) for h in forbidden_hosts):
        raise ValidationError("Ссылка недопустима")

    return url


def detect_platform(url: str) -> Platform:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if "youtu.be" in host or "youtube.com" in host:
        return Platform.YOUTUBE
    if "tiktok.com" in host:
        return Platform.TIKTOK
    if "instagram.com" in host:
        return Platform.INSTAGRAM
    if "x.com" in host or "twitter.com" in host:
        return Platform.TWITTER
    if "vk.com" in host:
        # грубо: если в пути есть 'video'
        if "video" in (parsed.path or ""):
            return Platform.VK_VIDEO
        return Platform.VK
    if "rutube.ru" in host:
        return Platform.RUTUBE
    if "facebook.com" in host:
        return Platform.FACEBOOK
    if "dailymotion.com" in host:
        return Platform.DAILYMOTION
    if "pornhub.com" in host:
        return Platform.PORNHUB
    if "soundcloud.com" in host:
        return Platform.SOUNDCLOUD
    if "spotify.com" in host:
        return Platform.SPOTIFY

    raise UnsupportedPlatformError("Эта платформа пока не поддерживается")