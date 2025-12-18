from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import FormatChoice


class AbstractPlatformAdapter(ABC):
    """
    Adapter contract for a platform.
    """

    @abstractmethod
    async def extract_choices(self, url: str) -> list[FormatChoice]:
        """
        Extract and build deduplicated format choices for the given URL.
        Must raise DomainError / ValidationError for user-safe failures.
        """
        raise NotImplementedError