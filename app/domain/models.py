from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


UserId = NewType("UserId", int)
ChatId = NewType("ChatId", int)
MessageId = NewType("MessageId", int)


class Platform(Enum):
    YOUTUBE = "youtube"
    VK = "vk"
    RUTUBE = "rutube"


class MediaKind(Enum):
    VIDEO = "video"
    MP3 = "mp3"


class Container(Enum):
    MP4 = "mp4"
    MKV = "mkv"
    MP3 = "mp3"

    @property
    def ext(self) -> str:
        return self.value


class CodecFamily(Enum):
    H264 = "h264"
    VP9 = "vp9"
    AV1 = "av1"
    OTHER = "other"


@dataclass(frozen=True)
class VideoSelector:
    video_format_id: str
    audio_format_id: str | None
    height: int
    fps: int
    codec: CodecFamily


@dataclass(frozen=True)
class Mp3Selector:
    audio_format_id: str  # bestaudio
    bitrate_kbps: int


@dataclass(frozen=True)
class FormatOption:
    option_id: str
    kind: MediaKind
    label: str  # UI label only
    video: VideoSelector | None
    mp3: Mp3Selector | None
    container: Container
    estimated_filesize: int | None
    duration_sec: int | None


@dataclass(frozen=True)
class DownloadJob:
    chat_id: ChatId
    user_id: UserId
    url: str
    platform: Platform
    option: FormatOption
    status_message_id: MessageId  # message to edit for statuses