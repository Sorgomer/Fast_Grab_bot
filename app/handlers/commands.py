from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router(name="commands")


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Я могу скачивать видео и аудио с разных платформ:\n"
        "YouTube, TikTok, Instagram, X (Twitter), VK, Facebook, Dailymotion, Rutube, "
        "SoundCloud, Spotify, PornHub и других, поддерживаемых yt-dlp.\n\n"
        "Просто отправь мне ссылку — я предложу варианты качества 🙂"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ Инструкция:\n\n"
        "1. Отправь ссылку на видео или аудио.\n"
        "2. Выбери качество с помощью кнопок.\n"
        "3. Дождись загрузки и получи файл прямо здесь.\n\n"
        "⚠️ Ограничения Telegram:\n"
        "• Файл до 2 ГБ\n"
        "• Если файл больше лимита — я об этом сообщу."
    )