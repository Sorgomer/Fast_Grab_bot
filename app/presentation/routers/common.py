from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start", "help"))
async def start_handler(message: Message) -> None:
    await message.answer(
        "Пришли ссылку на видео YouTube или VK — я покажу доступные форматы."
    )