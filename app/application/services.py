from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Dict

from app.domain.models import Job, JobId
from app.infrastructure.temp_storage import TempStorage
from app.infrastructure.telegram_sender import TelegramSender, TelegramSenderError
from app.infrastructure.yt import YdlClient, YdlError
from app.infrastructure.ffmpeg import FfmpegMerger, FfmpegError, FfprobeClient, FfprobeError
from app.infrastructure.ffmpeg.ffmpeg import MergeInputs


class DownloadService:
    def __init__(
        self,
        *,
        temp_storage: TempStorage,
        ydl: YdlClient,
        ffmpeg: FfmpegMerger,
        ffprobe: FfprobeClient,
        telegram_sender: TelegramSender,
    ) -> None:
        self._temp = temp_storage
        self._ydl = ydl
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._sender = telegram_sender
        self._logger = logging.getLogger("download_service")
        self._cancel_tokens: Dict[JobId, asyncio.Event] = {}

    def register_cancel_token(self, job_id: JobId, token: asyncio.Event) -> None:
        self._cancel_tokens[job_id] = token

    def cancel(self, job_id: JobId) -> bool:
        token = self._cancel_tokens.get(job_id)
        if token is None:
            return False
        token.set()
        return True

    async def handle_job(self, job: Job, cancel_event: asyncio.Event) -> None:
        chat_id = int(job.chat_id)
        status_id = await self._sender.send_status(chat_id, "Анализ…")

        workdir: Path | None = None
        try:
            if cancel_event.is_set():
                await self._sender.edit_status(chat_id, status_id, "Отменено.")
                return

            workdir = self._temp.allocate(str(job.job_id))

            await self._sender.edit_status(chat_id, status_id, "Скачивание (видео + аудио)…")
            v_file = await self._ydl.download_stream(
                url=job.url,
                extractor_format_id=job.choice.video.fmt.extractor_format_id,
                out_path=workdir / "video.stream",
            )
            if cancel_event.is_set():
                await self._sender.edit_status(chat_id, status_id, "Отменено.")
                return

            a_file = await self._ydl.download_stream(
                url=job.url,
                extractor_format_id=job.choice.audio.fmt.extractor_format_id,
                out_path=workdir / "audio.stream",
            )
            if cancel_event.is_set():
                await self._sender.edit_status(chat_id, status_id, "Отменено.")
                return

            await self._sender.edit_status(chat_id, status_id, "Склейка ffmpeg…")
            merged = await self._ffmpeg.merge(
                MergeInputs(
                    video_path=v_file,
                    audio_path=a_file,
                    output_path=workdir / f"output.{job.choice.ext}",
                    container=job.choice.container,
                )
            )

            await self._sender.edit_status(chat_id, status_id, "Проверка ffprobe…")
            probe = await self._ffprobe.probe(merged)
            if not probe.has_video or not probe.has_audio:
                raise RuntimeError("invalid streams")
            if probe.size_bytes <= 0:
                raise RuntimeError("empty file")
            if probe.duration_sec is not None and probe.duration_sec <= 0:
                raise RuntimeError("zero duration")

            await self._sender.edit_status(chat_id, status_id, "Отправка…")
            await self._sender.send_video_file(chat_id, merged)

            await self._sender.edit_status(chat_id, status_id, "Готово ✅")

        except (YdlError, FfmpegError, FfprobeError, TelegramSenderError):
            self._logger.exception("job failed: %s", job.job_id)
            await self._sender.edit_status(chat_id, status_id, "Не удалось скачать. Попробуй другую ссылку или формат.")
        except Exception:
            self._logger.exception("job failed: %s", job.job_id)
            await self._sender.edit_status(chat_id, status_id, "Ошибка обработки. Попробуй позже.")
        finally:
            if workdir is not None:
                self._temp.cleanup(str(job.job_id))