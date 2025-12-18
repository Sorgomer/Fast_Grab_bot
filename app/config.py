
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


class SettingsError(RuntimeError):
    pass


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    v = value.strip()
    return v if v else None


def _env_int(name: str, *, default: int | None = None, min_value: int | None = None) -> int:
    raw = _env(name)
    if raw is None:
        if default is None:
            raise SettingsError(f"Missing required env var: {name}")
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise SettingsError(f"Invalid int for {name}: {raw!r}") from exc

    if min_value is not None and value < min_value:
        raise SettingsError(f"Env var {name} must be >= {min_value}, got {value}")
    return value


def _env_path(name: str, *, default: str | None = None) -> Path:
    raw = _env(name)
    if raw is None:
        if default is None:
            raise SettingsError(f"Missing required env var: {name}")
        raw = default
    return Path(raw).expanduser().resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str

    log_level: str
    temp_root: Path

    max_parallel_downloads: int
    queue_maxsize: int

    rate_limit_per_user: int
    rate_limit_window_sec: int

    # Telegram policy
    tg_hard_limit_mb: int           # theoretical Bot API ceiling (~2GB)
    tg_safe_limit_mb: int           # safe zone upper bound
    tg_risky_limit_mb: int          # risk zone upper bound
    tg_best_effort_from_mb: int     # >= this => best-effort (no guarantees)
    tg_document_only_from_mb: int   # >= this => send_document only

    # Stability
    max_active_jobs_per_user: int

    @classmethod
    def from_env(cls) -> "Settings":
        token = _env("BOT_TOKEN")
        if token is None:
            raise SettingsError("Missing required env var: BOT_TOKEN")

        log_level = (_env("LOG_LEVEL") or "INFO").upper()
        temp_root = _env_path("TEMP_ROOT", default="./.tmp")

        max_parallel_downloads = _env_int("MAX_PARALLEL_DOWNLOADS", default=2, min_value=1)
        queue_maxsize = _env_int("QUEUE_MAXSIZE", default=20, min_value=1)

        rate_limit_per_user = _env_int("RATE_LIMIT_PER_USER", default=6, min_value=1)
        rate_limit_window_sec = _env_int("RATE_LIMIT_WINDOW_SEC", default=10, min_value=1)

        tg_hard_limit_mb = _env_int("TG_HARD_LIMIT_MB", default=2000, min_value=100)
        tg_safe_limit_mb = _env_int("TG_SAFE_LIMIT_MB", default=900, min_value=50)
        tg_risky_limit_mb = _env_int("TG_RISKY_LIMIT_MB", default=1500, min_value=100)
        tg_best_effort_from_mb = _env_int("TG_BEST_EFFORT_FROM_MB", default=1500, min_value=100)
        tg_document_only_from_mb = _env_int("TG_DOCUMENT_ONLY_FROM_MB", default=300, min_value=50)

        max_active_jobs_per_user = _env_int("MAX_ACTIVE_JOBS_PER_USER", default=1, min_value=1)

        s = cls(
            bot_token=token,
            log_level=log_level,
            temp_root=temp_root,
            max_parallel_downloads=max_parallel_downloads,
            queue_maxsize=queue_maxsize,
            rate_limit_per_user=rate_limit_per_user,
            rate_limit_window_sec=rate_limit_window_sec,
            tg_hard_limit_mb=tg_hard_limit_mb,
            tg_safe_limit_mb=tg_safe_limit_mb,
            tg_risky_limit_mb=tg_risky_limit_mb,
            tg_best_effort_from_mb=tg_best_effort_from_mb,
            tg_document_only_from_mb=tg_document_only_from_mb,
            max_active_jobs_per_user=max_active_jobs_per_user,
        )
        s._validate()
        return s

    def _validate(self) -> None:
        allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if self.log_level not in allowed_levels:
            raise SettingsError(f"Invalid LOG_LEVEL={self.log_level!r}. Allowed: {sorted(allowed_levels)}")
        if not self.bot_token or ":" not in self.bot_token:
            raise SettingsError("BOT_TOKEN looks invalid (expected Telegram token format)")
        if self.temp_root.name == "":
            raise SettingsError("TEMP_ROOT must be a directory path, got empty name")

        if self.tg_safe_limit_mb >= self.tg_hard_limit_mb:
            raise SettingsError("TG_SAFE_LIMIT_MB must be < TG_HARD_LIMIT_MB")
        if self.tg_risky_limit_mb > self.tg_hard_limit_mb:
            raise SettingsError("TG_RISKY_LIMIT_MB must be <= TG_HARD_LIMIT_MB")
        if self.tg_best_effort_from_mb > self.tg_hard_limit_mb:
            raise SettingsError("TG_BEST_EFFORT_FROM_MB must be <= TG_HARD_LIMIT_MB")
        if self.tg_document_only_from_mb <= 0:
            raise SettingsError("TG_DOCUMENT_ONLY_FROM_MB must be > 0")
