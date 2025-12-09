from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.services.models import MediaInfo, MediaType, FormatKind, MediaFormat


def build_formats_keyboard(info: MediaInfo, task_id: str) -> InlineKeyboardMarkup:
    video_buttons = []
    audio_buttons = []
    mp3_button: InlineKeyboardButton | None = None

    # Видео по разрешениям
    desired_heights = [144, 240, 360, 480, 720, 1080]
    used_heights: set[int] = set()

    def parse_height(fmt: MediaFormat) -> int | None:
        if not fmt.video_quality:
            return None
        if fmt.video_quality.endswith("p"):
            try:
                return int(fmt.video_quality[:-1])
            except ValueError:
                return None
        return None

    for h in desired_heights:
        best_fmt = None
        for f in info.formats:
            if f.media_type != MediaType.VIDEO or f.kind != FormatKind.VIDEO:
                continue
            height = parse_height(f)
            if height == h:
                best_fmt = f
                break
        if best_fmt:
            used_heights.add(h)
            video_buttons.append(
                InlineKeyboardButton(
                    text=f"{h}p",
                    callback_data=f"fmt:{task_id}:{best_fmt.id}",
                )
            )

    # Аудио битрейты
    desired_bitrates = [64, 128, 192, 320]
    used_bitrates: set[int] = set()

    for br in desired_bitrates:
        best_fmt = None
        for f in info.formats:
            if f.media_type != MediaType.AUDIO or f.kind == FormatKind.MP3:
                continue
            if not f.audio_bitrate_kbps:
                continue
            if abs(f.audio_bitrate_kbps - br) <= 16:
                best_fmt = f
                break
        if best_fmt:
            used_bitrates.add(br)
            audio_buttons.append(
                InlineKeyboardButton(
                    text=f"{br} kbps",
                    callback_data=f"fmt:{task_id}:{best_fmt.id}",
                )
            )

    # MP3
    for f in info.formats:
        if f.kind == FormatKind.MP3:
            mp3_button = InlineKeyboardButton(
                text="🎵 MP3",
                callback_data=f"fmt:{task_id}:{f.id}",
            )
            break

    rows = []
    # видео в несколько строк
    for btn in video_buttons:
        rows.append([btn])
    # mp3
    if mp3_button:
        rows.append([mp3_button])
    # аудио
    for btn in audio_buttons:
        rows.append([btn])

    return InlineKeyboardMarkup(inline_keyboard=rows)