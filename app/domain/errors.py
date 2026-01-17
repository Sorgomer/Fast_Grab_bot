from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainError(Exception):
    """
    Domain-level exception that is safe to show to user.
    Never includes stack traces or internal details.
    """
    user_message: str


@dataclass(frozen=True, slots=True)
class ValidationError(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class UnsupportedPlatformError(DomainError):
    pass

class JobCancelledError(Exception):
    """Raised when a user cancels an in-flight or queued download job."""
    pass