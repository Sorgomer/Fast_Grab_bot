from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        logger.debug(f"Incoming update: {event!r}")
        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            logger.exception(f"Error while handling update: {e!r}")
            raise