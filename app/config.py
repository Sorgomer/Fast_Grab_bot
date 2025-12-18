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
    p = Path(raw).expanduser().resolve()
    return p


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str

    log_level: str
    temp_root: Path

    max_parallel_downloads: int
    queue_maxsize: int

    rate_limit_per_user: int
    rate_limit_window_sec: int

    telegram_max_file_mb: int

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

        telegram_max_file_mb = _env_int("TELEGRAM_MAX_FILE_MB", default=49, min_value=1)

        s = cls(
            bot_token=token,
            log_level=log_level,
            temp_root=temp_root,
            max_parallel_downloads=max_parallel_downloads,
            queue_maxsize=queue_maxsize,
            rate_limit_per_user=rate_limit_per_user,
            rate_limit_window_sec=rate_limit_window_sec,
            telegram_max_file_mb=telegram_max_file_mb,
        )
        s._validate()
        return s

    def _validate(self) -> None:
        allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if self.log_level not in allowed_levels:
            raise SettingsError(
                f"Invalid LOG_LEVEL={self.log_level!r}. Allowed: {sorted(allowed_levels)}"
            )
        if not self.bot_token or ":" not in self.bot_token:
            raise SettingsError("BOT_TOKEN looks invalid (expected Telegram token format)")

        # Temp root must be a directory path we can create later in startup preflight
        if self.temp_root.name == "":
            raise SettingsError("TEMP_ROOT must be a directory path, got empty name")