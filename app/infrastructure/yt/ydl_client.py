from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.models import AudioCodec, VideoCodec
from app.domain.policies import RawExtractorFormat

from .ydl_config import YdlConfig


class YdlError(RuntimeError):
    pass


def _map_vcodec(vcodec: str | None) -> VideoCodec:
    if not vcodec or vcodec == "none":
        return VideoCodec.UNKNOWN
    v = vcodec.lower()
    if "avc" in v or "h264" in v:
        return VideoCodec.H264
    if "hevc" in v or "h265" in v:
        return VideoCodec.H265
    if "vp9" in v:
        return VideoCodec.VP9
    if "av01" in v or "av1" in v:
        return VideoCodec.AV1
    return VideoCodec.UNKNOWN


def _map_acodec(acodec: str | None) -> AudioCodec:
    if not acodec or acodec == "none":
        return AudioCodec.UNKNOWN
    a = acodec.lower()
    if "mp4a" in a or "aac" in a:
        return AudioCodec.AAC
    if "opus" in a:
        return AudioCodec.OPUS
    if "vorbis" in a:
        return AudioCodec.VORBIS
    if "mp3" in a:
        return AudioCodec.MP3
    return AudioCodec.UNKNOWN


def _kbps(value: Any) -> int | None:
    try:
        if value is None:
            return None
        v = float(value)
        if v <= 0:
            return None
        return int(round(v))
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class ExtractResult:
    title: str | None
    raw_formats: list[RawExtractorFormat]
    webpage_url: str


class YdlClient:
    """
    yt-dlp wrapper:
      - extract info
      - download a single stream by extractor format id
    No merge, no postprocessors, no container conversions.
    """

    def __init__(self, *, cfg: YdlConfig) -> None:
        self._cfg = cfg
        self._logger = logging.getLogger("ydl")

    async def extract(self, url: str, *, extra_opts: dict[str, Any] | None = None) -> ExtractResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, url, extra_opts),
                timeout=self._cfg.extract_timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise YdlError("Extractor timed out while fetching media info") from exc

    def _extract_sync(
        self,
        url: str,
        extra_opts: dict[str, Any] | None = None,
    ) -> ExtractResult:
        try:
            import yt_dlp  # type: ignore
        except Exception as exc:
            raise YdlError("yt-dlp is not installed") from exc

        ydl_opts: dict[str, Any] = {
            "quiet": self._cfg.quiet,
            "no_warnings": self._cfg.no_warnings,
            "socket_timeout": self._cfg.socket_timeout_sec,
            "retries": self._cfg.retries,
            "restrictfilenames": self._cfg.restrict_filenames,
            "noplaylist": True,
            "skip_download": True,
        }

        if extra_opts:
            ydl_opts.update(extra_opts)
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise YdlError("Failed to extract media info") from exc

        # Some extractors return a dict with entries (playlist). We disallow playlist.
        if isinstance(info, dict) and "entries" in info and info.get("_type") in {"playlist", "multi_video"}:
            raise YdlError("Playlists are not supported")

        if not isinstance(info, dict):
            raise YdlError("Unexpected extractor response type")

        formats = info.get("formats")
        if not isinstance(formats, list):
            raise YdlError("Extractor did not return formats list")

        raw_formats: list[RawExtractorFormat] = []
        for f in formats:
            if not isinstance(f, dict):
                continue

            fmt_id = f.get("format_id")
            if not isinstance(fmt_id, str) or not fmt_id.strip():
                continue

            vcodec = f.get("vcodec")
            acodec = f.get("acodec")

            has_video = isinstance(vcodec, str) and vcodec != "none"
            has_audio = isinstance(acodec, str) and acodec != "none"

            # We want *pure* streams for pairing: video-only and audio-only.
            is_video_only = has_video and not has_audio
            is_audio_only = has_audio and not has_video
            is_muxed = has_video and has_audio

            width = f.get("width")
            height = f.get("height")
            fps = f.get("fps")

            ext = f.get("ext")
            filesize = f.get("filesize") or f.get("filesize_approx")

            # yt-dlp uses tbr/abr/vbr in Kbps-ish
            vbr = _kbps(f.get("vbr") or f.get("tbr"))
            abr = _kbps(f.get("abr") or f.get("tbr"))

            raw_formats.append(
                RawExtractorFormat(
                    extractor_format_id=fmt_id,
                    is_video=is_video_only or is_muxed,
                    is_audio=is_audio_only or is_muxed,
                    width=int(width) if isinstance(width, (int, float)) else None,
                    height=int(height) if isinstance(height, (int, float)) else None,
                    fps=float(fps) if isinstance(fps, (int, float)) else None,
                    vcodec=_map_vcodec(vcodec if isinstance(vcodec, str) else None),
                    acodec=_map_acodec(acodec if isinstance(acodec, str) else None),
                    vbr_kbps=vbr if (is_video_only or is_muxed) else None,
                    abr_kbps=abr if (is_audio_only or is_muxed) else None,
                    ext=ext if isinstance(ext, str) else None,
                    filesize_bytes=int(filesize) if isinstance(filesize, (int, float)) else None,
                )
            )

        title = info.get("title") if isinstance(info.get("title"), str) else None
        webpage_url = info.get("webpage_url") if isinstance(info.get("webpage_url"), str) else url

        # Keep only meaningful formats
        raw_formats = [rf for rf in raw_formats if rf.is_video or rf.is_audio]
        if not raw_formats:
            raise YdlError("No usable formats found")

        return ExtractResult(title=title, raw_formats=raw_formats, webpage_url=webpage_url)

    async def download_stream(self, *, url: str, extractor_format_id: str, out_path: Path) -> Path:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._download_stream_sync, url, extractor_format_id, out_path),
                timeout=self._cfg.download_timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            self._logger.error(
                "yt-dlp download timeout after %ss: url=%s format=%s out=%s",
                self._cfg.download_timeout_sec, url, extractor_format_id, str(out_path),
            )
            raise YdlError(
                f"Downloader timed out after {self._cfg.download_timeout_sec}s while downloading media stream"
            ) from exc

    def _download_stream_sync(self, url: str, extractor_format_id: str, out_path: Path) -> Path:
        try:
            import yt_dlp  # type: ignore
        except Exception as exc:
            raise YdlError("yt-dlp is not installed") from exc

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # IMPORTANT:
        # - no postprocessors
        # - no merge_output_format
        # - we download exactly one stream by format id
        ydl_opts: dict[str, Any] = {
            "quiet": self._cfg.quiet,
            "no_warnings": self._cfg.no_warnings,
            "socket_timeout": self._cfg.socket_timeout_sec,
            "retries": self._cfg.retries,
            "restrictfilenames": self._cfg.restrict_filenames,
            "noplaylist": True,
            "format": extractor_format_id,
            "outtmpl": str(out_path),
            "paths": {"home": str(out_path.parent)},
            "postprocessors": [],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as exc:
            raise YdlError("Failed to download stream") from exc

        # yt-dlp might modify extension depending on stream; ensure we locate the actual file:
        if out_path.exists():
            return out_path

        # Fallback: try any file with same stem
        candidates = sorted(out_path.parent.glob(out_path.name + "*"))
        for c in candidates:
            if c.is_file():
                return c

        raise YdlError("Downloaded file not found on disk")