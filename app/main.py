from __future__ import annotations

import asyncio
import logging
import signal
from types import FrameType
from typing import Callable, Awaitable

from .di import Container, DIError
from .logging_setup import setup_logging
from .lifecycle import AppLifecycle


class MainError(RuntimeError):
    pass


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop: Callable[[], None]) -> None:
    logger = logging.getLogger("signals")

    def _handler(signum: int, _frame: FrameType | None) -> None:
        logger.info("signal received: %s", signum)
        stop()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, stop)
        except NotImplementedError:
            # Fallback for platforms where add_signal_handler is not supported
            signal.signal(s, _handler)


async def _run_polling(container: Container) -> None:
    """
    Strictly crash at startup if presentation layer isn't ready.
    This import is intentional to keep app bootstrap independent of presentation code.
    """
    try:
        from app.presentation.bot_factory import build_dispatcher_and_bot  # type: ignore
    except Exception as exc:
        raise MainError(
            "Presentation layer is not implemented yet (build_dispatcher_and_bot missing). "
            "Finish Phase 2 blocks before running the app."
        ) from exc

    bot, dp = build_dispatcher_and_bot(container)

    # aiogram 3.22: polling runner
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def amain() -> None:
    container = Container.build()
    setup_logging(level=container.settings.log_level)

    logger = logging.getLogger("main")
    lifecycle = AppLifecycle(container=container)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    _install_signal_handlers(loop, _stop)

    await lifecycle.startup()

    polling_task = asyncio.create_task(_run_polling(container), name="polling")
    stop_task = asyncio.create_task(stop_event.wait(), name="stop_event")

    done, _ = await asyncio.wait({polling_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)

    if stop_task in done and not polling_task.done():
        logger.info("stop requested; cancelling polling")
        polling_task.cancel()

    try:
        await polling_task
    except asyncio.CancelledError:
        logger.info("polling cancelled")
    finally:
        await lifecycle.shutdown()
        bot = container.get("bot")
        await bot.session.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()