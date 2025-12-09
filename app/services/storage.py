from pathlib import Path

from app.services.models import DownloadTask
from app.utils.files import get_task_dir, remove_dir


def get_task_directory(task: DownloadTask) -> Path:
    return get_task_dir(task)


def cleanup_task_files(task: DownloadTask) -> None:
    task_dir = get_task_dir(task)
    remove_dir(task_dir)