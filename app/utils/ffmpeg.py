import asyncio
from pathlib import Path

from loguru import logger


async def run_ffmpeg(args: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    code = await process.wait()
    if code != 0:
        logger.error(f"ffmpeg exited with code {code}")
        raise RuntimeError("ffmpeg error")


async def ensure_mp3(input_path: Path, bitrate_kbps: int = 192) -> Path:
    output_path = input_path.with_suffix(".mp3")
    args = [
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ab",
        f"{bitrate_kbps}k",
        "-ar",
        "44100",
        "-f",
        "mp3",
        str(output_path),
    ]
    await run_ffmpeg(args)
    return output_path