from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.domain.models import FormatChoice, Platform


@dataclass(frozen=True, slots=True)
class ParsedLinkDTO:
    url: str
    platform: Platform


@dataclass(frozen=True, slots=True)
class FormatListDTO:
    platform: Platform
    choices: list[FormatChoice]
    session_version: int


@dataclass(frozen=True, slots=True)
class EnqueueResultDTO:
    accepted: bool
    message: str


@dataclass(frozen=True, slots=True)
class CancelResultDTO:
    cancelled: bool
    message: str