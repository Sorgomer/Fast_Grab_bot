from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile

from app.config import AppConfig, build_config
from app.infrastructure.download_queue import DownloadQueue
from app.infrastructure.yt.ydl_client import YdlClient
from app.infrastructure.ffmpeg.ffmpeg import Ffmpeg
from app.infrastructure.media_validator import MediaValidator
from app.infrastructure.platform_detector import PlatformDetector
from app.infrastructure.session_store import SessionStore
from app.infrastructure.yt.ydl_process import YdlProcessRunner, YdlProcessSpec
from app.presentation.routers.common import router as common_router
from app.presentation.routers.download import router as download_router, DownloadDeps
from app.domain.errors import DomainError, DownloadError, ExtractionError, MergeError, ValidationError
from app.domain.models import Container, DownloadJob, MediaKind, Platform


@dataclass(frozen=True)
class App:
    config: AppConfig
    bot: Bot
    dp: Dispatcher
    queue: DownloadQueue


def build_app() -> App:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required in environment.")

    cfg = build_config(token)
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.downloads_dir.mkdir(parents=True, exist_ok=True)
    cfg.temp_dir.mkdir(parents=True, exist_ok=True)

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    detector = PlatformDetector()
    sessions = SessionStore(ttl_sec=20 * 60)
    ffmpeg = Ffmpeg(ffmpeg_path=cfg.ffmpeg_path)
    validator = MediaValidator(ffprobe_path=cfg.ffprobe_path, max_file_mb=cfg.max_file_mb)

    ydl = YdlClient(
        temp_dir=cfg.temp_dir,
        socket_timeout_sec=cfg.ydl_socket_timeout_sec,
        retries=cfg.ydl_retries,
    )
    async def job_handler(job: DownloadJob) -> None:
        await _process_job(
            bot=bot,
            cfg=cfg,
            ffmpeg=ffmpeg,
            validator=validator,
            job=job,
            queue=queue,
        )

    queue = DownloadQueue(
        maxsize=cfg.queue_maxsize,
        workers=cfg.workers,
        handler=job_handler,
    )

    deps = DownloadDeps(
        detector=detector,
        ydl=ydl,
        sessions=sessions,
        enqueue_job=queue.try_enqueue,
    )

    dp.include_router(common_router)
    dp.include_router(download_router)

    # Provide deps via middleware-less approach: aiogram 3 allows dependency injection via handler args
    # by setting in Dispatcher context:
    dp["deps"] = deps

    return App(config=cfg, bot=bot, dp=dp, queue=queue)


