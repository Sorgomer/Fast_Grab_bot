
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


def build_label(*, height: int, availability: ChoiceAvailability) -> str:
    return f"{_mark(availability)} {height}p"


def _choice_rank(c: FormatChoice) -> tuple[int, int, int, int, int]:
    """
    Чем МЕНЬШЕ tuple — тем формат ЛУЧШЕ.
    """
    availability_rank = _availability_rank(c.availability)

    container_rank = 0 if c.container == Container.MP4 else 1

    codec_rank = {
        VideoCodec.H264: 0,
        VideoCodec.H265: 1,
        VideoCodec.VP9: 2,
        VideoCodec.AV1: 3,
    }.get(c.vcodec, 9)

    fps_rank = -c.fps_int

    size_rank = c.estimated_bytes if c.estimated_bytes is not None else 10**18

    return (
        availability_rank,
        container_rank,
        codec_rank,
        fps_rank,
        size_rank,
    )

def build_format_choices(
    *,
    platform_key: str,
    raw_formats: list[RawExtractorFormat],
    tg_limits: TelegramLimits,
) -> list[FormatChoice]:
    videos = [f for f in raw_formats if f.is_video and not f.is_audio]
    audios = [f for f in raw_formats if f.is_audio and not f.is_video]
    muxed = [f for f in raw_formats if f.is_video and f.is_audio]

    # If extractor provides muxed (progressive) formats (common on RuTube),
    # fall back to muxed choices when we cannot form video-only + audio-only pairs.
    if muxed and (not videos or not audios):
        built: list[FormatChoice] = []
        for m in muxed:
            height = int(m.height or 0)
            if height <= 0:
                continue

            fps_int = _fps_int(m.fps)
            vcodec = m.vcodec
            acodec = m.acodec
            container = choose_container(vcodec=vcodec, acodec=acodec)

            estimated = int(m.filesize_bytes * 1.01) if m.filesize_bytes is not None else None
            boost = _risk_boost(height=height, fps_int=fps_int, vcodec=vcodec, container=container)
            availability = _availability(estimated=estimated, limits=tg_limits, risk_boost=boost)

            choice_id = _stable_choice_id(platform_key, height, fps_int, vcodec, container)
            label = build_label(height=height, availability=availability)

            built.append(
                FormatChoice(
                    choice_id=choice_id,
                    label=label,
                    container=container,
                    availability=availability,
                    video=VideoSpec(
                        fmt=StreamSpec(m.extractor_format_id, vcodec, m.vbr_kbps),
                        width=m.width,
                        height=m.height,
                        fps=m.fps,
                    ),
                    audio=AudioSpec(
                        fmt=StreamSpec(m.extractor_format_id, acodec, m.abr_kbps),
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
        label = build_label(height=height, availability=availability)

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
    """
    1 height = 1 button (best format).
    """
    best_by_height: dict[int, FormatChoice] = {}

    for c in choices:
        cur = best_by_height.get(c.height)
        if cur is None or _choice_rank(c) < _choice_rank(cur):
            best_by_height[c.height] = c

    # пере-лейблим после выбора победителя
    final: list[FormatChoice] = []

    for c in best_by_height.values():
        if c.availability == ChoiceAvailability.UNAVAILABLE:
            continue  # ❌ не показываем вообще

        final.append(
            FormatChoice(
                choice_id=c.choice_id,
                label=build_label(height=c.height, availability=c.availability),
                container=c.container,
                availability=c.availability,
                video=c.video,
                audio=c.audio,
                height=c.height,
                fps_int=c.fps_int,
                vcodec=c.vcodec,
                estimated_bytes=c.estimated_bytes,
            )
        )

    # сортировка для UI
    return sorted(
    final,
    key=lambda c: -c.height,
    )


def _availability_rank(av: ChoiceAvailability) -> int:
    if av == ChoiceAvailability.GUARANTEED:
        return 0
    if av == ChoiceAvailability.RISKY:
        return 1
    return 2
