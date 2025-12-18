
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Dict

from app.domain.models import Job, JobId, Container
from app.infrastructure.active_jobs import ActiveJobsRegistry
from app.infrastructure.temp_storage import TempStorage
from app.infrastructure.telegram_sender import TelegramSender, TelegramSenderError
from app.infrastructure.yt import YdlClient, YdlError
from app.infrastructure.ffmpeg import FfmpegMerger, FfmpegError, FfprobeClient, FfprobeError
from app.infrastructure.ffmpeg.ffmpeg import MergeInputs


class DownloadService:
    """
    Orchestrates media pipeline for a queued job:
      download video+audio -> ffmpeg merge -> ffprobe validate -> send to Telegram.

    IMPORTANT:
      - Telegram delivery for big files is best-effort (network/telegram side).
      - Pre-send checks are mandatory to avoid broken files.
    """

    def __init__(
        self,
        *,
        temp_storage: TempStorage,
        ydl: YdlClient,
        ffmpeg: FfmpegMerger,
        ffprobe: FfprobeClient,
        telegram_sender: TelegramSender,
        active_jobs: ActiveJobsRegistry,
        tg_hard_limit_bytes: int,
    ) -> None:
        self._temp = temp_storage
        self._ydl = ydl
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._sender = telegram_sender
        self._active = active_jobs
        self._tg_hard_limit_bytes = tg_hard_limit_bytes
        self._logger = logging.getLogger("download_service")
        self._cancel_tokens: Dict[JobId, asyncio.Event] = {}

    def register_cancel_token(self, job_id: JobId, token: asyncio.Event) -> None:
        self._cancel_tokens[job_id] = token

    def cancel(self, job_id: JobId) -> None:
        token = self._cancel_tokens.get(job_id)
        if token is not None:
            token.set()

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
            out_path = workdir / f"output.{job.choice.ext}"
            merged = await self._ffmpeg.merge(
                MergeInputs(
                    video_path=v_file,
                    audio_path=a_file,
                    output_path=out_path,
                    container=job.choice.container,
                )
            )

            await self._sender.edit_status(chat_id, status_id, "Проверка ffprobe…")
            probe = await self._ffprobe.probe(merged)

            self._pre_send_checks(job=job, output_path=merged, probe=probe)

            await self._sender.edit_status(chat_id, status_id, "Отправка…")
            await self._sender.send_media_best_effort(chat_id, merged)

            await self._sender.edit_status(chat_id, status_id, "Готово ✅")

        except (YdlError, FfmpegError, FfprobeError, TelegramSenderError):
            self._logger.exception("job failed: %s", job.job_id)
            await self._sender.edit_status(chat_id, status_id, "Не удалось отправить. Попробуй другой формат.")
        except Exception:
            self._logger.exception("job failed: %s", job.job_id)
            await self._sender.edit_status(chat_id, status_id, "Ошибка обработки. Попробуй позже.")
        finally:
            # Always release per-user active job slot
            self._active.release(int(job.user_id))
            if workdir is not None:
                self._temp.cleanup(str(job.job_id))

    def _pre_send_checks(self, *, job: Job, output_path: Path, probe) -> None:
        # exists
        if not output_path.exists():
            raise TelegramSenderError("Файл не найден перед отправкой.")
        # size > 0
        size = output_path.stat().st_size
        if size <= 0:
            raise TelegramSenderError("Файл пустой.")
        # size <= hard limit
        if size > self._tg_hard_limit_bytes:
            raise TelegramSenderError("Файл превышает лимит Telegram для ботов (≈2ГБ).")
        # expected container by extension + ffprobe format
        expected_ext = f".{job.choice.ext}"
        if output_path.suffix.lower() != expected_ext:
            raise TelegramSenderError("Неожиданный контейнер файла.")
        if probe.format_name is not None:
            fmt = probe.format_name.lower()
            if job.choice.container == Container.MP4:
                if "mp4" not in fmt and "mov" not in fmt:
                    raise TelegramSenderError("Контейнер файла не соответствует ожидаемому (mp4).")
            if job.choice.container == Container.MKV:
                if "matroska" not in fmt and "mkv" not in fmt:
                    raise TelegramSenderError("Контейнер файла не соответствует ожидаемому (mkv).")
        # streams exist
        if not probe.has_video or not probe.has_audio:
            raise TelegramSenderError("Файл повреждён (нет видео/аудио).")
        # duration sanity
        if probe.duration_sec is not None and probe.duration_sec <= 0:
            raise TelegramSenderError("Файл повреждён (длительность 0).")
