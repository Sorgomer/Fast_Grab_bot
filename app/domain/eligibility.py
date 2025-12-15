

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Eligibility(Enum):
    PASS = "pass"
    RISK = "risk"
    FAIL = "fail"


class EligibilityReason(Enum):
    FILE_TOO_LARGE = "file_too_large"
    LONG_DURATION = "long_duration"
    HIGH_BITRATE = "high_bitrate"
    UNSUPPORTED_CONTAINER = "unsupported_container"
    UNSUPPORTED_VIDEO_CODEC = "unsupported_video_codec"
    HIGH_FPS = "high_fps"


@dataclass(frozen=True)
class EligibilityResult:
    status: Eligibility
    reason_codes: tuple[EligibilityReason, ...]


class EligibilityChecker:
    MAX_SIZE_BYTES = int(2 * 1024 * 1024 * 1024)          # 2 GB
    RISK_SIZE_BYTES = int(1.5 * 1024 * 1024 * 1024)      # 1.5 GB

    RISK_DURATION_SEC = 30 * 60                          # 30 minutes
    FAIL_DURATION_SEC = 90 * 60                          # 90 minutes

    RISK_BITRATE_KBPS = 8000
    FAIL_BITRATE_KBPS = 12000

    MAX_FPS = 60

    SUPPORTED_CONTAINERS = {"mp4", "mkv"}
    SUPPORTED_VIDEO_CODECS = {"h264"}

    def check(
        self,
        *,
        container: str | None,
        video_codec: str | None,
        fps: int | None,
        duration_sec: int | None,
        filesize_bytes: int | None,
    ) -> EligibilityResult:
        reasons: list[EligibilityReason] = []

        # Container
        if container and container not in self.SUPPORTED_CONTAINERS:
            return EligibilityResult(
                status=Eligibility.FAIL,
                reason_codes=(EligibilityReason.UNSUPPORTED_CONTAINER,),
            )

        # Video codec
        if video_codec and video_codec not in self.SUPPORTED_VIDEO_CODECS:
            return EligibilityResult(
                status=Eligibility.FAIL,
                reason_codes=(EligibilityReason.UNSUPPORTED_VIDEO_CODEC,),
            )

        # Filesize
        if filesize_bytes:
            if filesize_bytes > self.MAX_SIZE_BYTES:
                return EligibilityResult(
                    status=Eligibility.FAIL,
                    reason_codes=(EligibilityReason.FILE_TOO_LARGE,),
                )
            if filesize_bytes > self.RISK_SIZE_BYTES:
                reasons.append(EligibilityReason.FILE_TOO_LARGE)

        # Duration
        if duration_sec:
            if duration_sec > self.FAIL_DURATION_SEC:
                return EligibilityResult(
                    status=Eligibility.FAIL,
                    reason_codes=(EligibilityReason.LONG_DURATION,),
                )
            if duration_sec > self.RISK_DURATION_SEC:
                reasons.append(EligibilityReason.LONG_DURATION)

        # Bitrate (kbps)
        if filesize_bytes and duration_sec and duration_sec > 0:
            bitrate_kbps = int((filesize_bytes * 8) / duration_sec / 1000)
            if bitrate_kbps > self.FAIL_BITRATE_KBPS:
                return EligibilityResult(
                    status=Eligibility.FAIL,
                    reason_codes=(EligibilityReason.HIGH_BITRATE,),
                )
            if bitrate_kbps > self.RISK_BITRATE_KBPS:
                reasons.append(EligibilityReason.HIGH_BITRATE)

        # FPS
        if fps and fps > self.MAX_FPS:
            reasons.append(EligibilityReason.HIGH_FPS)

        if reasons:
            return EligibilityResult(
                status=Eligibility.RISK,
                reason_codes=tuple(sorted(set(reasons), key=lambda r: r.value)),
            )

        return EligibilityResult(status=Eligibility.PASS, reason_codes=())