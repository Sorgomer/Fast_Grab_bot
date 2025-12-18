from __future__ import annotations

from app.application.dto import EnqueueResultDTO


class RetryDownloadUseCase:
    async def execute(self) -> EnqueueResultDTO:
        return EnqueueResultDTO(
            accepted=False,
            message="Повтор загрузки пока не поддерживается.",
        )