async def _process_job(
    bot: Bot,
    cfg: AppConfig,
    ffmpeg: Ffmpeg,
    validator: MediaValidator,
    job: DownloadJob,
    queue: DownloadQueue,
) -> None:
    from aiogram.exceptions import TelegramBadRequest

    def _container_for_video(codec_family: str) -> Container:
        # Conservative: H264 -> mp4, others -> mkv (wide compatibility for merged streams)
        return Container.MP4 if codec_family.lower() == "h264" else Container.MKV

    async def _edit(text: str) -> None:
        try:
            await bot.edit_message_text(
                chat_id=job.chat_id,
                message_id=int(job.status_message_id),
                text=text,
            )
        except TelegramBadRequest:
            return

    # paths
    base = cfg.temp_dir / f"user_{int(job.user_id)}"
    base.mkdir(parents=True, exist_ok=True)

    video_path = base / "video.bin"
    audio_path = base / "audio.bin"

    out_name = "result"
    out_base = cfg.downloads_dir / f"user_{int(job.user_id)}"
    out_base.mkdir(parents=True, exist_ok=True)

    try:
        if job.option.kind == MediaKind.VIDEO:
            if job.option.video is None:
                raise DownloadError("Некорректный выбор формата.")

            v = job.option.video
            platform = job.platform
            if platform in (Platform.VK, Platform.RUTUBE):
                await _edit("⬇️ Скачиваю видео…")

                runner = YdlProcessRunner(
                    YdlProcessSpec(
                        executable="yt-dlp",
                        args=[
                            "--no-playlist",
                            "--no-warnings",
                            "--newline",
                            "--progress",
                            "--restrict-filenames",
                            "--user-agent", "Mozilla/5.0",
                            "--referer", job.url,
                            "--cookies-from-browser", "chrome",
                            "-f", "bv*+ba/b",
                            "-o", str(out_base / f"{out_name}.mp4"),
                            job.url,
                        ],
                        workdir=out_base,
                    )
                )

                queue._active_runners.add(runner)
                try:
                    await runner.start()
                    await runner.wait()
                finally:
                    queue._active_runners.discard(runner)

                merged_path = out_base / f"{out_name}.mp4"

                if not merged_path.exists():
                    raise DownloadError("Видео не было скачано.")

                await _edit("🔎 Проверяю результат…")

                max_mb = cfg.max_file_mb
                size_mb = merged_path.stat().st_size / (1024 * 1024)
                if size_mb > max_mb:
                    raise ValidationError(
                        f"Файл слишком большой для Telegram ({size_mb:.1f} МБ). "
                        f"Выберите качество ниже (≤ {max_mb} МБ)."
                    )

                await validator.validate_video_file(merged_path)

                await _edit("📤 Отправляю…")
                await bot.send_video(
                    chat_id=job.chat_id,
                    video=FSInputFile(merged_path),
                    caption="Готово ✅",
                    supports_streaming=True,
                )
                await _edit("✅ Готово.")
                return
            else:
                await _edit("⬇️ Скачиваю видеопоток…")
                runner = YdlProcessRunner(
                    YdlProcessSpec(
                        executable="yt-dlp",
                        args=[
                            "--no-playlist",
                            "--no-warnings",
                            "--newline",
                            "--progress",
                            "--restrict-filenames",
                            "--user-agent", "Mozilla/5.0",
                            "--referer", job.url,
                            "-f", v.video_format_id,
                            "-o", str(video_path),
                            job.url,
                        ],
                        workdir=video_path.parent,
                    )
                )

                queue._active_runners.add(runner)
                try:
                    await runner.start()
                    await runner.wait()
                finally:
                    queue._active_runners.discard(runner)

                await _edit("⬇️ Скачиваю аудиопоток…")
                audio_runner = YdlProcessRunner(
                    YdlProcessSpec(
                        executable="yt-dlp",
                        args=[
                            "--no-playlist",
                            "--no-warnings",
                            "--newline",
                            "--progress",
                            "--restrict-filenames",
                            "--user-agent", "Mozilla/5.0",
                            "--referer", job.url,
                            "-f", v.audio_format_id,
                            "-o", str(audio_path),
                            job.url,
                        ],
                        workdir=audio_path.parent,
                    )
                )

                queue._active_runners.add(audio_runner)
                try:
                    await audio_runner.start()
                    await audio_runner.wait()
                finally:
                    queue._active_runners.discard(audio_runner)

                container = _container_for_video(v.codec.value)
                merged_path = out_base / f"{out_name}.{container.ext}"

                await _edit("🎬 Собираю файл (ffmpeg merge)…")
                await ffmpeg.merge_av(video_path, audio_path, merged_path.with_suffix(""), container)

                if not merged_path.exists():
                    raise MergeError(f"Результирующий файл не найден: {merged_path}")
                if merged_path.stat().st_size <= 0:
                    raise MergeError("Результирующий файл пустой.")

                await _edit("🔎 Проверяю результат…")
                await validator.validate_video_file(merged_path)

                max_mb = cfg.max_file_mb
                size_mb = merged_path.stat().st_size / (1024 * 1024)
                if size_mb > max_mb:
                    raise ValidationError(
                        f"Файл слишком большой для Telegram ({size_mb:.1f} МБ). "
                        f"Выберите качество ниже (≤ {max_mb} МБ)."
                    )

                await _edit("📤 Отправляю…")
                await bot.send_video(
                    chat_id=job.chat_id,
                    video=FSInputFile(merged_path),
                    caption="Готово ✅",
                    supports_streaming=True,
                )
                await _edit("✅ Готово.")

        elif job.option.kind == MediaKind.MP3:
            if job.platform != Platform.YOUTUBE:
                raise DownloadError("MP3 доступен только для YouTube.")
            if job.option.mp3 is None:
                raise DownloadError("Некорректный выбор формата.")

            a = job.option.mp3
            await _edit("⬇️ Скачиваю аудио…")
            audio_runner = YdlProcessRunner(
                YdlProcessSpec(
                    executable="yt-dlp",
                    args=[
                        "--no-playlist",
                        "--no-warnings",
                        "--newline",
                        "--progress",
                        "--restrict-filenames",
                        "--user-agent", "Mozilla/5.0",
                        "--referer", job.url,
                        "-f", a.audio_format_id,
                        "-o", str(audio_path),
                        job.url,
                    ],
                    workdir=audio_path.parent,
                )
            )

            queue._active_runners.add(audio_runner)
            try:
                await audio_runner.start()
                await audio_runner.wait()
            finally:
                queue._active_runners.discard(audio_runner)

            mp3_path = out_base / f"{out_name}.mp3"
            await _edit("🎵 Конвертирую в MP3 (ffmpeg)…")
            await ffmpeg.to_mp3(audio_path, mp3_path.with_suffix(""), a.bitrate_kbps)

            await _edit("🔎 Проверяю MP3…")
            await validator.validate_mp3_file(mp3_path)

            await _edit("📤 Отправляю…")
            await bot.send_audio(chat_id=job.chat_id, audio=FSInputFile(mp3_path), caption="Готово ✅")
            await _edit("✅ Готово.")
        else:
            raise DownloadError("Неизвестный тип медиа.")

    except DomainError as e:
        await _edit(f"⛔ {str(e)}")
    except TelegramBadRequest as e:
        await _edit("⛔ Telegram отклонил файл. Попробуйте другое качество.")
    except Exception as e:
        import logging
        logging.exception("Unexpected error during download/send")
        await _edit("⛔ Неожиданная ошибка при скачивании. Попробуйте другой формат или ссылку.")
    finally:
        # best-effort cleanup
        for p in (video_path, audio_path):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass