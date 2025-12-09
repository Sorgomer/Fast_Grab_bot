from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

import yt_dlp

from app.services.models import MediaInfo, MediaFormat, MediaType, FormatKind, DownloadTask
from app.utils.yt_dlp_config import build_extract_opts, build_download_opts
from app.utils.exceptions import DownloadError
from app.utils.files import get_base_download_dir


class BasePlatformDownloader(ABC):
    @abstractmethod
    async def extract_info(self, url: str) -> MediaInfo:
        ...

    @abstractmethod
    async def download(self, task: DownloadTask) -> Path:
        ...


class YtDlpPlatformDownloader(BasePlatformDownloader):
    def __init__(self, platform):
        self.platform = platform

    async def extract_info(self, url: str) -> MediaInfo:
        base_dir = get_base_download_dir()
        opts = build_extract_opts(base_dir)

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False, process=False)

        try:
            info = await asyncio.to_thread(_extract)
        except Exception as e:
            raise DownloadError(f"Не удалось получить информацию: {e!r}")

        if "_type" in info and info["_type"] == "playlist":
            info = info["entries"][0]

        title = info.get("title") or "Без названия"
        thumbnail = info.get("thumbnail")
        duration = info.get("duration")

        formats: list[MediaFormat] = []

        for f in info.get("formats", []):
            format_id = f.get("format_id")
            ext = f.get("ext")
            if not format_id or not ext:
                continue

            vcodec = f.get("vcodec")
            acodec = f.get("acodec")

            height = f.get("height")
            abr = f.get("abr")
            filesize = f.get("filesize") or f.get("filesize_approx")

            if vcodec != "none":
                label = f"{height}p" if height else f.get("format_note") or "video"
                formats.append(
                    MediaFormat(
                        id=format_id,
                        label=label,
                        media_type=MediaType.VIDEO,
                        kind=FormatKind.VIDEO,
                        filesize=filesize,
                        ext=ext,
                        video_quality=label,
                    )
                )
            elif acodec != "none":
                bitrate = int(abr) if abr else None
                kbps_label = f"{bitrate} kbps" if bitrate else "audio"
                formats.append(
                    MediaFormat(
                        id=format_id,
                        label=kbps_label,
                        media_type=MediaType.AUDIO,
                        kind=FormatKind.AUDIO,
                        filesize=filesize,
                        ext=ext,
                        audio_bitrate_kbps=bitrate,
                    )
                )

        if formats:
            formats.append(
                MediaFormat(
                    id="mp3",
                    label="MP3 192 kbps",
                    media_type=MediaType.AUDIO,
                    kind=FormatKind.MP3,
                    filesize=None,
                    ext="mp3",
                    audio_bitrate_kbps=192,
                )
            )

        return MediaInfo(
            platform=self.platform,
            url=url,
            title=title,
            thumbnail=thumbnail,
            duration=duration,
            formats=formats,
        )

    async def download(self, task: DownloadTask) -> Path:
        from app.utils.files import get_task_dir

        task_dir = get_task_dir(task)
        to_mp3 = task.format.kind == FormatKind.MP3
        audio_only = task.format.media_type == MediaType.AUDIO or to_mp3

        opts = build_download_opts(
            task_dir,
            None if to_mp3 or audio_only else task.format.id,
            audio_only=audio_only,
            to_mp3=to_mp3,
        )

        def _download():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(task.url, download=True)

        try:
            info = await asyncio.to_thread(_download)
        except Exception as e:
            raise DownloadError(f"Ошибка загрузки: {e!r}")

        video_id = info.get("id")
        ext = "mp3" if to_mp3 else info.get("ext", task.format.ext or "mp4")

        file_path = task_dir / f"{video_id}.{ext}"
        if not file_path.exists():
            for p in task_dir.iterdir():
                if p.is_file():
                    file_path = p
                    break

        if not file_path.exists():
            raise DownloadError("Файл не найден после загрузки")

        return file_path