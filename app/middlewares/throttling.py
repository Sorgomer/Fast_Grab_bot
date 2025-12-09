from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from app.loader.queue import get_rate_limiter
from app.utils.exceptions import TooManyRequestsError


class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        rate_limiter = get_rate_limiter()

        user_id = None
        is_link_or_callback = False

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            # Ограничиваем только сообщения с ссылками (грубая проверка)
            if "http://" in event.text or "https://" in event.text:
                is_link_or_callback = True
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            is_link_or_callback = True

        if user_id and is_link_or_callback:
            if not await rate_limiter.check_and_increment_messages(user_id):
                raise TooManyRequestsError(
                    "Слишком много запросов. Попробуйте чуть позже."
                )

        return await handler(event, data)