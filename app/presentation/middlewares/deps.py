from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.presentation.routers.download import DownloadDeps


Handler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class DepsMiddleware(BaseMiddleware):
    deps: DownloadDeps

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["deps"] = self.deps
        return await handler(event, data)