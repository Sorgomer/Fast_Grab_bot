from aiogram import Router, Dispatcher

from .commands import router as commands_router
from .links import router as links_router
from .callbacks_formats import router as formats_router
from .errors import register_error_handlers


def setup_routers(dp: Dispatcher) -> None:
    main_router = Router()
    main_router.include_router(commands_router)
    main_router.include_router(links_router)
    main_router.include_router(formats_router)

    dp.include_router(main_router)
    register_error_handlers(dp)