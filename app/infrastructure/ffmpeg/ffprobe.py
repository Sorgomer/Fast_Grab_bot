
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
    format_name: str | None


class FfprobeClient:
    """
    Async wrapper around ffprobe.
    """

    async def probe(self, file_path: Path) -> ProbeResult:
        return await asyncio.to_thread(self._probe_sync, file_path)

    def _probe_sync(self, file_path: Path) -> ProbeResult:
        if not file_path.exists():
            raise FfprobeError("file does not exist")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-print_format", "json",
            str(file_path),
        ]
        FFPROBE_TIMEOUT_SEC = 20  # 20 секунд на probe

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired as exc:
            # stderr может быть полезен для диагностики
            stderr = (exc.stderr or "").strip() if hasattr(exc, "stderr") else ""
            raise FfprobeError(f"ffprobe timed out after {FFPROBE_TIMEOUT_SEC}s; stderr={stderr}") from exc

        if result.returncode != 0:
            raise FfprobeError("ffprobe failed")

        try:
            data = json.loads(result.stdout)
        except Exception as exc:
            raise FfprobeError("ffprobe output parse failed") from exc

        streams = data.get("streams")
        if not isinstance(streams, list):
            raise FfprobeError("ffprobe did not return streams")

        has_video = any(isinstance(s, dict) and s.get("codec_type") == "video" for s in streams)
        has_audio = any(isinstance(s, dict) and s.get("codec_type") == "audio" for s in streams)

        duration_sec: float | None = None
        format_name: str | None = None
        fmt = data.get("format")
        if isinstance(fmt, dict):
            if isinstance(fmt.get("format_name"), str):
                format_name = fmt.get("format_name")
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
            format_name=format_name,
        )
