from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

import re

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

_URL_RX = re.compile(r"https?://\S+")
_URL_ANY_RE = r"(?s).*https?://\S+.*"

@router.message(
    (F.text.regexp(_URL_ANY_RE) & ~F.text.startswith("/"))
    | F.caption.regexp(_URL_ANY_RE)
)
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
        raw = message.text or message.caption or ""
        m = _URL_RX.search(raw)
        if not m:
            await status_animator.fail(handle, text=UX_MINE_BAD_LINK)
            return

        url = m.group(0).strip().rstrip(").,;:!?]}>\"'“”»")
        parsed = await parse_link.execute(url)
        dto = await get_formats.execute(
            user_id=message.from_user.id,
            url=parsed.url,
            platform=parsed.platform,
        )
    except DomainError as exc:
        text = getattr(exc, "user_message", None) or str(exc)
        low = text.lower()
        if "не поддерж" in low:
            await status_animator.fail(handle, text=UX_MINE_UNSUPPORTED)
        elif "ссылка" in low or "http://" in low or "https://" in low:
            await status_animator.fail(handle, text=UX_MINE_BAD_LINK)
        else:
            await status_animator.fail(handle, text=text)
        return
    except Exception:
        await status_animator.fail(handle, text=UX_MINE_TRY_LATER)
        return

    kb = formats_keyboard(choices=dto.choices, version=dto.session_version)
    await status_animator.set_text(
        handle,
        "Выбери качество:\n✅ - Пещера безопасна. Видео можно добыть\n⚠️ - Порода нестабильная. Результат не гарантирован.",
        reply_markup=kb,
    )


@router.message(~F.text & ~F.caption)
async def non_text_input_handler(message: Message) -> None:
    await message.answer("⛏️👷Я готов спуститься в шахту интернета.\nСкинь ссылку — добуду видео.")


@router.message(
    (F.text & ~F.text.regexp(_URL_ANY_RE) & ~F.text.startswith("/"))
    | (F.caption & ~F.caption.regexp(_URL_ANY_RE))
)
async def invalid_text_input_handler(message: Message) -> None:
    await message.answer("⛏️👷Я готов спуститься в шахту интернета.\nСкинь ссылку — добуду видео.")