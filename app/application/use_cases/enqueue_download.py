from __future__ import annotations

import uuid

from app.application.dto import EnqueueResultDTO
from app.domain.models import Job, JobStage, JobId, UserId, ChatId, Platform
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
    ) -> None:
        self._sessions = sessions
        self._queue = queue
        self._downloads = downloads

    async def execute(
        self,
        *,
        user_id: int,
        chat_id: int,
        session_version: int,
        choice_id: str,
    ) -> EnqueueResultDTO:
        try:
            choice = self._sessions.get_choice(user_id=user_id, version=session_version, choice_id=choice_id)
            url, platform_key = self._sessions.get_session_meta(user_id=user_id, version=session_version)
        except KeyError:
            return EnqueueResultDTO(accepted=False, message="Эта ссылка устарела. Пришли новую.")

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
            return EnqueueResultDTO(accepted=False, message="Очередь занята. Попробуй позже.")

        self._downloads.register_cancel_token(job.job_id, token)
        return EnqueueResultDTO(accepted=True, message="Принято. Начинаю.")