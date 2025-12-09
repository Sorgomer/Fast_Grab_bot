import asyncio

import uvloop
from aiohttp import web
from loguru import logger

from app.main_app import create_app
from app.config.settings import get_settings
from app.loader.logging import setup_logging


def main():
    uvloop.install()
    setup_logging()
    settings = get_settings()

    logger.info("Starting app on {}:{}", settings.webapp_host, settings.webapp_port)

    async def _run():
        app = await create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=settings.webapp_host, port=settings.webapp_port)
        await site.start()
        logger.info("App started")
        # Блокируемся навсегда
        while True:
            await asyncio.sleep(3600)

    asyncio.run(_run())


if __name__ == "__main__":
    main()