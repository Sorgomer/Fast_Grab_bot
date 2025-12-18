from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.domain.models import Job


JobHandler = Callable[[Job, asyncio.Event], Awaitable[None]]


@dataclass(slots=True)
class _QueueItem:
    job: Job
    cancel_event: asyncio.Event


class DownloadQueue:
    """
    Bounded async queue with worker pool and cancellation.
    """

    def __init__(self, *, maxsize: int, workers: int, handler: JobHandler) -> None:
        self._queue: asyncio.Queue[_QueueItem] = asyncio.Queue(maxsize=maxsize)
        self._workers = workers
        self._handler = handler
        self._tasks: list[asyncio.Task[None]] = []
        self._logger = logging.getLogger("download_queue")

    async def start(self) -> None:
        for i in range(self._workers):
            task = asyncio.create_task(self._worker(i), name=f"worker-{i}")
            self._tasks.append(task)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def enqueue(self, job: Job) -> asyncio.Event | None:
        if self._queue.full():
            return None
        cancel_event = asyncio.Event()
        await self._queue.put(_QueueItem(job=job, cancel_event=cancel_event))
        return cancel_event

    async def _worker(self, idx: int) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item.cancel_event.is_set():
                    continue
                await self._handler(item.job, item.cancel_event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("job failed: %s", item.job.job_id)
            finally:
                self._queue.task_done()