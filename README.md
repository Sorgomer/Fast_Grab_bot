
# Fast Grab Bot (local polling)

Telegram бот для скачивания видео (YouTube, VK) через `yt-dlp` + `ffmpeg`, запуск только в режиме **polling**.

## Требования

- Python 3.11+
- `ffmpeg` / `ffprobe` в PATH
- `pip install -r requirements.txt`

## Настройка

1) Скопируй `.env.example` в `.env` и укажи `BOT_TOKEN`.

2) Экспортируй переменные окружения (пример для macOS/Linux):

```bash
set -a
source .env
set +a
```

## Запуск

```bash
python -m app.main
```

## Политика Telegram по размерам

- до `TG_SAFE_LIMIT_MB` — ✅ (наиболее надёжно)
- `TG_SAFE_LIMIT_MB..TG_HARD_LIMIT_MB` — ⚠️ (best-effort, может не пройти)
- больше `TG_HARD_LIMIT_MB` — ❌ (не показываем/не ставим в очередь)

Для больших файлов отправка идёт через **send_document** (у видео `send_video` строже).
