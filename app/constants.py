from __future__ import annotations


APP_NAME: str = "download_bot"

# User-facing, short, user-safe messages (no stack traces)
MSG_UNSUPPORTED_LINK: str = "Ссылка не поддерживается. Пришли ссылку на YouTube или VK Video."
MSG_BAD_LINK: str = "Не вижу корректную ссылку. Пришли URL целиком."
MSG_INTERNAL_ERROR: str = "Что-то пошло не так. Попробуй ещё раз чуть позже."
MSG_QUEUE_BUSY: str = "Очередь занята. Попробуй позже."
MSG_CANCELLED: str = "Ок, отменил."