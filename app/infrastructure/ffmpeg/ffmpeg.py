from __future__ import annotations

import asyncio
import logging
from asyncio.subprocess import PIPE, Process
from app.domain.errors import JobCancelledError
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

    async def merge(self, inp: MergeInputs, *, cancel_event: asyncio.Event | None = None) -> Path:
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

        if inp.container == Container.MP4:
            cmd += ["-movflags", "+faststart"]

        cmd += [str(inp.output_path)]

        FFMPEG_TIMEOUT_SEC = 900
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)

        async def _terminate(p: Process) -> None:
            if p.returncode is not None:
                return
            try:
                p.terminate()
            except ProcessLookupError:
                return
            try:
                await asyncio.wait_for(p.wait(), timeout=5)
                return
            except asyncio.TimeoutError:
                pass
            try:
                p.kill()
            except ProcessLookupError:
                return
            await p.wait()

        comm_task = asyncio.create_task(proc.communicate())
        cancel_task: asyncio.Task[None] | None = None
        if cancel_event is not None:
            cancel_task = asyncio.create_task(cancel_event.wait())

        try:
            wait_set: set[asyncio.Task[object]] = {comm_task}
            if cancel_task is not None:
                wait_set.add(cancel_task)  # type: ignore[arg-type]

            done, _ = await asyncio.wait(
                wait_set,
                timeout=FFMPEG_TIMEOUT_SEC,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if not done:
                await _terminate(proc)
                self._logger.error(
                    "ffmpeg timeout after %ss. cmd=%s",
                    FFMPEG_TIMEOUT_SEC,
                    " ".join(cmd),
                )
                raise FfmpegError(f"ffmpeg timed out after {FFMPEG_TIMEOUT_SEC}s")

            if cancel_task is not None and cancel_task in done:
                await _terminate(proc)
                raise JobCancelledError()

            stdout_b, stderr_b = await comm_task
        finally:
            if cancel_task is not None:
                cancel_task.cancel()

        if proc.returncode != 0:
            self._logger.error("ffmpeg stderr: %s", (stderr_b or b"").decode(errors="ignore").strip())
            raise FfmpegError("ffmpeg merge failed")

        if not inp.output_path.exists() or inp.output_path.stat().st_size <= 0:
            raise FfmpegError("ffmpeg produced empty output")

        return inp.output_path