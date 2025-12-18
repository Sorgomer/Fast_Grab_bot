from __future__ import annotations

import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Dict, Any


class LoggingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._logger = logging.getLogger("tg")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        self._logger.debug("event: %s", type(event).__name__)
        return await handler(event, data)