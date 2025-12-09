from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Dict, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramNetworkError
from aiogram.types import FSInputFile
from loguru import logger

from app.config.settings import get_settings
from app.services.models import (
    DownloadTask,
    DownloadTaskStatus,
    MediaInfo,
    MediaFormat,
    MediaType,
)
from app.services.platforms import get_downloader
from app.services.rate_limiter import RateLimiter
from app.services.storage import cleanup_task_files
from app.utils.exceptions import (
    DownloadError,
    FileTooLargeError,
    TaskNotFoundError,
    TaskCancelledError,
)
from app.utils.files import get_file_size
from app.utils.text import build_status_message


class DownloadManager:
    def __init__(self, bot: Bot, rate_limiter: RateLimiter):
        self.bot = bot
        self.rate_limiter = rate_limiter
        self.settings = get_settings()
        self.queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.tasks: Dict[str, DownloadTask] = {}
        self.pending_infos: Dict[str, MediaInfo] = {}
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        for i in range(self.settings.max_global_downloads):
            t = asyncio.create_task(self._worker(i), name=f"download-worker-{i}")
            self.workers.append(t)
        logger.info("DownloadManager started with {} workers", len(self.workers))

    async def stop(self) -> None:
        self._stop_event.set()
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("DownloadManager stopped")

    def create_task_id(self) -> str:
        return uuid.uuid4().hex

    def store_media_info(self, task_id: str, info: MediaInfo) -> None:
        self.pending_infos[task_id] = info

    def get_media_info(self, task_id: str) -> MediaInfo:
        if task_id not in self.pending_infos:
            raise TaskNotFoundError("Информация о задаче не найдена")
        return self.pending_infos[task_id]

    async def enqueue(self, task: DownloadTask) -> None:
        if not await self.rate_limiter.can_start_download(task.user_id):
            raise DownloadError(
                "Слишком много одновременно загружаемых файлов. "
                "Дождитесь завершения текущих задач."
            )
        self.tasks[task.id] = task
        await self.rate_limiter.register_download_start(task.user_id)
        await self.queue.put(task)
        logger.info(
            "Task {} enqueued for user {} ({})", task.id, task.user_id, task.format.label
        )

    async def cancel(self, task_id: str, user_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task or task.user_id != user_id:
            raise TaskNotFoundError("Задача не найдена")

        running = self.running_tasks.get(task_id)
        if running:
            running.cancel()
            task.update_status(DownloadTaskStatus.CANCELLED)
            raise TaskCancelledError("Задача отменена")

        # Если в очереди — просто пометится как отмененная и не будет обработана
        task.update_status(DownloadTaskStatus.CANCELLED)
        raise TaskCancelledError("Задача отменена")

    async def _worker(self, worker_id: int) -> None:
        logger.info("Worker {} started", worker_id)
        while not self._stop_event.is_set():
            try:
                task = await self.queue.get()
            except asyncio.CancelledError:
                break

            if task.status == DownloadTaskStatus.CANCELLED:
                self.queue.task_done()
                continue

            async_task = asyncio.create_task(
                self._process_task(task), name=f"task-{task.id}"
            )
            self.running_tasks[task.id] = async_task
            try:
                await async_task
            finally:
                self.running_tasks.pop(task.id, None)
                self.queue.task_done()

        logger.info("Worker {} stopped", worker_id)

    async def _process_task(self, task: DownloadTask) -> None:
        logger.info("Processing task {} for user {}", task.id, task.user_id)
        try:
            await self._edit_status(task, DownloadTaskStatus.PENDING)

            # DOWNLOADING
            task.update_status(DownloadTaskStatus.DOWNLOADING)
            await self._edit_status(task, DownloadTaskStatus.DOWNLOADING)

            downloader = get_downloader(task.platform)
            file_path = await downloader.download(task)
            task.file_path = str(file_path)

            # check size
            size = get_file_size(file_path)
            if size is None:
                raise DownloadError("Файл не найден")

            max_bytes = self.settings.max_file_size_mb * 1024 * 1024
            if size > max_bytes:
                raise FileTooLargeError(
                    "Файл слишком большой и не может быть отправлен через Telegram"
                )

            # PROCESSING
            task.update_status(DownloadTaskStatus.PROCESSING)
            await self._edit_status(task, DownloadTaskStatus.PROCESSING)

            # SENDING
            task.update_status(DownloadTaskStatus.SENDING)
            await self._edit_status(task, DownloadTaskStatus.SENDING)

            await self._send_file(task, Path(file_path))

            task.update_status(DownloadTaskStatus.COMPLETED)
            await self._edit_status(task, DownloadTaskStatus.COMPLETED)

        except FileTooLargeError as e:
            task.update_status(DownloadTaskStatus.FAILED)
            await self._edit_error(task, str(e))
        except DownloadError as e:
            task.update_status(DownloadTaskStatus.FAILED)
            await self._edit_error(task, f"Ошибка загрузки: {e}")
        except TaskCancelledError as e:
            task.update_status(DownloadTaskStatus.CANCELLED)
            await self._edit_error(task, str(e))
        except asyncio.CancelledError:
            task.update_status(DownloadTaskStatus.CANCELLED)
            await self._edit_error(task, "Задача отменена")
            raise
        except Exception as e:
            logger.exception("Unexpected error in task {}: {}", task.id, e)
            task.update_status(DownloadTaskStatus.FAILED)
            await self._edit_error(task, "Произошла непредвиденная ошибка")
        finally:
            await self.rate_limiter.register_download_end(task.user_id)
            if task.file_path:
                cleanup_task_files(task)

    async def _edit_status(self, task: DownloadTask, status: DownloadTaskStatus) -> None:
        text = build_status_message(status, task.format)
        try:
            await self.bot.edit_message_text(
                chat_id=task.chat_id,
                message_id=task.message_id,
                text=text,
            )
        except Exception:
            # игнорируем ошибки редактирования (например, слишком много обновлений)
            pass

    async def _edit_error(self, task: DownloadTask, error: str) -> None:
        try:
            await self.bot.edit_message_text(
                chat_id=task.chat_id,
                message_id=task.message_id,
                text=f"❌ {error}",
            )
        except Exception:
            pass

    async def _send_file(self, task: DownloadTask, path: Path) -> None:
        input_file = FSInputFile(path)
        try:
            if task.format.media_type == MediaType.VIDEO:
                await self._send_with_retry(
                    self.bot.send_video,
                    chat_id=task.chat_id,
                    video=input_file,
                    caption=task.media_info.title,
                )
            else:
                await self._send_with_retry(
                    self.bot.send_audio,
                    chat_id=task.chat_id,
                    audio=input_file,
                    caption=task.media_info.title,
                )
        except FileTooLargeError:
            raise
        except Exception as e:
            logger.exception("Error sending file for task {}: {}", task.id, e)
            raise DownloadError("Не удалось отправить файл")

    async def _send_with_retry(self, func, *args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            return await func(*args, **kwargs)
        except TelegramNetworkError:
            # 502, 504 и т.п.
            await asyncio.sleep(3)
            return await func(*args, **kwargs)