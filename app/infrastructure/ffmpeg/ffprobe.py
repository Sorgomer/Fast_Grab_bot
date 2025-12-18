from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FfprobeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProbeResult:
    has_video: bool
    has_audio: bool
    duration_sec: float | None
    size_bytes: int


class FfprobeClient:
    """
    ffprobe wrapper for strict validation before sending to user.
    """

    async def probe(self, file_path: Path) -> ProbeResult:
        return await asyncio.to_thread(self._probe_sync, file_path)

    def _probe_sync(self, file_path: Path) -> ProbeResult:
        if not file_path.exists():
            raise FfprobeError("file not found")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_streams",
            "-show_format",
            "-print_format", "json",
            str(file_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise FfprobeError("ffprobe failed")

        try:
            data = json.loads(proc.stdout)
        except Exception as exc:
            raise FfprobeError("ffprobe returned invalid json") from exc

        streams = data.get("streams")
        fmt = data.get("format")

        has_video = False
        has_audio = False
        if isinstance(streams, list):
            for s in streams:
                if not isinstance(s, dict):
                    continue
                stype = s.get("codec_type")
                if stype == "video":
                    has_video = True
                elif stype == "audio":
                    has_audio = True

        duration_sec: float | None = None
        if isinstance(fmt, dict):
            d = fmt.get("duration")
            try:
                if d is not None:
                    duration_sec = float(d)
            except Exception:
                duration_sec = None

        size = file_path.stat().st_size
        return ProbeResult(
            has_video=has_video,
            has_audio=has_audio,
            duration_sec=duration_sec,
            size_bytes=size,
        )