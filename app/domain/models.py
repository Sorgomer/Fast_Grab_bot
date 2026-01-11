
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


class Platform(str, Enum):
    YOUTUBE = "youtube"
    VK = "vk"
    RUTUBE = "rutube"


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


class ChoiceAvailability(str, Enum):
    GUARANTEED = "guaranteed"   # safe zone
    RISKY = "risky"             # might fail through Telegram
    UNAVAILABLE = "unavailable" # exceeds hard limit


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
    One UI button == one final file (video+audio merged into a container).

    estimated_bytes:
      Best-effort estimate (may be None when extractor doesn't provide size).
      Used only for UX and pre-validation. Not a guarantee.
    """
    choice_id: str
    label: str

    container: Container
    availability: ChoiceAvailability

    video: VideoSpec
    audio: AudioSpec

    height: int
    fps_int: int
    vcodec: VideoCodec

    estimated_bytes: int | None = None

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

    status_message_id: int | None = None
    error_user_message: str | None = None
