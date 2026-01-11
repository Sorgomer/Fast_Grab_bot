from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class YdlConfig:
    """
    Centralized yt-dlp config.
    IMPORTANT: No postprocessors, no merge. Downloader/extractor only.
    """

    # Networking / robustness
    socket_timeout_sec: int = 30
    extract_timeout_sec: int = 15
    retries: int = 3

    # Behavior
    quiet: bool = True
    no_warnings: bool = True

    # Output
    restrict_filenames: bool = True

    # Extract
    extract_flat: bool = False