from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.domain.errors import DownloadError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class YdlProcessSpec:
    """
    Immutable spec for running yt-dlp as subprocess.
    """
    executable: str
    args: Sequence[str]
    workdir: Path


class YdlProcessRunner:
    """
    Runs yt-dlp as an asyncio subprocess and allows controlled termination.
    """

    def __init__(self, spec: YdlProcessSpec) -> None:
        self._spec = spec
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("yt-dlp process already started")

        log.info("Starting yt-dlp subprocess")
        self._process = await asyncio.create_subprocess_exec(
            self._spec.executable,
            *self._spec.args,
            cwd=str(self._spec.workdir) if self._spec.workdir is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def wait(self) -> None:
        if self._process is None:
            raise RuntimeError("yt-dlp process not started")

        stdout, stderr = await self._process.communicate()

        if self._process.returncode != 0:
            err = stderr.decode(errors="ignore").strip()
            log.error("yt-dlp failed: %s", err)
            raise DownloadError("Ошибка при скачивании видео")

    async def terminate(self, timeout: float = 5.0) -> None:
        if self._process is None:
            return

        if self._process.returncode is not None:
            return

        log.info("Terminating yt-dlp subprocess")
        self._process.terminate()

        try:
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("yt-dlp did not terminate in time, killing")
            self._process.kill()
            await self._process.wait()