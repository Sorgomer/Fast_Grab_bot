from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.application.ports.status_animator import StatusAnimatorPort, StatusHandle
from app.infrastructure.telegram_sender import TelegramSender


@dataclass(slots=True)
class _HandleState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    loop_task: asyncio.Task[None] | None = None
    loop_stop: asyncio.Event = field(default_factory=asyncio.Event)
    last_edit_mono: float = 0.0


class StatusAnimator(StatusAnimatorPort):
    """Single-message status animation controller.

    Guarantees:
      - one Telegram message edited over time
      - loop animations throttled to avoid FloodWait
      - stop() cancels all running loops (lifecycle-safe)
    """

    def __init__(self, *, sender: TelegramSender, min_edit_interval_sec: float, loop_interval_sec: float | None = None) -> None:
        self._sender = sender
        self._min_interval = float(min_edit_interval_sec)
        # tuned for fast UX without FloodWait
        self._loop_interval = float(loop_interval_sec) if loop_interval_sec is not None else max(0.5, self._min_interval)
        self._logger = logging.getLogger("status_animator")
        self._state: dict[StatusHandle, _HandleState] = {}

    async def start(self) -> None:
        return

    async def stop(self) -> None:
        handles = list(self._state.keys())
        for h in handles:
            try:
                await self.stop_loop(h)
            except Exception:
                self._logger.exception("failed to stop loop: chat_id=%s message_id=%s", h.chat_id, h.message_id)
        self._state.clear()

    async def begin(self, *, chat_id: int, text: str) -> StatusHandle:
        message_id = await self._sender.send_status(chat_id, text)
        return self.attach(chat_id=chat_id, message_id=message_id)

    def attach(self, *, chat_id: int, message_id: int) -> StatusHandle:
        handle = StatusHandle(chat_id=chat_id, message_id=message_id)
        self._state.setdefault(handle, _HandleState())
        return handle

    async def set_text(self, handle: StatusHandle, text: str, *, reply_markup: Any | None = None) -> None:
        await self._edit_throttled(handle, text, reply_markup=reply_markup, min_interval_sec=self._min_interval)

    async def start_loop(self, handle: StatusHandle, *, frames: Sequence[str]) -> None:
        frames_t = tuple(frames)
        if not frames_t:
            return
        await self.stop_loop(handle)

        st = self._state.setdefault(handle, _HandleState())
        st.loop_stop.clear()
        st.loop_task = asyncio.create_task(
            self._loop_worker(handle, frames_t),
            name=f"status_loop:{handle.chat_id}:{handle.message_id}",
        )

    async def stop_loop(self, handle: StatusHandle) -> None:
        st = self._state.get(handle)
        if st is None or st.loop_task is None:
            return
        task = st.loop_task
        st.loop_task = None
        st.loop_stop.set()
        try:
            await task
        except asyncio.CancelledError:
            return
        except Exception:
            self._logger.exception("loop task failed: chat_id=%s message_id=%s", handle.chat_id, handle.message_id)

    async def finish(self, handle: StatusHandle, *, text: str) -> None:
        await self.stop_loop(handle)
        await self.set_text(handle, text)

    async def fail(self, handle: StatusHandle, *, text: str) -> None:
        await self.stop_loop(handle)
        await self.set_text(handle, text)

    async def _loop_worker(self, handle: StatusHandle, frames: tuple[str, ...]) -> None:
        idx = 0
        st = self._state.setdefault(handle, _HandleState())
        while not st.loop_stop.is_set():
            try:
                await self._edit_throttled(handle, frames[idx], reply_markup=None, min_interval_sec=self._loop_interval)
                idx = (idx + 1) % len(frames)
            except asyncio.CancelledError:
                return
            except Exception:
                # Do not let a transient Telegram error kill the animation forever.
                self._logger.exception(
                    "status loop edit failed; keeping loop alive: chat_id=%s message_id=%s",
                    handle.chat_id,
                    handle.message_id,
                )
                # Small backoff to avoid tight error loops.
                await asyncio.sleep(max(0.5, self._loop_interval))

    async def _edit_throttled(self, handle: StatusHandle, text: str, *, reply_markup: Any | None, min_interval_sec: float) -> None:
        st = self._state.setdefault(handle, _HandleState())
        async with st.lock:
            now = time.monotonic()
            delta = now - st.last_edit_mono
            if delta < min_interval_sec:
                await asyncio.sleep(min_interval_sec - delta)
            await self._sender.edit_status(
                handle.chat_id,
                handle.message_id,
                text,
                reply_markup=reply_markup,
            )
            st.last_edit_mono = time.monotonic()
