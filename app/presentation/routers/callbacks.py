from __future__ import annotations

import asyncio
import logging
from aiogram import Router
from aiogram.types import CallbackQuery

from app.application.use_cases.enqueue_download import EnqueueDownloadUseCase
from app.application.ports.status_animator import StatusAnimatorPort
from app.presentation.callback_data import FormatSelectCb
from app.constants import UX_MINE_ENTER, UX_MINE_DOWNLOAD_FRAMES

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(FormatSelectCb.filter())
async def format_selected(
    callback: CallbackQuery,
    callback_data: FormatSelectCb,
    enqueue: EnqueueDownloadUseCase,
    status_animator: StatusAnimatorPort,
) -> None:
    # Always acknowledge button press immediately.
    await callback.answer()

    # Callback may come without message in rare cases.
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    message_id = callback.message.message_id

    # Bind animator to the existing message BEFORE any business logic.
    handle = status_animator.attach(chat_id=chat_id, message_id=message_id)

    # Execute enqueue. Newer versions require status_message_id so the worker can edit the same message.
    try:
        result = await enqueue.execute(
            user_id=callback.from_user.id,
            chat_id=chat_id,
            session_version=callback_data.version,
            choice_id=callback_data.choice_id,
            status_message_id=message_id,
        )
    except TypeError:
        result = await enqueue.execute(
            user_id=callback.from_user.id,
            chat_id=chat_id,
            session_version=callback_data.version,
            choice_id=callback_data.choice_id,
        )

    logger.info(
        "[CALLBACK] quality selected user_id=%s chat_id=%s choice_id=%s version=%s accepted=%s",
        callback.from_user.id,
        chat_id,
        callback_data.choice_id,
        callback_data.version,
        result.accepted,
    )

    if not result.accepted:
        # Keep it user-safe and in the same message.
        await status_animator.set_text(handle, f"⚠️ {result.message}", reply_markup=None)
        return

    # Remove the keyboard immediately and show the initial acceptance text.
    await status_animator.set_text(handle, UX_MINE_ENTER, reply_markup=None)

    # After 1.5s start the mining loop. This runs in background and will be stopped
    # later by the download pipeline stages.
    mining_frames = UX_MINE_DOWNLOAD_FRAMES

    async def _delayed_start() -> None:
        try:
            await asyncio.sleep(1.5)
            await status_animator.start_loop(handle, frames=mining_frames)
        except Exception:
            logger.exception("[CALLBACK] failed to start mining loop")

    asyncio.create_task(_delayed_start())