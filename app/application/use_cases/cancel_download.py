from __future__ import annotations

from app.application.dto import CancelResultDTO
from app.application.services import DownloadService
from app.domain.models import JobId


class CancelDownloadUseCase:
    def __init__(self, *, downloads: DownloadService) -> None:
        self._downloads = downloads

    async def execute(self, *, job_id: str) -> CancelResultDTO:
        cancelled = self._downloads.cancel(JobId(job_id))
        if cancelled:
            return CancelResultDTO(cancelled=True, message="Ок, отменил.")
        return CancelResultDTO(cancelled=False, message="Не получилось отменить (возможно, уже завершено).")