from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from app.infrastructure.yt.ydl_process import YdlProcessRunner, YdlProcessSpec

from app.domain.errors import QueueFullError
from app.domain.models import DownloadJob


log = logging.getLogger(__name__)

JobHandler = Callable[[DownloadJob], Awaitable[None]]


@dataclass
class DownloadQueue:
    maxsize: int
    workers: int
    handler: JobHandler

    def __post_init__(self) -> None:
        self._queue: asyncio.Queue[DownloadJob] = asyncio.Queue(maxsize=self.maxsize)
        self._tasks: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()
        self._active_runners: set[YdlProcessRunner] = set()

    def try_enqueue(self, job: DownloadJob) -> None:
        if self._queue.full():
            raise QueueFullError("Очередь занята. Попробуйте чуть позже.")
        self._queue.put_nowait(job)

    async def start(self) -> None:
        self._stop_event.clear()
        for idx in range(self.workers):
            task = asyncio.create_task(self._worker_loop(idx), name=f"dl-worker-{idx}")
            self._tasks.append(task)
        log.info("DownloadQueue started with %d workers", self.workers)

    async def stop(self) -> None:
        self._stop_event.set()
        for _ in self._tasks:
            self._queue.put_nowait(_poison())
        await self._terminate_active_runners()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        log.info("DownloadQueue stopped")
    
    async def _terminate_active_runners(self) -> None:
        runners = list(self._active_runners)
        if not runners:
            return

        await asyncio.gather(
            *(r.terminate(timeout=3.0) for r in runners),
            return_exceptions=True,
        )

    async def _worker_loop(self, idx: int) -> None:
        while not self._stop_event.is_set():
            job = await self._queue.get()
            try:
                if job.url == "__POISON__":
                    return
                await self.handler(job)
            except Exception:
                log.exception("Worker %d failed on job", idx)
            finally:
                self._queue.task_done()


def _poison() -> DownloadJob:
    from app.domain.models import (
        ChatId,
        MessageId,
        Platform,
        UserId,
        FormatOption,
        MediaKind,
        Container,
    )

    return DownloadJob(
        chat_id=ChatId(0),
        user_id=UserId(0),
        url="__POISON__",
        platform=Platform.YOUTUBE,
        option=FormatOption(
            option_id="poison", 
            kind=MediaKind.VIDEO, 
            label="poison", 
            video=None, 
            mp3=None,
            container=Container.MP4,
            estimated_filesize=None,
            duration_sec=None,
        ),
        status_message_id=MessageId(0),
    )