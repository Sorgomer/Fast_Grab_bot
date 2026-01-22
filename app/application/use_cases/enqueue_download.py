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
from app.constants import (MSG_FORMAT_RISKY_WARNING,
                       MSG_QUEUE_BUSY,
                       MSG_ALREADY_ACTIVE_JOB,
                       MSG_SESSION_EXPIRED,
                       MSG_CHOICE_PROCESS_FAILED,
                       MSG_FORMAT_UNAVAILABLE,
                       )


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
        status_message_id: int,
    ) -> EnqueueResultDTO:
        # per-user active limit (stability)
        if not self._active.try_acquire(user_id):
            return EnqueueResultDTO(accepted=False, message=MSG_ALREADY_ACTIVE_JOB)

        try:
            choice = self._sessions.get_choice(user_id=user_id, version=session_version, choice_id=choice_id)
            url, platform_key = self._sessions.get_session_meta(user_id=user_id, version=session_version)
        except KeyError:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message=MSG_SESSION_EXPIRED)
        except Exception:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message=MSG_CHOICE_PROCESS_FAILED)

        if choice.availability == ChoiceAvailability.UNAVAILABLE:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message=MSG_FORMAT_UNAVAILABLE)

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
            status_message_id=status_message_id,
            platform=Platform(platform_key),
            url=url,
            choice=choice,
            stage=JobStage.QUEUED,
        )

        token = await self._queue.enqueue(job)
        if token is None:
            self._active.release(user_id)
            return EnqueueResultDTO(accepted=False, message=MSG_QUEUE_BUSY)

        self._downloads.register_cancel_token(job.job_id, token)

        if warned:
            return EnqueueResultDTO(
                accepted=True,
                message=MSG_FORMAT_RISKY_WARNING)
        return EnqueueResultDTO(accepted=True, message="")
