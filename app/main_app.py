from aiohttp import web

from app.loader.bot import create_bot_and_dispatcher
from app.loader.redis import init_redis
from app.loader.queue import create_download_infrastructure
from app.loader.web import create_web_app


async def create_app() -> web.Application:
    bot, dp = create_bot_and_dispatcher()
    redis = await init_redis()
    create_download_infrastructure(bot, redis)
    app = create_web_app(bot, dp)
    return app