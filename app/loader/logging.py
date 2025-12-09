import logging
import sys

from loguru import logger

from app.config.settings import get_settings


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    settings = get_settings()

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(settings.log_level)

    for name in ("aiogram", "aiohttp", "asyncio"):
        logging.getLogger(name).setLevel(settings.log_level)

    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        backtrace=True,
        diagnose=False,
    )

    logger.info("Logging configured")