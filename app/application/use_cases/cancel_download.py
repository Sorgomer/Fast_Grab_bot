from __future__ import annotations

from app.application.dto import CancelResultDTO
from app.application.services import DownloadService
from app.domain.models import JobId


class CancelDownloadUseCase:
    def __init__(self, *, downloads: DownloadService) -> None:
        self._downloads = downloads

    async def execute(self, *, user_id: int, job_id: str | None = None) -> CancelResultDTO:
        if job_id:
            cancelled = self._downloads.cancel(JobId(job_id))
        else:
            cancelled = self._downloads.cancel_by_user(user_id)

        if cancelled:
            return CancelResultDTO(cancelled=True, message="⛏️⛔ Стоп-машина: добычу остановил.")
        return CancelResultDTO(cancelled=False, message="⚒️ Нечего останавливать: активной добычи не вижу.")