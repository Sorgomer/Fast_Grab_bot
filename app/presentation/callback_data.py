from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class DownloadCb(CallbackData, prefix="dl"):
    option_id: str