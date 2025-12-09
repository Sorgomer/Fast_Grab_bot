# Telegram Download Bot

Полноценный Telegram-бот для скачивания видео и аудио с популярных платформ
(YouTube, TikTok, Instagram, X/Twitter, VK, Facebook, Dailymotion, Rutube,
SoundCloud, Spotify, PornHub и др., которые поддерживает `yt-dlp`).

## Стек

- Python 3.11+
- aiogram 3.22.0
- aiohttp (webhook-сервер)
- yt-dlp 2025.01.15
- uvloop
- Redis (опционально для rate limiting)
- Render (деплой)

## Запуск локально

1. Установи зависимости:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt# trigger
