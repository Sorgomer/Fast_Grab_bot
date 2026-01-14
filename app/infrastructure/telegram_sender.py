from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Final

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError


class TelegramSenderError(RuntimeError):
    pass


class TelegramSenderRejectedError(TelegramSenderError):
    """Telegram rejected the upload (e.g., strict validation for send_video)."""


class TelegramSenderNetworkAmbiguousError(TelegramSenderError):
    """Network timeout/error: delivery status is ambiguous, do NOT retry to avoid duplicates."""


class TelegramSender:
    """
    Sends messages and files to Telegram.

    Strategy:
      - small files: try send_video for UX, fallback to send_document if Telegram rejects
      - big files: send_document only (send_video is stricter)
    """

    _MIN_REQUEST_TIMEOUT_SEC: Final[int] = 60
    _MAX_REQUEST_TIMEOUT_SEC: Final[int] = 60 * 60  # 1 hour safety cap
    _SECONDS_PER_MB: Final[float] = 2.0

    def __init__(self, *, bot: Bot, hard_limit_mb: int, document_only_from_mb: int) -> None:
        self._bot = bot
        self._hard_bytes = hard_limit_mb * 1024 * 1024
        self._document_only_from_bytes = document_only_from_mb * 1024 * 1024
        self._logger = logging.getLogger("telegram_sender")

    async def send_status(self, chat_id: int, text: str) -> int:
        msg = await self._bot.send_message(chat_id=chat_id, text=text)
        return msg.message_id

    async def edit_status(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        await self._bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )

    def _request_timeout_sec(self, size_bytes: int) -> int:
        # Telegram upload time strongly depends on network. Use a generous timeout based on size.
        # 2 seconds per MB is conservative for slow uplinks; capped to avoid hanging forever.
        mb = max(1.0, float(size_bytes) / (1024.0 * 1024.0))
        timeout = int(round(self._MIN_REQUEST_TIMEOUT_SEC + mb * self._SECONDS_PER_MB))
        if timeout < self._MIN_REQUEST_TIMEOUT_SEC:
            return self._MIN_REQUEST_TIMEOUT_SEC
        if timeout > self._MAX_REQUEST_TIMEOUT_SEC:
            return self._MAX_REQUEST_TIMEOUT_SEC
        return timeout

    async def send_media_best_effort(self, chat_id: int, file_path: Path) -> None:
        if not file_path.exists():
            raise TelegramSenderError("Файл не найден перед отправкой.")
        size = file_path.stat().st_size
        request_timeout = self._request_timeout_sec(size)
        if size <= 0:
            raise TelegramSenderError("Файл пустой.")
        if size > self._hard_bytes:
            raise TelegramSenderError("Файл превышает лимит Telegram для ботов (≈2ГБ).")

        input_file = FSInputFile(path=str(file_path), filename=file_path.name)

        if size >= self._document_only_from_bytes:
            await self._send_document_once(chat_id, input_file, request_timeout=request_timeout)
            return

        # Try send_video first, fallback to document ONLY if Telegram rejects video.
        try:
            await self._send_video_once(chat_id, input_file, request_timeout=request_timeout)
        except TelegramSenderRejectedError:
            await self._send_document_once(chat_id, input_file, request_timeout=request_timeout)

    async def _send_video_once(self, chat_id: int, input_file: FSInputFile, *, request_timeout: int) -> None:
        try:
            await self._bot.send_video(chat_id=chat_id, video=input_file, request_timeout=request_timeout)
        except TelegramBadRequest as exc:
            raise TelegramSenderRejectedError("Telegram отклонил видео.") from exc
        except TelegramNetworkError as exc:
            # Ambiguous: Telegram may have received the upload even if the client timed out.
            raise TelegramSenderNetworkAmbiguousError(
                "Telegram не подтвердил доставку (таймаут/сеть). Возможна отправка. Повтор не выполняю, чтобы избежать дублей."
            ) from exc

    async def _send_document_once(self, chat_id: int, input_file: FSInputFile, *, request_timeout: int) -> None:
        try:
            await self._bot.send_document(chat_id=chat_id, document=input_file, request_timeout=request_timeout)
        except TelegramBadRequest as exc:
            raise TelegramSenderRejectedError("Telegram отклонил документ.") from exc
        except TelegramNetworkError as exc:
            # Ambiguous: Telegram may have received the upload even if the client timed out.
            raise TelegramSenderNetworkAmbiguousError(
                "Telegram не подтвердил доставку (таймаут/сеть). Возможна отправка. Повтор не выполняю, чтобы избежать дублей."
            ) from exc
