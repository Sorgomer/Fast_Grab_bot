import shutil
from pathlib import Path
from typing import Optional

from app.config.settings import get_settings
from app.services.models import DownloadTask


def get_base_download_dir() -> Path:
    settings = get_settings()
    base = Path(settings.download_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_task_dir(task: DownloadTask) -> Path:
    base = get_base_download_dir()
    task_dir = base / str(task.user_id) / task.id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def get_temp_file_path(task: DownloadTask, ext: str) -> Path:
    task_dir = get_task_dir(task)
    return task_dir / f"file.{ext}"


def remove_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def get_file_size(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    return path.stat().st_size