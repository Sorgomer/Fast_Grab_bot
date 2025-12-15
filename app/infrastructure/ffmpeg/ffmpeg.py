from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import MergeError
from app.domain.models import Container


log = logging.getLogger(__name__)


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.warning("ffmpeg failed: %s", (stderr or b"").decode("utf-8", errors="ignore")[:2000])
        raise MergeError("Не удалось обработать медиафайл (ffmpeg).")


@dataclass(frozen=True)
class Ffmpeg:
    ffmpeg_path: str

    async def merge_av(self, video_path: Path, audio_path: Path, out_path: Path, container: Container) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # stream copy when possible, but still do merge via ffmpeg (mandatory)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            str(out_path.with_suffix(f".{container.ext}")),
        ]
        await _run(cmd)

    async def to_mp3(self, audio_path: Path, out_path: Path, bitrate_kbps: int) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(audio_path),
            "-vn",
            "-b:a",
            f"{bitrate_kbps}k",
            str(out_path.with_suffix(".mp3")),
        ]
        await _run(cmd)