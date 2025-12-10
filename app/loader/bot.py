from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from loguru import logger

from app.config.settings import get_settings
from app.handlers import setup_routers
from app.middlewares import setup_middlewares


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    settings = get_settings()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    dp = Dispatcher()
    setup_middlewares(dp)
    setup_routers(dp)

    logger.info("Bot and Dispatcher created")
    return bot, dp