from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class YdlConfig:
    # Networking / robustness
    socket_timeout_sec: int = 30
    extract_timeout_sec: int = 15
    download_timeout_sec: int = 3600  # 60 минут на stream-download
    retries: int = 3

    # Behavior
    quiet: bool = True
    no_warnings: bool = True

    # Output
    restrict_filenames: bool = True

    # Extract
    extract_flat: bool = False