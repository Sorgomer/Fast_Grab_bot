from pathlib import Path
from typing import Any

import yt_dlp

from app.config.settings import get_settings


def build_base_opts(download_dir: Path) -> dict[str, Any]:
    settings = get_settings()
    return {
        "cachedir": False,
        "outtmpl": str(download_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "nocheckcertificate": True,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 5,
        "ffmpeg_location": "ffmpeg",  # предполагаем что ffmpeg в PATH
        "progress_hooks": [],
        "http_headers": {
            "User-Agent": yt_dlp.utils.std_headers["User-Agent"],
        },
    }


def build_extract_opts(download_dir: Path) -> dict[str, Any]:
    opts = build_base_opts(download_dir)
    opts["skip_download"] = True
    return opts


def build_download_opts(
    download_dir: Path,
    format_id: str | None = None,
    audio_only: bool = False,
    to_mp3: bool = False,
) -> dict[str, Any]:
    opts = build_base_opts(download_dir)
    if format_id:
        opts["format"] = format_id

    if audio_only and not to_mp3:
        opts["format"] = "bestaudio/best"

    if to_mp3:
        opts.setdefault("postprocessors", []).append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        )
    return opts