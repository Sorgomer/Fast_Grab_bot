from __future__ import annotations

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.di import Container
from app.presentation.routers.common import router as common_router
from app.presentation.routers.links import router as links_router
from app.presentation.routers.callbacks import router as callbacks_router
from app.presentation.routers.errors import router as errors_router
from app.presentation.middlewares.throttling import ThrottlingMiddleware
from app.presentation.middlewares.logging import LoggingMiddleware


def build_dispatcher(container: Container) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

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
    )

    return dp