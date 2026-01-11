
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Protocol, runtime_checkable

from aiogram import Bot

from .config import Settings
from .constants import APP_NAME
from .domain.policies import TelegramLimits
from .infrastructure.active_jobs import ActiveJobsRegistry
from .infrastructure.rate_limiter import RateLimiter
from .infrastructure.session_store import SessionStore
from .infrastructure.temp_storage import TempStorage
from .infrastructure.telegram_sender import TelegramSender
from .infrastructure.yt import YdlClient, YdlConfig
from .infrastructure.ffmpeg import FfmpegMerger, FfprobeClient
from .infrastructure.platform_detector import PlatformDetector
from .infrastructure.platforms import PlatformRegistry, YouTubeAdapter, VkAdapter, RutubeAdapter
from .infrastructure.download_queue import DownloadQueue
from .application.services import DownloadService
from .application.use_cases.parse_link import ParseLinkUseCase
from .application.use_cases.get_formats import GetFormatsUseCase
from .application.use_cases.enqueue_download import EnqueueDownloadUseCase
from .application.use_cases.cancel_download import CancelDownloadUseCase
from .application.use_cases.retry_download import RetryDownloadUseCase


class DIError(RuntimeError):
    pass


@runtime_checkable
class AsyncStartStop(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class RateLimiterPort(Protocol):
    def allow(self, user_id: int) -> bool: ...


@dataclass(slots=True)
class Container:
    settings: Settings
    logger: logging.Logger
    _components: dict[str, Any]

    @classmethod
    def build(cls) -> "Container":
        settings = Settings.from_env()
        logger = logging.getLogger(APP_NAME)
        return cls(settings=settings, logger=logger, _components={})

    def register(self, name: str, component: Any) -> None:
        if name in self._components:
            raise DIError(f"Component already registered: {name}")
        self._components[name] = component

    def get(self, name: str) -> Any:
        try:
            return self._components[name]
        except KeyError as exc:
            raise DIError(f"Unknown component: {name}") from exc

    def all_components(self) -> list[tuple[str, Any]]:
        return list(self._components.items())


def build_graph(container: Container) -> None:
    s = container.settings

    tg_limits = TelegramLimits(
        hard_bytes=s.tg_hard_limit_mb * 1024 * 1024,
        safe_bytes=s.tg_safe_limit_mb * 1024 * 1024,
        risky_bytes=s.tg_risky_limit_mb * 1024 * 1024,
        best_effort_from_bytes=s.tg_best_effort_from_mb * 1024 * 1024,
    )

    session_store = SessionStore()
    rate_limiter: RateLimiterPort = RateLimiter(limit=s.rate_limit_per_user, window_sec=s.rate_limit_window_sec)
    active_jobs = ActiveJobsRegistry(max_active_per_user=s.max_active_jobs_per_user)

    temp_storage = TempStorage(root=s.temp_root)

    ydl = YdlClient(cfg=YdlConfig())
    ffmpeg = FfmpegMerger()
    ffprobe = FfprobeClient()

    detector = PlatformDetector()
    yt_adapter = YouTubeAdapter(ydl=ydl, tg_limits=tg_limits)
    vk_adapter = VkAdapter(ydl=ydl, tg_limits=tg_limits)
    rutube_adapter = RutubeAdapter(ydl=ydl, tg_limits=tg_limits)
    registry = PlatformRegistry(youtube=yt_adapter, vk=vk_adapter, rutube=rutube_adapter)

    bot = Bot(token=s.bot_token)

    sender = TelegramSender(
        bot=bot,
        hard_limit_mb=s.tg_hard_limit_mb,
        document_only_from_mb=s.tg_document_only_from_mb,
    )

    downloads = DownloadService(
        temp_storage=temp_storage,
        ydl=ydl,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        telegram_sender=sender,
        active_jobs=active_jobs,
        tg_hard_limit_bytes=tg_limits.hard_bytes,
    )

    queue = DownloadQueue(
        maxsize=s.queue_maxsize,
        workers=s.max_parallel_downloads,
        handler=downloads.handle_job,
    )

    parse_link = ParseLinkUseCase(detector=detector)
    get_formats = GetFormatsUseCase(registry=registry, sessions=session_store)
    enqueue = EnqueueDownloadUseCase(sessions=session_store, queue=queue, downloads=downloads, active_jobs=active_jobs)
    cancel = CancelDownloadUseCase(downloads=downloads)
    retry = RetryDownloadUseCase()

    container.register("bot", bot)
    container.register("telegram_sender", sender)

    container.register("session_store", session_store)
    container.register("rate_limiter", rate_limiter)
    container.register("temp_storage", temp_storage)
    container.register("active_jobs", active_jobs)

    container.register("download_service", downloads)
    container.register("download_queue", queue)

    container.register("parse_link_uc", parse_link)
    container.register("get_formats_uc", get_formats)
    container.register("enqueue_download_uc", enqueue)
    container.register("cancel_download_uc", cancel)
    container.register("retry_download_uc", retry)
