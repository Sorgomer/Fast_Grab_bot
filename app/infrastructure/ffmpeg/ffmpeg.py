from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.domain.models import Container


class FfmpegError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MergeInputs:
    video_path: Path
    audio_path: Path
    output_path: Path
    container: Container


class FfmpegMerger:
    """
    Responsible only for merging (muxing) downloaded video+audio into a single container.
    No validation here (validation is ffprobe).
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("ffmpeg")

    async def merge(self, inp: MergeInputs) -> Path:
        return await asyncio.to_thread(self._merge_sync, inp)

    def _merge_sync(self, inp: MergeInputs) -> Path:
        if not inp.video_path.exists():
            raise FfmpegError("video input not found")
        if not inp.audio_path.exists():
            raise FfmpegError("audio input not found")

        inp.output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(inp.video_path),
            "-i", str(inp.audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "copy",
        ]

        # Make MP4 more stream-friendly when possible
        if inp.container == Container.MP4:
            cmd += ["-movflags", "+faststart"]

        cmd += [str(inp.output_path)]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            self._logger.error("ffmpeg stderr: %s", (proc.stderr or "").strip())
            raise FfmpegError("ffmpeg merge failed")

        if not inp.output_path.exists() or inp.output_path.stat().st_size <= 0:
            raise FfmpegError("ffmpeg produced empty output")

        return inp.output_path