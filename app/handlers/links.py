from aiogram import Router, F
from aiogram.types import Message

from app.loader.queue import get_download_manager
from app.keyboards.formats import build_formats_keyboard
from app.utils.url_tools import extract_first_url, validate_url, detect_platform
from app.utils.text import build_media_info_message
from app.utils.exceptions import AppError
from app.services.platforms import get_downloader

router = Router(name="links")


@router.message(F.text.regexp(r"https?://"))
async def handle_link(message: Message):
    dm = get_download_manager()

    url = extract_first_url(message.text or "")
    if not url:
        return

    url = validate_url(url)
    platform = detect_platform(url)

    await message.chat.do("typing")

    try:
        downloader = get_downloader(platform)
        info = await downloader.extract_info(url)
    except AppError as e:
        await message.answer(f"❌ {e}")
        return
    except Exception:
        await message.answer("❌ Не удалось получить информацию по ссылке.")
        return

    task_id = dm.create_task_id()
    dm.store_media_info(task_id, info)

    text = build_media_info_message(info)
    kb = build_formats_keyboard(info, task_id)

    await message.answer(text, reply_markup=kb)