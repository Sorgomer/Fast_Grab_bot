from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


class Platform(str, Enum):
    YOUTUBE = "youtube"
    VK = "vk"


class Container(str, Enum):
    MP4 = "mp4"
    MKV = "mkv"


class VideoCodec(str, Enum):
    H264 = "h264"
    H265 = "h265"
    VP9 = "vp9"
    AV1 = "av1"
    UNKNOWN = "unknown"


class AudioCodec(str, Enum):
    AAC = "aac"
    OPUS = "opus"
    VORBIS = "vorbis"
    MP3 = "mp3"
    UNKNOWN = "unknown"


class JobStage(str, Enum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    VALIDATING = "validating"
    SENDING = "sending"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


JobId = NewType("JobId", str)
UserId = NewType("UserId", int)
ChatId = NewType("ChatId", int)


@dataclass(frozen=True, slots=True)
class StreamSpec:
    """
    Stream spec refers to an internal platform/extractor format id.
    This is NOT shown to the user.
    """
    extractor_format_id: str
    codec: VideoCodec | AudioCodec
    bitrate_kbps: int | None


@dataclass(frozen=True, slots=True)
class VideoSpec:
    fmt: StreamSpec
    width: int | None
    height: int | None
    fps: float | None


@dataclass(frozen=True, slots=True)
class AudioSpec:
    fmt: StreamSpec
    sample_rate_hz: int | None


@dataclass(frozen=True, slots=True)
class FormatChoice:
    """
    Domain object for ONE UI BUTTON = ONE final file.

    It always represents:
      - a video stream AND an audio stream
      - an intended output container (mp4/mkv)
      - stable, deduplicated identity for callbacks/UI
    """
    choice_id: str  # stable id we generate (not yt-dlp id)
    label: str      # ready-to-show text (no markdown required)
    container: Container

    video: VideoSpec
    audio: AudioSpec

    # For dedup/UI grouping
    height: int
    fps_int: int
    vcodec: VideoCodec

    @property
    def ext(self) -> str:
        return self.container.value


@dataclass(slots=True)
class Job:
    job_id: JobId
    user_id: UserId
    chat_id: ChatId

    platform: Platform
    url: str

    choice: FormatChoice
    stage: JobStage

    # Optional, for progress/UI
    status_message_id: int | None = None
    error_user_message: str | None = None