
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

    Strategy:
      - small files: try send_video for UX, fallback to send_document if Telegram rejects
      - big files: send_document only (send_video is stricter)
    """

    def __init__(self, *, bot: Bot, hard_limit_mb: int, document_only_from_mb: int) -> None:
        self._bot = bot
        self._hard_bytes = hard_limit_mb * 1024 * 1024
        self._document_only_from_bytes = document_only_from_mb * 1024 * 1024
        self._logger = logging.getLogger("telegram_sender")

    async def send_status(self, chat_id: int, text: str) -> int:
        msg = await self._bot.send_message(chat_id=chat_id, text=text)
        return msg.message_id

    async def edit_status(self, chat_id: int, message_id: int, text: str) -> None:
        await self._bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)

    async def send_media_best_effort(self, chat_id: int, file_path: Path) -> None:
        if not file_path.exists():
            raise TelegramSenderError("Файл не найден перед отправкой.")
        size = file_path.stat().st_size
        if size <= 0:
            raise TelegramSenderError("Файл пустой.")
        if size > self._hard_bytes:
            raise TelegramSenderError("Файл превышает лимит Telegram для ботов (≈2ГБ).")

        input_file = FSInputFile(path=str(file_path), filename=file_path.name)

        if size >= self._document_only_from_bytes:
            await self._send_document_with_retry(chat_id, input_file)
            return

        # Try send_video first, fallback to document on strict validation failures.
        try:
            await self._send_video_with_retry(chat_id, input_file)
        except TelegramSenderError:
            await self._send_document_with_retry(chat_id, input_file)

    async def _send_video_with_retry(self, chat_id: int, input_file: FSInputFile) -> None:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                await self._bot.send_video(chat_id=chat_id, video=input_file)
                return
            except TelegramNetworkError as exc:
                last_exc = exc
                await asyncio.sleep(1 + attempt)
            except TelegramBadRequest as exc:
                raise TelegramSenderError("Telegram отклонил видео.") from exc
        raise TelegramSenderError("Не удалось отправить видео (ошибка сети).") from last_exc

    async def _send_document_with_retry(self, chat_id: int, input_file: FSInputFile) -> None:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                await self._bot.send_document(chat_id=chat_id, document=input_file)
                return
            except TelegramNetworkError as exc:
                last_exc = exc
                await asyncio.sleep(1 + attempt)
            except TelegramBadRequest as exc:
                raise TelegramSenderError("Telegram отклонил документ.") from exc
        raise TelegramSenderError("Не удалось отправить документ (ошибка сети).") from last_exc
