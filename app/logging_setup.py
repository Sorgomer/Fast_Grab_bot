from __future__ import annotations

import logging
from typing import Final


def setup_logging() -> None:
    level: Final[int] = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)