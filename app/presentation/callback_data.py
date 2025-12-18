from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class FormatSelectCb(CallbackData, prefix="fmt"):
    choice_id: str
    version: int