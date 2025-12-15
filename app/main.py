from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os
import signal
from typing import Optional

from aiogram import Dispatcher
from aiogram.types import Update

from app.di import build_app, App
from app.logging_setup import setup_logging
from app.presentation.routers.download import DownloadDeps


log = logging.getLogger(__name__)


class AppRunner:
    def __init__(self, app: App) -> None:
        self._app = app
        self._stop_event = asyncio.Event()

    async def startup(self) -> None:
        await self._app.queue.start()

    async def shutdown(self) -> None:
        log.info("Stopping download queue...")

        try:
            await asyncio.wait_for(self._app.queue.stop(), timeout=5.0)
        except asyncio.TimeoutError:
            log.warning("Queue did not stop in time, forcing shutdown")

        log.info("Closing bot session...")
        try:
            await asyncio.wait_for(self._app.bot.session.close(), timeout=5.0)
        except asyncio.TimeoutError:
            log.warning("Bot session did not close in time")

        log.info("Shutdown complete")

    async def run(self) -> None:
        dp = self._app.dp

        # inject deps provider
        deps = dp.get("deps")
        if not isinstance(deps, DownloadDeps):
            raise RuntimeError("Deps not initialized.")

        async def _deps_middleware(handler, event, data):
            data["deps"] = deps
            return await handler(event, data)

        dp.update.middleware(_deps_middleware)

        await self.startup()
        try:
            await dp.start_polling(
                self._app.bot,
                handle_signals=False,
                allowed_updates=dp.resolve_used_update_types(),
                stop_event=self._stop_event,
            )
        finally:
            await self.shutdown()

    def request_stop(self) -> None:
        log.info("SIGINT received, shutting down...")
        self._stop_event.set()

        # Force-stop polling to unblock long-polling HTTP request
        try:
            asyncio.get_running_loop().create_task(
                self._app.dp.stop_polling()
            )
        except RuntimeError:
            pass


async def amain() -> None:
    setup_logging()
    app = build_app()
    runner = AppRunner(app)

    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, runner.request_stop)
        except NotImplementedError:
            pass

    await runner.run()

def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()