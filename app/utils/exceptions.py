class AppError(Exception):
    """Базовое приложение-исключение."""


class ValidationError(AppError):
    pass


class UnsupportedPlatformError(AppError):
    pass


class TooManyRequestsError(AppError):
    pass


class DownloadError(AppError):
    pass


class FileTooLargeError(AppError):
    pass


class TaskNotFoundError(AppError):
    pass


class TaskCancelledError(AppError):
    pass