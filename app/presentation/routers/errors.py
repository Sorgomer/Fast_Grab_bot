from __future__ import annotations

from aiogram import Router
from aiogram.types import ErrorEvent

router = Router()


@router.error()
async def error_handler(event: ErrorEvent) -> None:
    # User-safe fallback
    if event.update.message:
        await event.update.message.answer("⚒️ Здесь добывают только видео.\n\nПришли ссылку (http:// или https://)\n\nили загляни в /help.")