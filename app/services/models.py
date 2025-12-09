from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from app.utils.url_tools import Platform


class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class FormatKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    MP3 = "mp3"


@dataclass
class MediaFormat:
    id: str
    label: str
    media_type: MediaType
    kind: FormatKind
    filesize: Optional[int] = None
    ext: str | None = None
    video_quality: str | None = None
    audio_bitrate_kbps: Optional[int] = None


@dataclass
class MediaInfo:
    platform: Platform
    url: str
    title: str
    thumbnail: Optional[str]
    duration: Optional[int]
    formats: list[MediaFormat] = field(default_factory=list)


class DownloadTaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    id: str
    user_id: int
    chat_id: int
    message_id: int
    platform: Platform
    url: str
    media_info: MediaInfo
    format: MediaFormat
    status: DownloadTaskStatus = DownloadTaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    file_path: Optional[str] = None
    error_message: Optional[str] = None

    def update_status(self, status: DownloadTaskStatus) -> None:
        self.status = status
        self.updated_at = datetime.utcnow()