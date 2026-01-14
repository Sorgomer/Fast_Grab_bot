from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start", "help"))
async def start_handler(message: Message) -> None:
    await message.answer(
        "⛏️👷Я готов спуститься в шахту интернета.\nСкинь ссылку — добуду видео."
    )


@router.message(F.text.startswith("/") & ~F.text.regexp(r"^/(start|help)(?:@\w+)?(?:\s|$)"))
async def unknown_command_handler(message: Message) -> None:
    await message.answer("⚒️ Здесь добывают только видео.\n\nПришли ссылку (http:// или https://)\n\nили загляни в /help."
    )