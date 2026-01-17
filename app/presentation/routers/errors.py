from __future__ import annotations

import asyncio
import logging

from aiogram import Router
from aiogram.types import ErrorEvent
from app.domain.errors import JobCancelledError

router = Router()
logger = logging.getLogger("tg.errors")


@router.error()
async def error_handler(event: ErrorEvent) -> None:
    exc = event.exception
    if isinstance(exc, (JobCancelledError, asyncio.CancelledError)):
        return
    # ЛОГИРУЕМ реальную причину (traceback попадёт в терминал)
    logger.exception("Unhandled error while processing update", exc_info=event.exception)

    # User-safe fallback (как было)
    if event.update.message:
        await event.update.message.answer(
            "⚒️ Здесь добывают только видео.\n\nПришли ссылку (http:// или https://)\n\nили загляни в /help."
        )
