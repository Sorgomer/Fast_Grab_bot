from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import ValidationError


log = logging.getLogger(__name__)


async def _run_capture(cmd: list[str]) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    out = (stdout or b"").decode("utf-8", errors="ignore")
    err = (stderr or b"").decode("utf-8", errors="ignore")
    return proc.returncode, out + "\n" + err


@dataclass(frozen=True)
class MediaValidator:
    ffprobe_path: str
    max_file_mb: int

    async def validate_file_exists(self, path: Path) -> None:
        if not path.exists():
            raise ValidationError("Файл не создан. Попробуйте другой формат.")
        size = path.stat().st_size
        if size <= 0:
            raise ValidationError("Файл получился пустым. Попробуйте другой формат.")
        if size > self.max_file_mb * 1024 * 1024:
            raise ValidationError("Файл слишком большой для отправки ботом. Выберите меньший формат.")

    async def validate_video_file(self, path: Path) -> None:
        await self.validate_file_exists(path)
        code, text = await _run_capture([
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=nw=1",
            str(path),
        ])
        if code != 0:
            log.warning("ffprobe error: %s", text[:2000])
            raise ValidationError("Не удалось проверить файл. Попробуйте другой формат.")

        has_video = "codec_type=video" in text
        has_audio = "codec_type=audio" in text
        if not has_video or not has_audio:
            raise ValidationError("Файл некорректный (нет видео или аудио). Выберите другой формат.")

    async def validate_mp3_file(self, path: Path) -> None:
        await self.validate_file_exists(path)
        code, text = await _run_capture([
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=nw=1",
            str(path),
        ])
        if code != 0:
            log.warning("ffprobe error: %s", text[:2000])
            raise ValidationError("Не удалось проверить MP3. Попробуйте другой формат.")
        if "codec_type=audio" not in text:
            raise ValidationError("MP3 некорректен. Попробуйте другой формат.")