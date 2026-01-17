from __future__ import annotations

from app.application.use_cases.cancel_download import CancelDownloadUseCase
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start", "help"))
async def start_handler(message: Message) -> None:
    await message.answer(
        "⛏️👷Я готов спуститься в шахту интернета.\nСкинь ссылку — добуду видео."
    )

@router.message(Command("cancel"))
async def cancel_handler(message: Message, cancel_download: CancelDownloadUseCase) -> None:
    # Optional: `/cancel <job_id>`
    job_id: str | None = None
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            job_id = parts[1].strip() or None

    result = await cancel_download.execute(user_id=message.from_user.id, job_id=job_id)
    await message.answer(result.message)

@router.message(F.text.startswith("/") & ~F.text.regexp(r"^/(start|help)(?:@\w+)?(?:\s|$)"))
async def unknown_command_handler(message: Message) -> None:
    await message.answer("⚒️ Здесь добывают только видео.\n\nПришли ссылку (http:// или https://)\n\nили загляни в /help."
    )