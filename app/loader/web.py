from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from loguru import logger

from app.config.settings import get_settings
from app.loader.queue import get_download_manager


async def on_startup(app: web.Application):
    settings = get_settings()
    bot: Bot = app["bot"]
    await bot.set_webhook(
        url=str(settings.webhook_url) + settings.webhook_path,
        allowed_updates=app["dp"].resolve_used_update_types(),
        drop_pending_updates=True,
    )
    logger.info("Webhook set to {}", settings.webhook_url + settings.webhook_path)
    dm = get_download_manager()
    await dm.start()


async def on_shutdown(app: web.Application):
    bot: Bot = app["bot"]
    await bot.delete_webhook()
    logger.info("Webhook deleted")
    dm = get_download_manager()
    await dm.stop()


def create_web_app(bot: Bot, dp: Dispatcher) -> web.Application:
    app = web.Application()

    app["bot"] = bot
    app["dp"] = dp

    settings = get_settings()

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    ).register(app, path=settings.webhook_path)

    async def health(request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/health", health)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    setup_application(app, dp, bot=bot)

    return app