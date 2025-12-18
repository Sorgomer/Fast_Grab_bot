from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError


class TelegramSenderError(RuntimeError):
    pass


class TelegramSender:
    """
    Sends messages and files to Telegram.
    Owns retry policy (limited) and file-size checks.
    """

    def __init__(self, *, bot: Bot, max_file_mb: int) -> None:
        self._bot = bot
        self._max_bytes = max_file_mb * 1024 * 1024
        self._logger = logging.getLogger("telegram_sender")

    async def send_status(self, chat_id: int, text: str) -> int:
        msg = await self._bot.send_message(chat_id=chat_id, text=text)
        return msg.message_id

    async def edit_status(self, chat_id: int, message_id: int, text: str) -> None:
        await self._bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)

    async def send_video_file(self, chat_id: int, file_path: Path) -> None:
        size = file_path.stat().st_size
        if size > self._max_bytes:
            raise TelegramSenderError("Файл слишком большой для отправки в Telegram.")

        input_file = FSInputFile(path=str(file_path), filename=file_path.name)

        # minimal retry for network
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                await self._bot.send_video(chat_id=chat_id, video=input_file)
                await asyncio.sleep(0)
                return
            except TelegramNetworkError as exc:
                last_exc = exc
                await asyncio.sleep(1 + attempt)
            except TelegramBadRequest as exc:
                # not retryable usually
                raise TelegramSenderError("Telegram отклонил файл.") from exc

        raise TelegramSenderError("Не удалось отправить файл (ошибка сети).") from last_exc