
from __future__ import annotations

import uuid

from app.application.dto import EnqueueResultDTO
from app.domain.models import (
    ChoiceAvailability,
    Job,
    JobStage,
    JobId,
    UserId,
    ChatId,
    Platform,
)
from app.infrastructure.active_jobs import ActiveJobsRegistry
from app.infrastructure.session_store import SessionStore
from app.infrastructure.download_queue import DownloadQueue
from app.application.services import DownloadService


class EnqueueDownloadUseCase:
    def __init__(
        self,
        *,
        sessions: SessionStore,
        queue: DownloadQueue,
        downloads: DownloadService,
        active_jobs: ActiveJobsRegistry,
    ) -> None:
        self._sessions = sessions
        self._queue = queue
        self._downloads = downloads
        self._active = active_jobs

    async def execute(
        self,
        *,
        user_id: int,
        chat_id: int,
        session_version: int,
        choice_id: str,
    ) -> EnqueueResultDTO:
        # per-user active limit (stability)
        if not self._active.try_acquire(user_id):
            return EnqueueResultDTO(accepted=False, message="У тебя уже есть активная загрузка. Дождись завершения или отмени.")

        try:
            choice = self._sessions.get_choice(user_id=user_id, version=session_version, choice_id=choice_id)
            url, platform_key = self._sessions.get_session_meta(user_id=user_id, version=session_version)
        except KeyError:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message="Эта ссылка устарела. Пришли новую.")
        except Exception:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message="Не удалось обработать выбор. Попробуй ещё раз.")

        if choice.availability == ChoiceAvailability.UNAVAILABLE:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message="❌ Этот формат недоступен (превышает лимиты Telegram). Выбери другой.")

        warned = False
        if choice.availability == ChoiceAvailability.RISKY:
            try:
                if not self._sessions.warned_risky_once(user_id=user_id, version=session_version):
                    self._sessions.mark_warned_risky_once(user_id=user_id, version=session_version)
                    warned = True
            except KeyError:
                warned = True

        job = Job(
            job_id=JobId(uuid.uuid4().hex),
            user_id=UserId(user_id),
            chat_id=ChatId(chat_id),
            platform=Platform(platform_key),
            url=url,
            choice=choice,
            stage=JobStage.QUEUED,
        )

        token = await self._queue.enqueue(job)
        if token is None:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message="Очередь занята. Попробуй позже.")

        self._downloads.register_cancel_token(job.job_id, token)

        if warned:
            return EnqueueResultDTO(
                accepted=True,
                message="⚠️ Формат в зоне риска - сделаю все что в моих силах",
            )
        return EnqueueResultDTO(accepted=True, message="Принято. Начинаю.")
