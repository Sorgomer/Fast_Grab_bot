from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    bot_token: str
    work_dir: Path
    downloads_dir: Path
    temp_dir: Path

    queue_maxsize: int
    workers: int

    ydl_socket_timeout_sec: int
    ydl_retries: int

    ffmpeg_path: str
    ffprobe_path: str

    max_file_mb: int  # Telegram bot API practical limit depends, keep conservative


def build_config(bot_token: str) -> AppConfig:
    base = Path.cwd() / "runtime"
    downloads = base / "downloads"
    temp = base / "temp"
    return AppConfig(
        bot_token=bot_token,
        work_dir=base,
        downloads_dir=downloads,
        temp_dir=temp,
        queue_maxsize=30,
        workers=2,
        ydl_socket_timeout_sec=20,
        ydl_retries=3,
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        max_file_mb=1900,  # keep under 2GB as conservative
    )