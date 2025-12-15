from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from yt_dlp import YoutubeDL

from app.domain.errors import DownloadError, ExtractionError
from app.domain.models import CodecFamily, Container, FormatOption, MediaKind, Mp3Selector, VideoSelector


log = logging.getLogger(__name__)


def _codec_family(vcodec: str) -> CodecFamily:
    v = vcodec.lower()
    if v.startswith("avc1") or "h264" in v:
        return CodecFamily.H264
    if v.startswith("vp9") or "vp9" in v:
        return CodecFamily.VP9
    if v.startswith("av01") or "av1" in v:
        return CodecFamily.AV1
    return CodecFamily.OTHER


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass(frozen=True)
class YdlClient:
    temp_dir: Path
    socket_timeout_sec: int
    retries: int

    def _base_opts(self) -> Dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": self.socket_timeout_sec,
            "retries": self.retries,
            "nocheckcertificate": False,
            "ignoreerrors": False,
            "restrictfilenames": True,
        }

    async def extract_info(self, url: str) -> Dict[str, Any]:
        def _extract() -> Dict[str, Any]:
            with YoutubeDL(self._base_opts()) as ydl:
                info = ydl.extract_info(url, download=False)
                if not isinstance(info, dict):
                    raise ExtractionError("Не удалось получить метаданные по ссылке.")
                return info

        try:
            return await asyncio.to_thread(_extract)
        except ExtractionError:
            raise
        except Exception as e:
            log.exception("yt-dlp extract failed")
            raise ExtractionError("Не удалось разобрать ссылку. Возможно, видео недоступно.") from e

    def build_options(self, info: Dict[str, Any]) -> List[FormatOption]:
        formats = info.get("formats")
        extractor = str(info.get("extractor") or info.get("extractor_key") or "").lower()
        is_rutube = "rutube" in extractor
        duration_sec = _safe_int(info.get("duration")) or None
        if not isinstance(formats, list) or not formats:
            raise ExtractionError("Форматы не найдены. Видео может быть недоступно.")

        # Разделяем потоки
        video_only = [
            f for f in formats
            if f.get("vcodec") not in (None, "none")
            and f.get("acodec") in (None, "none")
        ]
        audio_only = [
            f for f in formats
            if f.get("acodec") not in (None, "none")
            and f.get("vcodec") in (None, "none")
        ]

        combined: list[dict[str, Any]] = []

        for f in formats:
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")

            has_video = vcodec not in (None, "none")
            has_audio = acodec not in (None, "none")

            if has_video and has_audio:
                combined.append(f)

        if not audio_only and not (is_rutube and combined):
            raise ExtractionError("Не удалось найти аудиодорожку для сборки файла.")

        best_audio = None
        best_audio_id: str | None = None

        if audio_only:
            best_audio = max(
                audio_only,
                key=lambda f: (
                    _safe_int(f.get("abr")),
                    _safe_int(f.get("tbr")),
                    _safe_int(f.get("filesize", 0)),
                ),
            )
            best_audio_id = str(best_audio.get("format_id"))

        # Группируем видео по разрешению
        from collections import defaultdict
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)

        source_videos = video_only if not is_rutube else (video_only + combined)
        for f in source_videos:
            height = _safe_int(f.get("height"))
            if height > 0:
                grouped[height].append(f)

        codec_priority = {
            CodecFamily.H264: 0,
            CodecFamily.VP9: 1,
            CodecFamily.AV1: 2,
            CodecFamily.OTHER: 3,
        }

        options: list[FormatOption] = []

        for idx, height in enumerate(sorted(grouped.keys(), reverse=True)):
            group = grouped[height]

            def sort_key(f: dict[str, Any]) -> tuple:
                codec = _codec_family(str(f.get("vcodec") or ""))
                return (
                    codec_priority.get(codec, 9),
                    -_safe_int(f.get("fps")),
                    -_safe_int(f.get("tbr")),
                    -_safe_int(f.get("filesize", 0)),
                )

            best_video = sorted(group, key=sort_key)[0]
            ext = str(best_video.get("ext") or "").lower()
            if ext == "mp4":
                container = Container.MP4
            elif ext == "mkv":
                container = Container.MKV
            else:
                continue  # неподдерживаемый контейнер — не показываем

            filesize = (
                best_video.get("filesize")
                or best_video.get("filesize_approx")
            )
            filesize = _safe_int(filesize) or None

            if height == 2160:
                label = "🎥 2160p (4K)"
            elif height == 1440:
                label = "🎥 1440p (2K)"
            elif height == 1080:
                label = "🎥 1080p (Full HD)"
            elif height == 720:
                label = "🎥 720p (HD)"
            else:
                label = f"🎥 {height}p"

            options.append(
                FormatOption(
                    option_id=f"opt_{idx}",
                    kind=MediaKind.VIDEO,
                    label=label,
                    video=VideoSelector(
                        video_format_id=str(best_video.get("format_id")),
                        audio_format_id=None if (is_rutube and best_video in combined) else best_audio_id,
                        height=height,
                        fps=_safe_int(best_video.get("fps")),
                        codec=_codec_family(str(best_video.get("vcodec") or "")),
                    ),
                    mp3=None,

                    container=container,
                    estimated_filesize=filesize,
                    duration_sec=duration_sec,
                )
            )

        # MP3 (only if audio-only is available)
        if best_audio is not None and best_audio_id is not None:
            abr = _safe_int(best_audio.get("abr"), default=128)
            options.append(
                FormatOption(
                    option_id="mp3",
                    kind=MediaKind.MP3,
                    label=f"MP3 (~{abr} kbps)",
                    video=None,
                    mp3=Mp3Selector(
                        audio_format_id=best_audio_id,
                        bitrate_kbps=max(64, min(320, abr)),
                    ),
                    container=Container.MP3,
                    estimated_filesize=_safe_int(best_audio.get("filesize")) or None,
                    duration_sec=duration_sec,
                )
            )

        return options

    def _video_label(self, height: int, fps: int, codec: CodecFamily) -> str:
        fps_part = f"{fps}fps" if fps > 0 else ""
        codec_part = codec.value.upper()
        return " ".join([p for p in [f"{height}p", fps_part, codec_part] if p])

    def _option_id(self, kind: MediaKind, height: int, fps: int, codec: CodecFamily) -> str:
        if kind == MediaKind.VIDEO:
            return f"v:{height}:{fps}:{codec.value}"
        return kind.value


    async def dump_info_json(self, info: Dict[str, Any], out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(info, ensure_ascii=False)
        await asyncio.to_thread(out_path.write_text, data, "utf-8")