from __future__ import annotations

from app.application.dto import CancelResultDTO
from app.application.services import DownloadService
from app.domain.models import JobId
from app.constants import UX_MINE_CANCELLED, UX_MINE_CANCEL_NOTHING


class CancelDownloadUseCase:
    def __init__(self, *, downloads: DownloadService) -> None:
        self._downloads = downloads

    async def execute(self, *, user_id: int, job_id: str | None = None) -> CancelResultDTO:
        if job_id:
            cancelled = self._downloads.cancel(JobId(job_id))
        else:
            cancelled = self._downloads.cancel_by_user(user_id)

        if cancelled:
            return CancelResultDTO(cancelled=True, message=UX_MINE_CANCELLED)
        return CancelResultDTO(cancelled=False, message=UX_MINE_CANCEL_NOTHING)