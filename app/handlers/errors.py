from aiogram import Dispatcher
from aiogram.types import ErrorEvent
from loguru import logger

from app.utils.exceptions import AppError, TooManyRequestsError, ValidationError


def register_error_handlers(dp: Dispatcher) -> None:
    @dp.errors()
    async def errors_handler(event: ErrorEvent):
        exc = event.exception
        logger.exception("Error while handling update: {}", exc)

        message = getattr(event.update, "message", None)
        callback = getattr(event.update, "callback_query", None)

        text = None
        show_alert = False

        if isinstance(exc, TooManyRequestsError):
            text = str(exc)
        elif isinstance(exc, ValidationError):
            text = str(exc)
        elif isinstance(exc, AppError):
            text = str(exc)
            show_alert = True

        if text:
            try:
                if callback:
                    await callback.answer(text, show_alert=show_alert)
                elif message:
                    await message.answer(f"❌ {text}")
            except Exception as e:
                logger.error("Failed to send error message: {}", e)