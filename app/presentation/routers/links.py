from __future__ import annotations

import logging
import re
from typing import Optional

from aiogram import F, Router
from aiogram.types import Message, MessageEntity

from app.application.ports.status_animator import StatusAnimatorPort
from app.application.use_cases.get_formats import GetFormatsUseCase
from app.application.use_cases.parse_link import ParseLinkUseCase
from app.constants import (
    UX_MINE_BAD_LINK,
    UX_MINE_ENTER,
    UX_MINE_SEARCH,
    UX_MINE_TRY_LATER,
    UX_MINE_UNSUPPORTED,
)
from app.domain.errors import DomainError
from app.presentation.keyboards.formats import formats_keyboard

router = Router()

logger = logging.getLogger(__name__)

# Accept both full URLs and common scheme-less URLs that Telegram may send (e.g., youtu.be/..., vk.com/...).
_URL_RX = re.compile(
    r"(?:(?:https?://)?(?:www\.)?(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?:/\S*)?"
)


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip(").,;:!?]}>\"'“”»")
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url


def _extract_url_from_entities(raw: str, entities: list[MessageEntity] | None) -> Optional[str]:
    if not entities:
        return None

    for ent in entities:
        ent_type = getattr(ent.type, "value", ent.type)

        # Telegram: visible text can be NOT an URL, but entity contains ent.url
        if ent_type == "text_link" and getattr(ent, "url", None):
            return getattr(ent, "url")

        # Telegram: entity marks a substring inside raw text
        if ent_type == "url":
            try:
                return raw[ent.offset : ent.offset + ent.length]
            except Exception:
                continue

    return None


def _extract_url_from_message(msg: Message) -> Optional[str]:
    raw = msg.text or msg.caption or ""

    url = _extract_url_from_entities(raw, getattr(msg, "entities", None))
    if url:
        return _normalize_url(url)

    url = _extract_url_from_entities(raw, getattr(msg, "caption_entities", None))
    if url:
        return _normalize_url(url)

    m = _URL_RX.search(raw)
    if not m:
        return None

    return _normalize_url(m.group(0))


def _extract_url(message: Message) -> Optional[str]:
    url = _extract_url_from_message(message)
    if url:
        return url

    r = message.reply_to_message
    if r is not None:
        url = _extract_url_from_message(r)
        if url:
            return url

    return None


@router.message((F.text & ~F.text.startswith("/")) | F.caption)
async def link_handler(
    message: Message,
    parse_link: ParseLinkUseCase,
    get_formats: GetFormatsUseCase,
    status_animator: StatusAnimatorPort,
) -> None:
    # Never process bot commands here.
    if message.text and message.text.startswith("/"):
        return

    logger.debug(
        "link_handler hit: text=%r caption=%r entities=%s caption_entities=%s reply_has=%s",
        message.text,
        message.caption,
        getattr(message, "entities", None),
        getattr(message, "caption_entities", None),
        bool(message.reply_to_message),
    )

    url = _extract_url(message)
    logger.debug("extracted url=%r", url)

    if not url:
        logger.debug(
            "URL not detected. text=%r caption=%r entities=%s caption_entities=%s reply_has=%s reply_text=%r reply_caption=%r",
            message.text,
            message.caption,
            getattr(message, "entities", None),
            getattr(message, "caption_entities", None),
            bool(message.reply_to_message),
            (message.reply_to_message.text if message.reply_to_message else None),
            (message.reply_to_message.caption if message.reply_to_message else None),
        )
        await message.answer("⛏️👷Я готов спуститься в шахту интернета.\nСкинь ссылку — добуду видео.")
        return

    chat_id = int(message.chat.id)
    handle = await status_animator.begin(chat_id=chat_id, text=UX_MINE_ENTER)
    await status_animator.set_text(handle, UX_MINE_SEARCH)

    try:
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