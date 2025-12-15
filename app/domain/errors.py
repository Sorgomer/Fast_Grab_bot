from __future__ import annotations


class DomainError(Exception):
    """Base domain error shown to user as friendly message."""


class UnsupportedPlatformError(DomainError):
    pass


class ExtractionError(DomainError):
    pass


class DownloadError(DomainError):
    pass


class MergeError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class QueueFullError(DomainError):
    pass