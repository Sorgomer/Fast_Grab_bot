from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery

from app.application.use_cases.enqueue_download import EnqueueDownloadUseCase
from app.presentation.callback_data import FormatSelectCb

router = Router()


@router.callback_query(FormatSelectCb.filter())
async def format_selected(
    callback: CallbackQuery,
    callback_data: FormatSelectCb,
    enqueue: EnqueueDownloadUseCase,
) -> None:
    result = await enqueue.execute(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        session_version=callback_data.version,
        choice_id=callback_data.choice_id,
    )
    await callback.answer()
    await callback.message.answer(result.message)