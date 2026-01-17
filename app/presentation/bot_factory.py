from __future__ import annotations

from aiogram import Bot, Dispatcher

from app.di import Container
from app.presentation.routers.common import router as common_router
from app.presentation.routers.links import router as links_router
from app.presentation.routers.callbacks import router as callbacks_router
from app.presentation.routers.errors import router as errors_router
from app.presentation.middlewares.throttling import ThrottlingMiddleware
from app.presentation.middlewares.logging import LoggingMiddleware


def build_dispatcher_and_bot(container: Container) -> tuple[Bot, Dispatcher]:
    settings = container.settings

    # Use the DI-managed bot instance to avoid multiple sessions.
    bot: Bot = container.get("bot")
    dp = Dispatcher()

    # Middlewares
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(ThrottlingMiddleware(limiter=container.get("rate_limiter")))

    # Routers
    dp.include_router(common_router)
    dp.include_router(links_router)
    dp.include_router(callbacks_router)
    dp.include_router(errors_router)

    # Dependencies injection (aiogram 3: put in workflow data)
    dp.workflow_data.update(
        parse_link=container.get("parse_link_uc"),
        get_formats=container.get("get_formats_uc"),
        enqueue=container.get("enqueue_download_uc"),
        status_animator=container.get("status_animator"),
        cancel_download=container.get("cancel_download_uc"),
    )

    return bot, dp