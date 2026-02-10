from __future__ import annotations

from app.application.use_cases.cancel_download import CancelDownloadUseCase
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from app.constants import UX_PROMPT_SEND_LINK, UX_MINE_BAD_LINK, UX_HELP

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    await message.answer(UX_PROMPT_SEND_LINK)

@router.message(Command("help"))
async def start_handler(message: Message) -> None:
    await message.answer(UX_HELP)

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
    await message.answer(UX_MINE_BAD_LINK)