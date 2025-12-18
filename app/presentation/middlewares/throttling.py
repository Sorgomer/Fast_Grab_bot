from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Awaitable, Dict, Any

from app.di import RateLimiterPort


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, *, limiter: RateLimiterPort) -> None:
        self._limiter = limiter

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.from_user and not self._limiter.allow(event.from_user.id):
            return None
        return await handler(event, data)