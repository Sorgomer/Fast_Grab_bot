from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app.application.use_cases.parse_link import ParseLinkUseCase
from app.application.use_cases.get_formats import GetFormatsUseCase
from app.domain.errors import DomainError
from app.presentation.keyboards.formats import formats_keyboard

router = Router()


@router.message()
async def link_handler(
    message: Message,
    parse_link: ParseLinkUseCase,
    get_formats: GetFormatsUseCase,
) -> None:
    try:
        parsed = await parse_link.execute(message.text or "")
        dto = await get_formats.execute(
            user_id=message.from_user.id,
            url=parsed.url,
            platform=parsed.platform,
        )
    except DomainError as exc:
        await message.answer(exc.user_message)
        return
    except Exception:
        await message.answer("Не удалось обработать ссылку " \
        "Попробуй ещё раз")
        return

    kb = formats_keyboard(choices=dto.choices, version=dto.session_version)
    await message.answer("Выбери формат:\n" \
    "✅ - Рекомендовано\n" \
    "⚠️ - Telegram может не пропустить этот формат", reply_markup=kb)