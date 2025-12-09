from datetime import timedelta

from app.services.models import MediaInfo, MediaFormat, DownloadTaskStatus


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "неизвестно"
    td = timedelta(seconds=seconds)
    total_minutes, sec = divmod(td.seconds, 60)
    hours, minutes = divmod(total_minutes, 60)
    if td.days > 0 or hours > 0:
        return f"{hours}ч {minutes}м {sec}с"
    return f"{minutes}м {sec}с"


def build_media_info_message(info: MediaInfo) -> str:
    duration = format_duration(info.duration)
    return (
        f"🔗 <b>{info.platform.value.upper()}</b>\n"
        f"🎬 <b>{info.title}</b>\n"
        f"⏱ Длительность: <b>{duration}</b>\n\n"
        f"Выберите качество:"
    )


def build_status_message(status: DownloadTaskStatus, fmt: MediaFormat | None = None) -> str:
    if status == DownloadTaskStatus.PENDING:
        return "⏳ Статус: <i>В очереди...</i>"
    if status == DownloadTaskStatus.DOWNLOADING:
        return "📥 Статус: <i>Загрузка...</i>"
    if status == DownloadTaskStatus.PROCESSING:
        return "⚙️ Статус: <i>Обработка...</i>"
    if status == DownloadTaskStatus.SENDING:
        return "📤 Статус: <i>Отправка...</i>"
    if status == DownloadTaskStatus.COMPLETED:
        return "✅ Готово!"
    if status == DownloadTaskStatus.CANCELLED:
        return "🛑 Загрузка отменена."
    if status == DownloadTaskStatus.FAILED:
        return "❌ Произошла ошибка."
    return "❔ Неизвестный статус."


def build_format_chosen_message(fmt: MediaFormat) -> str:
    label = fmt.label
    return f"Вы выбрали: <b>{label}</b>\n"