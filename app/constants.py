from __future__ import annotations


APP_NAME: str = "download_bot"

# --- Mining UX (single status message, edited over time) ---
UX_PROMPT_SEND_LINK: str = "⛏️👷Я готов спуститься в шахту интернета.\nСкинь ссылку — добуду видео."
UX_MINE_ENTER: str = "🕸️ Вхожу в шахту интернета…"
UX_MINE_SEARCH: str = "🔍🕸️ Поиск видео в глубинах сети…"
UX_MINE_PROBE: str = '🔎 Проверяю добычу…'
UX_MINE_CLEAN: str = "🧼 Очищаю добычу…"
UX_MINE_DONE: str = "🎞️💎 Видео готово!"

MSG_CHOOSE_QUALITY: str = "Выбери качество:\n✅ - Пещера безопасна. Видео можно добыть\n⚠️ - Порода нестабильная. Результат не гарантирован."

UX_MINE_CANCELLED: str = "⛏️⛔ Стоп-машина: добычу остановил."
UX_MINE_CANCEL_NOTHING: str = "⚒️ Нечего останавливать: активной добычи не вижу."
UX_MINE_BAD_LINK: str = "⚒️ Здесь добывают только видео.\n\nПришли ссылку (http:// или https://)\n\nили загляни в /help."
UX_MINE_UNSUPPORTED_LINK: str = "⚠️ В этом районе пока не добываем. Ссылка не поддерживается."
UX_MINE_TRY_LATER: str = "⚠️ Шахта временно недоступна. Попробуй позже."
UX_MINE_SEND_FAILED: str = "⚠️ Telegram не принял груз. Попробуй качество ниже."

# User-facing messages
MSG_FORMAT_RISKY_WARNING: str = "⚠️ Формат “капризный”, может сорваться. Но я попробую добыть результат до конца."
MSG_QUEUE_BUSY: str = "Очередь на загрузку переполнена. Попробуй позже."
MSG_ALREADY_ACTIVE_JOB: str = "Мы уже добываем видео для тебя. Дождись окончания или дай команду остановить работы."
MSG_SESSION_EXPIRED: str = "Ссылка старая — по ней уже не скачать. Пришли новую."
MSG_CHOICE_PROCESS_FAILED: str = "Я не понял твой выбор. Повтори ещё раз."
MSG_FORMAT_UNAVAILABLE: str = "❌ Этот файл слишком тяжёлый — лифт Telegram не поднимет. Выбери формат полегче."

# Loop frames (anti-flood: update >= ~1.5s)
UX_MINE_DOWNLOAD_FRAMES: tuple[str, ...] = (
    "⛏️👷‍♂️🪨\nДобываю видео…",
    "👷‍♂️⛏️💥🪨\nДобываю видео…",
)

UX_MINE_UPLOAD_FRAMES: tuple[str, ...] = (
    "👷‍♂️📦\nПоднимаю видео на поверхность.",
    "👷‍♂️📦\nПоднимаю видео на поверхность..",
    "👷‍♂️📦\nПоднимаю видео на поверхность...",
)

UX_STATUS_MIN_EDIT_INTERVAL_SEC: float = 1.0