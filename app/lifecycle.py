from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from .di import AsyncStartStop, Container
from .di import build_graph as build_di_graph


class LifecycleError(RuntimeError):
    pass


@dataclass(slots=True)
class AppLifecycle:
    container: Container
    _started: bool = field(default=False, init=False)
    _start_order: list[str] = field(default_factory=list, init=False)
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger("lifecycle"), init=False)

    async def startup(self) -> None:
        if self._started:
            raise LifecycleError("startup() called twice")

        self._logger.info("startup: begin")
        await self._preflight()

        # DI graph must be built during startup (crash here if anything is wrong)
        build_di_graph(self.container)

        await self._start_components()
        self._started = True
        self._logger.info("startup: done")

    async def shutdown(self) -> None:
        if not self._started:
            self._logger.info("shutdown: skipped (not started)")
            return

        self._logger.info("shutdown: begin")
        await self._stop_components()
        self._started = False
        self._logger.info("shutdown: done")

    async def _preflight(self) -> None:
        s = self.container.settings
        try:
            s.temp_root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise LifecycleError(f"TEMP_ROOT is not writable: {s.temp_root}") from exc

    async def _start_components(self) -> None:
        for name, component in self.container.all_components():
            if isinstance(component, AsyncStartStop):
                self._logger.info("component.start: %s", name)
                try:
                    await component.start()
                except Exception as exc:
                    raise LifecycleError(f"Component failed to start: {name}") from exc
                self._start_order.append(name)

    async def _stop_components(self) -> None:
        for name in reversed(self._start_order):
            component: Any = self.container.get(name)
            if isinstance(component, AsyncStartStop):
                self._logger.info("component.stop: %s", name)
                try:
                    await component.stop()
                except Exception:
                    self._logger.exception("component.stop failed: %s", name)

        await asyncio.sleep(0)
        self._start_order.clear()