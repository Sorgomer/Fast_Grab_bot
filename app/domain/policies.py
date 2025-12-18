from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .errors import ValidationError
from .models import (
    AudioCodec,
    AudioSpec,
    Container,
    FormatChoice,
    StreamSpec,
    VideoCodec,
    VideoSpec,
)


@dataclass(frozen=True, slots=True)
class RawExtractorFormat:
    """
    Raw format view coming from infrastructure extractor (yt-dlp).
    Infrastructure will map yt-dlp info_dict into this structure.
    """
    extractor_format_id: str
    is_video: bool
    is_audio: bool

    width: int | None
    height: int | None
    fps: float | None

    vcodec: VideoCodec
    acodec: AudioCodec

    vbr_kbps: int | None
    abr_kbps: int | None

    ext: str | None  # source ext (not final container)
    filesize_bytes: int | None


def _fps_int(fps: float | None) -> int:
    if fps is None:
        return 0
    if fps < 0:
        return 0
    return int(round(fps))


def _stable_choice_id(platform_key: str, height: int, fps_int: int, vcodec: VideoCodec, container: Container) -> str:
    seed = f"{platform_key}:{height}:{fps_int}:{vcodec.value}:{container.value}".encode("utf-8")
    return hashlib.sha1(seed).hexdigest()[:16]


def choose_container(*, vcodec: VideoCodec, acodec: AudioCodec) -> Container:
    """
    Deterministic container policy.
    Conservative:
      - MP4 for H264/H265 with AAC (typical)
      - MKV for VP9/AV1/OPUS/VORBIS to avoid compatibility issues
    """
    if vcodec in (VideoCodec.VP9, VideoCodec.AV1):
        return Container.MKV
    if acodec in (AudioCodec.OPUS, AudioCodec.VORBIS):
        return Container.MKV
    return Container.MP4


def build_label(*, height: int, fps_int: int, vcodec: VideoCodec, container: Container) -> str:
    fps_part = f"{fps_int}fps" if fps_int > 0 else "fps?"
    return f"{height}p • {fps_part} • {vcodec.value} • {container.value}"


def _pair_score(video: RawExtractorFormat, audio: RawExtractorFormat) -> tuple[int, int, int]:
    """
    Higher is better. Used only for selecting best audio for a video choice.
    """
    height = video.height or 0
    fps = _fps_int(video.fps)
    abr = audio.abr_kbps or 0
    return (height, fps, abr)


def build_format_choices(
    *,
    platform_key: str,
    raw_formats: list[RawExtractorFormat],
) -> list[FormatChoice]:
    """
    Convert raw extractor formats into final choices:
      - always video+audio
      - deduplicate by (height, fps, vcodec, chosen_container)
      - pick best audio for a given video (by abr)
    """
    videos = [f for f in raw_formats if f.is_video and not f.is_audio]
    audios = [f for f in raw_formats if f.is_audio and not f.is_video]

    if not videos or not audios:
        raise ValidationError("Не удалось найти корректные форматы (нужны видео и аудио).")

    # Candidate pairs by video; choose best matching audio
    candidates: list[tuple[RawExtractorFormat, RawExtractorFormat]] = []
    for v in videos:
        if (v.height or 0) <= 0:
            continue
        best_audio = max(audios, key=lambda a: (a.abr_kbps or 0))
        candidates.append((v, best_audio))

    if not candidates:
        raise ValidationError("Не удалось подобрать форматы с корректным разрешением.")

    # Build choices, then dedup
    built: list[FormatChoice] = []
    for v, a in candidates:
        height = int(v.height or 0)
        fps_int = _fps_int(v.fps)
        vcodec = v.vcodec if v.vcodec != VideoCodec.UNKNOWN else VideoCodec.UNKNOWN
        acodec = a.acodec if a.acodec != AudioCodec.UNKNOWN else AudioCodec.UNKNOWN

        container = choose_container(vcodec=vcodec, acodec=acodec)
        choice_id = _stable_choice_id(platform_key, height, fps_int, vcodec, container)
        label = build_label(height=height, fps_int=fps_int, vcodec=vcodec, container=container)

        video_spec = VideoSpec(
            fmt=StreamSpec(
                extractor_format_id=v.extractor_format_id,
                codec=vcodec,
                bitrate_kbps=v.vbr_kbps,
            ),
            width=v.width,
            height=v.height,
            fps=v.fps,
        )
        audio_spec = AudioSpec(
            fmt=StreamSpec(
                extractor_format_id=a.extractor_format_id,
                codec=acodec,
                bitrate_kbps=a.abr_kbps,
            ),
            sample_rate_hz=None,
        )

        built.append(
            FormatChoice(
                choice_id=choice_id,
                label=label,
                container=container,
                video=video_spec,
                audio=audio_spec,
                height=height,
                fps_int=fps_int,
                vcodec=vcodec,
            )
        )

    return deduplicate_choices(built)


def deduplicate_choices(choices: list[FormatChoice]) -> list[FormatChoice]:
    """
    Dedup policy:
      key = (height, fps_int, vcodec, container)
    Keep one choice per key (deterministic by choice_id).
    """
    buckets: dict[tuple[int, int, str, str], FormatChoice] = {}
    for c in choices:
        key = (c.height, c.fps_int, c.vcodec.value, c.container.value)
        existing = buckets.get(key)
        if existing is None or c.choice_id < existing.choice_id:
            buckets[key] = c

    # Sort by quality: height desc, fps desc, then label
    return sorted(
        buckets.values(),
        key=lambda c: (-c.height, -c.fps_int, c.label),
    )