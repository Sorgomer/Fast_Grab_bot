
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .errors import ValidationError
from .models import (
    AudioCodec,
    AudioSpec,
    ChoiceAvailability,
    Container,
    FormatChoice,
    StreamSpec,
    VideoCodec,
    VideoSpec,
)


@dataclass(frozen=True, slots=True)
class TelegramLimits:
    hard_bytes: int
    safe_bytes: int
    risky_bytes: int
    best_effort_from_bytes: int


@dataclass(frozen=True, slots=True)
class RawExtractorFormat:
    """
    Raw format view coming from infrastructure extractor (yt-dlp).
    Infrastructure maps yt-dlp info_dict into this structure.
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

    ext: str | None
    filesize_bytes: int | None


def _fps_int(fps: float | None) -> int:
    if fps is None or fps <= 0:
        return 0
    return int(round(fps))


def _stable_choice_id(platform_key: str, height: int, fps_int: int, vcodec: VideoCodec, container: Container) -> str:
    seed = f"{platform_key}:{height}:{fps_int}:{vcodec.value}:{container.value}".encode("utf-8")
    return hashlib.sha1(seed).hexdigest()[:16]


def choose_container(*, vcodec: VideoCodec, acodec: AudioCodec) -> Container:
    # safest default: MP4 with H.264(+AAC). Anything else increases risk.
    if vcodec in (VideoCodec.AV1, VideoCodec.VP9):
        return Container.MKV
    if acodec in (AudioCodec.OPUS, AudioCodec.VORBIS):
        return Container.MKV
    return Container.MP4


def _estimate_total_bytes(video: RawExtractorFormat, audio: RawExtractorFormat) -> int | None:
    if video.filesize_bytes is None or audio.filesize_bytes is None:
        return None
    total = int(video.filesize_bytes) + int(audio.filesize_bytes)
    # small muxing overhead
    return int(total * 1.01)


def _risk_boost(*, height: int, fps_int: int, vcodec: VideoCodec, container: Container) -> int:
    """
    Purely UX-level risk heuristic.
    - 4K/60fps are common pain points in Telegram delivery and processing.
    - MKV/AV1/VP9 increase compatibility risk.
    """
    boost = 0
    if height >= 2160:
        boost += 2
    if fps_int >= 60:
        boost += 2
    if container == Container.MKV:
        boost += 1
    if vcodec in (VideoCodec.AV1, VideoCodec.VP9):
        boost += 1
    return boost


def _availability(*, estimated: int | None, limits: TelegramLimits, risk_boost: int) -> ChoiceAvailability:
    if estimated is not None and estimated > limits.hard_bytes:
        return ChoiceAvailability.UNAVAILABLE

    # Unknown size => cannot guarantee; show risky (but not blocked).
    if estimated is None:
        return ChoiceAvailability.RISKY

    # Safe zone upper bound, but boost can move it to risky.
    if estimated <= limits.safe_bytes and risk_boost == 0:
        return ChoiceAvailability.GUARANTEED
    if estimated <= limits.safe_bytes and risk_boost >= 3:
        return ChoiceAvailability.RISKY

    # Between safe and hard => risky.
    return ChoiceAvailability.RISKY


def _mark(av: ChoiceAvailability) -> str:
    if av == ChoiceAvailability.GUARANTEED:
        return "✅"
    if av == ChoiceAvailability.RISKY:
        return "⚠️"
    return "❌"


def build_label(*, height: int, fps_int: int, vcodec: VideoCodec, container: Container, availability: ChoiceAvailability) -> str:
    fps_part = f"{fps_int}fps" if fps_int > 0 else "fps?"
    return f"{_mark(availability)} {height}p • {fps_part} • {vcodec.value} • {container.value}"


def build_format_choices(
    *,
    platform_key: str,
    raw_formats: list[RawExtractorFormat],
    tg_limits: TelegramLimits,
) -> list[FormatChoice]:
    videos = [f for f in raw_formats if f.is_video and not f.is_audio]
    audios = [f for f in raw_formats if f.is_audio and not f.is_video]
    if not videos or not audios:
        raise ValidationError("Не удалось найти корректные форматы (нужны видео и аудио).")

    best_audio = max(audios, key=lambda a: (a.abr_kbps or 0, a.filesize_bytes or 0))
    acodec = best_audio.acodec

    built: list[FormatChoice] = []
    for v in videos:
        height = int(v.height or 0)
        if height <= 0:
            continue

        fps_int = _fps_int(v.fps)
        vcodec = v.vcodec
        container = choose_container(vcodec=vcodec, acodec=acodec)

        estimated = _estimate_total_bytes(v, best_audio)
        boost = _risk_boost(height=height, fps_int=fps_int, vcodec=vcodec, container=container)
        availability = _availability(estimated=estimated, limits=tg_limits, risk_boost=boost)

        choice_id = _stable_choice_id(platform_key, height, fps_int, vcodec, container)
        label = build_label(height=height, fps_int=fps_int, vcodec=vcodec, container=container, availability=availability)

        built.append(
            FormatChoice(
                choice_id=choice_id,
                label=label,
                container=container,
                availability=availability,
                video=VideoSpec(
                    fmt=StreamSpec(v.extractor_format_id, vcodec, v.vbr_kbps),
                    width=v.width,
                    height=v.height,
                    fps=v.fps,
                ),
                audio=AudioSpec(
                    fmt=StreamSpec(best_audio.extractor_format_id, acodec, best_audio.abr_kbps),
                    sample_rate_hz=None,
                ),
                height=height,
                fps_int=fps_int,
                vcodec=vcodec,
                estimated_bytes=estimated,
            )
        )

    if not built:
        raise ValidationError("Не удалось подобрать форматы.")

    return deduplicate_choices(built)


def deduplicate_choices(choices: list[FormatChoice]) -> list[FormatChoice]:
    buckets: dict[tuple[int, int, str, str], FormatChoice] = {}
    for c in choices:
        key = (c.height, c.fps_int, c.vcodec.value, c.container.value)
        existing = buckets.get(key)
        if existing is None:
            buckets[key] = c
            continue
        # Prefer higher availability (GUARANTEED over RISKY over UNAVAILABLE).
        rank_new = _availability_rank(c.availability)
        rank_old = _availability_rank(existing.availability)
        if rank_new < rank_old:
            buckets[key] = c

    def sort_key(c: FormatChoice) -> tuple[int, int, int, str]:
        # availability order: guaranteed, risky, unavailable
        return (_availability_rank(c.availability), -c.height, -c.fps_int, c.label)

    return sorted(buckets.values(), key=sort_key)


def _availability_rank(av: ChoiceAvailability) -> int:
    if av == ChoiceAvailability.GUARANTEED:
        return 0
    if av == ChoiceAvailability.RISKY:
        return 1
    return 2
