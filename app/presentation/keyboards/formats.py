from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.domain.models import FormatChoice
from app.presentation.callback_data import FormatSelectCb


def formats_keyboard(*, choices: list[FormatChoice], version: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for c in choices:
        cb = FormatSelectCb(choice_id=c.choice_id, version=version).pack()
        rows.append([InlineKeyboardButton(text=c.label, callback_data=cb)])

    return InlineKeyboardMarkup(inline_keyboard=rows)