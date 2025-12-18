from __future__ import annotations

import subprocess
from pathlib import Path


class MediaValidationError(RuntimeError):
    pass


class MediaValidator:
    """
    Validates final media file via ffprobe.
    """

    def validate(self, file_path: Path) -> None:
        if not file_path.exists():
            raise MediaValidationError("file not found")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            raise MediaValidationError("no video stream")

        cmd_audio = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(file_path),
        ]
        result_audio = subprocess.run(cmd_audio, capture_output=True, text=True)
        if result_audio.returncode != 0 or not result_audio.stdout.strip():
            raise MediaValidationError("no audio stream")