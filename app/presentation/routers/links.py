from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app.application.use_cases.parse_link import ParseLinkUseCase
from app.application.use_cases.get_formats import GetFormatsUseCase
from app.domain.errors import DomainError
from app.application.ports.status_animator import StatusAnimatorPort
from app.constants import (
    UX_MINE_ENTER,
    UX_MINE_SEARCH,
    UX_MINE_BAD_LINK,
    UX_MINE_UNSUPPORTED,
    UX_MINE_TRY_LATER,
)
from app.presentation.keyboards.formats import formats_keyboard

router = Router()


@router.message()
async def link_handler(
    message: Message,
    parse_link: ParseLinkUseCase,
    get_formats: GetFormatsUseCase,
    status_animator: StatusAnimatorPort,
) -> None:
    chat_id = int(message.chat.id)
    handle = await status_animator.begin(chat_id=chat_id, text=UX_MINE_ENTER)
    await status_animator.set_text(handle, UX_MINE_SEARCH)

    try:
        parsed = await parse_link.execute(message.text or "")
        dto = await get_formats.execute(
            user_id=message.from_user.id,
            url=parsed.url,
            platform=parsed.platform,
        )
    except DomainError as exc:
        # map common domain messages into mine-style text
        text = exc.user_message
        if "не вижу" in text.lower():
            await status_animator.fail(handle, text=UX_MINE_BAD_LINK)
        elif "не поддерж" in text.lower():
            await status_animator.fail(handle, text=UX_MINE_UNSUPPORTED)
        else:
            await status_animator.fail(handle, text=text)
        return
    except Exception:
        await status_animator.fail(handle, text=UX_MINE_TRY_LATER)
        return

    kb = formats_keyboard(choices=dto.choices, version=dto.session_version)
    await status_animator.set_text(
        handle,
        "Выбери качество:\n✅ - пройдёт почти всегда\n⚠️ - Telegram может не пропустить",
        reply_markup=kb,
    )