from aiogram import Dispatcher

from .logging import LoggingMiddleware
from .throttling import ThrottlingMiddleware
from .user_context import UserContextMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    dp.update.middleware(UserContextMiddleware())
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(ThrottlingMiddleware())