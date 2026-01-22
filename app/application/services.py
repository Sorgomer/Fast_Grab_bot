from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

from app.domain.models import Job, JobId, Container
from app.infrastructure.active_jobs import ActiveJobsRegistry
from app.infrastructure.temp_storage import TempStorage
from app.infrastructure.telegram_sender import TelegramSender, TelegramSenderError
from app.application.ports.status_animator import StatusAnimatorPort
from app.constants import (
    UX_MINE_ENTER,
    UX_MINE_DOWNLOAD_FRAMES,
    UX_MINE_PROBE,
    UX_MINE_CLEAN,
    UX_MINE_UPLOAD_FRAMES,
    UX_MINE_DONE,
    UX_MINE_CANCELLED,
    UX_MINE_SEND_FAILED,
    UX_MINE_TRY_LATER,
)
from app.infrastructure.yt import YdlClient, YdlError
from app.infrastructure.ffmpeg import FfmpegMerger, FfmpegError, FfprobeClient, FfprobeError
from app.infrastructure.ffmpeg.ffmpeg import MergeInputs
from app.domain.errors import JobCancelledError


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
        status_animator: StatusAnimatorPort,
        active_jobs: ActiveJobsRegistry,
        tg_hard_limit_bytes: int,
    ) -> None:
        self._temp = temp_storage
        self._ydl = ydl
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._sender = telegram_sender
        self._anim = status_animator
        self._active = active_jobs
        self._tg_hard_limit_bytes = tg_hard_limit_bytes
        self._logger = logging.getLogger("download_service")
        self._cancel_tokens: Dict[JobId, asyncio.Event] = {}
        self._active_job_by_user: Dict[int, JobId] = {}

    def register_cancel_token(self, job_id: JobId, token: asyncio.Event, user_id: int | None = None) -> None:
        # Backward compatible: some call sites may not pass user_id.
        self._cancel_tokens[job_id] = token
        if user_id is not None:
            self._active_job_by_user[user_id] = job_id

    def cancel_by_user(self, user_id: int) -> bool:
        job_id = self._active_job_by_user.get(user_id)
        if job_id is None:
            return False
        cancelled = self.cancel(job_id)
        if cancelled:
            # best-effort cleanup of mapping
            self._active_job_by_user.pop(user_id, None)
        return cancelled

    def cancel(self, job_id: JobId) -> bool:
        """Cancel a queued/running job.

        Returns True if the job was known and cancellation signal was delivered.
        Always removes the token from registry to avoid memory leaks.
        """
        token = self._cancel_tokens.pop(job_id, None)
        if token is None:
            return False
        token.set()
        return True

    @staticmethod
    def _raise_if_cancelled(cancel_event: asyncio.Event) -> None:
        if cancel_event.is_set():
            raise JobCancelledError()

    async def handle_job(self, job: Job, cancel_event: asyncio.Event) -> None:
        chat_id = int(job.chat_id)
        handle = self._anim.attach(chat_id=chat_id, message_id=int(job.status_message_id))

        # Allow `/cancel` by user_id even if token registration happened without user_id.
        self._active_job_by_user[int(job.user_id)] = job.job_id
        self._cancel_tokens.setdefault(job.job_id, cancel_event)

        # UX: pause after acceptance before starting the mining loop.
        await asyncio.sleep(1.5)
        await self._anim.start_loop(handle, frames=UX_MINE_DOWNLOAD_FRAMES)

        workdir: Path | None = None
        try:
            self._raise_if_cancelled(cancel_event)

            workdir = self._temp.allocate(str(job.job_id))

            video_fmt_id = job.choice.video.fmt.extractor_format_id
            audio_fmt_id = job.choice.audio.fmt.extractor_format_id

            if video_fmt_id == audio_fmt_id:
                # Muxed/progressive stream (video+audio in a single file). Common for RuTube.
                muxed_file = await self._ydl.download_stream(
                    url=job.url,
                    extractor_format_id=video_fmt_id,
                    out_path=workdir / "muxed.stream",
                    cancel_event=cancel_event,
                )
                self._raise_if_cancelled(cancel_event)

                v_file = muxed_file
                a_file = muxed_file
            else:
                v_file = await self._ydl.download_stream(
                    url=job.url,
                    extractor_format_id=video_fmt_id,
                    out_path=workdir / "video.stream",
                    cancel_event=cancel_event,
                )
                self._raise_if_cancelled(cancel_event)

                a_file = await self._ydl.download_stream(
                    url=job.url,
                    extractor_format_id=audio_fmt_id,
                    out_path=workdir / "audio.stream",
                    cancel_event=cancel_event,
                )
                self._raise_if_cancelled(cancel_event)

            await self._anim.stop_loop(handle)
            await self._anim.set_text(handle, UX_MINE_CLEAN)
            out_path = workdir / f"output.{job.choice.ext}"
            merged = await self._ffmpeg.merge(
                MergeInputs(
                    video_path=v_file,
                    audio_path=a_file,
                    output_path=out_path,
                    container=job.choice.container,
                ),
                cancel_event=cancel_event,
            )

            await self._anim.set_text(handle, UX_MINE_PROBE)
            probe = await self._ffprobe.probe(merged, cancel_event=cancel_event)

            self._pre_send_checks(job=job, output_path=merged, probe=probe)

            await self._anim.start_loop(handle, frames=UX_MINE_UPLOAD_FRAMES)
            await self._sender.send_media_best_effort(chat_id, merged)

            await self._anim.stop_loop(handle)
            await self._anim.finish(handle, text=UX_MINE_DONE)

        except JobCancelledError:
            await self._anim.stop_loop(handle)
            # удаляем статус-сообщение, а не заменяем текстом
            await self._sender.delete_status(chat_id=handle.chat_id, message_id=handle.message_id)
        except (YdlError, FfmpegError, FfprobeError):
            self._logger.exception("job failed: %s", job.job_id)
            await self._anim.stop_loop(handle)
            await self._anim.fail(handle, text=UX_MINE_TRY_LATER)
        except TelegramSenderError as exc:
            self._logger.exception("job failed: %s", job.job_id)
            await self._anim.stop_loop(handle)
            await self._anim.fail(handle, text=f"{UX_MINE_SEND_FAILED}\n\nПричина: {exc}")
        except Exception:
            self._logger.exception("job failed: %s", job.job_id)
            await self._anim.stop_loop(handle)
            await self._anim.fail(handle, text=UX_MINE_TRY_LATER)
        finally:
            # Always release per-user active job slot
            self._active.release(int(job.user_id))
            self._cancel_tokens.pop(job.job_id, None)
            # Drop per-user mapping for this job if present
            uid = int(job.user_id)
            if self._active_job_by_user.get(uid) == job.job_id:
                self._active_job_by_user.pop(uid, None)
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
