from functools import lru_cache
from typing import Optional
import os

from pydantic import HttpUrl, Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")

    # Webhook / web server
    webhook_url: HttpUrl = Field(alias="WEBHOOK_URL")
    webhook_path: str = Field(default="/webhook", alias="WEBHOOK_PATH")
    webapp_host: str = Field(default="0.0.0.0", alias="WEBAPP_HOST")
    webapp_port: int = Field(default_factory=lambda: int(os.getenv("PORT", 8000)), alias="PORT")

    # Redis
    redis_dsn: Optional[str] = Field(default=None, alias="REDIS_DSN")

    # Download / storage
    download_dir: str = Field(default="./downloads", alias="DOWNLOAD_DIR")
    max_file_size_mb: int = Field(default=1900, alias="MAX_FILE_SIZE_MB")

    # Rate limiting
    user_rate_limit: int = Field(default=5, alias="USER_RATE_LIMIT")
    user_rate_interval_sec: int = Field(default=60, alias="USER_RATE_INTERVAL_SEC")
    max_parallel_downloads_per_user: int = Field(
        default=2, alias="MAX_PARALLEL_DOWNLOADS_PER_USER"
    )
    max_global_downloads: int = Field(default=4, alias="MAX_GLOBAL_DOWNLOADS")

    # Tasks / cleanup
    task_ttl_sec: int = Field(default=3600, alias="TASK_TTL_SEC")
    cleanup_interval_sec: int = Field(default=1800, alias="CLEANUP_INTERVAL_SEC")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()