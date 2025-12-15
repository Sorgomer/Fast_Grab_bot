from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Router, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from yt_dlp.utils import DownloadError
from app.domain.models import Platform
from app.domain.eligibility import EligibilityChecker, Eligibility
from app.domain.errors import DomainError, QueueFullError
from app.domain.models import ChatId, DownloadJob, FormatOption, MediaKind, MessageId, UserId
from app.infrastructure.platform_detector import PlatformDetector
from app.infrastructure.session_store import SessionStore, UserSession
from app.infrastructure.yt.ydl_client import YdlClient
from app.presentation.callback_data import DownloadCb


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadDeps:
    detector: PlatformDetector
    ydl: YdlClient
    sessions: SessionStore
    enqueue_job: callable  # typed at usage site


router = Router()


def _build_keyboard(options: list[FormatOption]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    checker = EligibilityChecker()

    for opt in options:
        # MP3 всегда показываем (Telegram стабильно принимает)
        if opt.kind == MediaKind.MP3:
            kb.add(
                InlineKeyboardButton(
                    text=opt.label,
                    callback_data=DownloadCb(option_id=opt.option_id).pack(),
                )
            )
            continue

        # Проверка eligibility для видео
        result = checker.check(
            container=opt.container.ext if opt.container else None,
            video_codec=opt.video.codec.value if opt.video else None,
            fps=opt.video.fps if opt.video else None,
            duration_sec=opt.duration_sec,
            filesize_bytes=opt.estimated_filesize,
        )

        # FAIL — кнопку не показываем вообще
        if result.status == Eligibility.FAIL:
            continue

        label = opt.label

        # RISK — помечаем, но показываем
        if result.status == Eligibility.RISK:
            label = f"{label} · ⚠️"

        kb.add(
            InlineKeyboardButton(
                text=label,
                callback_data=DownloadCb(option_id=opt.option_id).pack(),
            )
        )

    kb.adjust(2)
    return kb.as_markup()


@router.message(F.text)
async def handle_url(message: Message, deps: DownloadDeps) -> None:
    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return

    user_id = UserId(message.from_user.id) if message.from_user else UserId(0)
    if user_id == UserId(0):
        await message.answer("Не удалось определить пользователя.")
        return

    try:
        platform = deps.detector.detect(url)
        info = await deps.ydl.extract_info(url)
        options = deps.ydl.build_options(info)

        deps.sessions.set(
            user_id,
            UserSession(url=url, platform=platform, options=options, created_at=__import__("time").time()),
        )

        kb = _build_keyboard(options)
        await message.answer(
            "Выбери формат",
            reply_markup=kb,
        )

    except DownloadError as e:
        if platform == Platform.YOUTUBE:
            log.warning("YouTube extractor unavailable: %s", e)
            await message.answer(
                "⛔ Не удалось получить данные от YouTube.\n"
                "Платформа временно недоступна или ограничена.\n"
                "Попробуйте позже."
            )
        else:
            log.warning("Extractor failed for platform %s: %s", platform, e)
            await message.answer(
                "⛔ Не удалось получить данные от платформы.\n"
                "Пожалуйста, попробуйте ещё раз позже."
            )

    except DomainError as e:
        await message.answer(str(e))

    except Exception:
        log.exception("Unexpected error on url")
        await message.answer(
            "⛔ Произошла внутренняя ошибка.\n"
            "Пожалуйста, попробуйте позже."
        )


@router.callback_query(DownloadCb.filter())
async def handle_format(callback: CallbackQuery, callback_data: DownloadCb, bot: Bot, deps: DownloadDeps) -> None:
    if callback.from_user is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

    user_id = UserId(callback.from_user.id)
    session = deps.sessions.get(user_id)
    if session is None:
        await callback.answer("Сессия устарела. Отправьте ссылку заново.", show_alert=True)
        return

    option = next((o for o in session.options if o.option_id == callback_data.option_id), None)
    if option is None:
        await callback.answer("Формат не найден. Отправьте ссылку заново.", show_alert=True)
        return

    if callback.message is None:
        await callback.answer("Сообщение не найдено.", show_alert=True)
        return

    chat_id = ChatId(callback.message.chat.id)
    status_msg = callback.message

    # UI invariant: do not recreate keyboard; edit only text (reply_markup untouched)
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=status_msg.message_id,
        text=f"✅ Формат выбран: {option.label}\n⏳ Добавляю в очередь…",
    )

    job = DownloadJob(
        chat_id=chat_id,
        user_id=user_id,
        url=session.url,
        platform=session.platform,
        option=option,
        status_message_id=MessageId(status_msg.message_id),
    )

    try:
        deps.enqueue_job(job)
    except QueueFullError as e:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"⛔ {str(e)}",
        )
        await callback.answer()
        return

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=status_msg.message_id,
        text=f"✅ Формат выбран: {option.label}\n⏳ В очереди. Начинаю скачивание…",
    )
    await callback.answer()