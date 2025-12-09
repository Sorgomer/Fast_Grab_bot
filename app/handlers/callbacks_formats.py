from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.loader.queue import get_download_manager
from app.keyboards.common import cancel_keyboard
from app.services.models import DownloadTask, DownloadTaskStatus
from app.utils.exceptions import AppError, TaskCancelledError
from app.services.platforms import get_downloader

router = Router(name="formats")


@router.callback_query(F.data.startswith("fmt:"))
async def callback_choose_format(callback: CallbackQuery):
    dm = get_download_manager()
    data = callback.data or ""
    _, task_id, format_id = data.split(":", 2)

    user = callback.from_user
    assert user is not None
    user_id = user.id
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    msg_id = callback.message.message_id  # type: ignore[union-attr]

    try:
        info = dm.get_media_info(task_id)
    except AppError as e:
        await callback.answer(str(e), show_alert=True)
        return

    fmt = None
    for f in info.formats:
        if f.id == format_id:
            fmt = f
            break

    if not fmt:
        await callback.answer("Формат не найден", show_alert=True)
        return

    task = DownloadTask(
        id=task_id,
        user_id=user_id,
        chat_id=chat_id,
        message_id=msg_id,
        platform=info.platform,
        url=info.url,
        media_info=info,
        format=fmt,
        status=DownloadTaskStatus.PENDING,
    )

    try:
        await dm.enqueue(task)
    except AppError as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.message.edit_text(
        f"Вы выбрали: <b>{fmt.label}</b>\n\n"
        "⏳ Статус: <i>В очереди...</i>",
        reply_markup=cancel_keyboard(task_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel:"))
async def callback_cancel(callback: CallbackQuery):
    dm = get_download_manager()
    data = callback.data or ""
    _, task_id = data.split(":", 1)

    user = callback.from_user
    assert user is not None
    user_id = user.id

    try:
        await dm.cancel(task_id, user_id)
    except TaskCancelledError as e:
        await callback.message.edit_text("🛑 Загрузка отменена.")
        await callback.answer(str(e), show_alert=False)
    except AppError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception:
        await callback.answer("Не удалось отменить задачу", show_alert=True)