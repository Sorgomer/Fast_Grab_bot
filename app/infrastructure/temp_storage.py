from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict


class TempStorageError(RuntimeError):
    pass


class TempStorage:
    """
    Manages temp directories per job.
    """

    def __init__(self, *, root: Path) -> None:
        self._root = root
        self._allocated: Dict[str, Path] = {}

    async def start(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

        # Cleanup leftovers from previous runs (crash/restart). Best-effort.
        try:
            for child in self._root.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
                except Exception:
                    continue
        except Exception:
            # Root might be missing or inaccessible; ignore at startup.
            pass

    async def stop(self) -> None:
        # best-effort cleanup
        for p in list(self._allocated.values()):
            shutil.rmtree(p, ignore_errors=True)
        self._allocated.clear()

    def allocate(self, job_id: str) -> Path:
        if job_id in self._allocated:
            raise TempStorageError("temp dir already allocated")

        path = self._root / job_id
        path.mkdir(parents=True, exist_ok=False)
        self._allocated[job_id] = path
        return path

    def cleanup(self, job_id: str) -> None:
        path = self._allocated.pop(job_id, None)
        if path is not None:
            shutil.rmtree(path, ignore_errors=True)