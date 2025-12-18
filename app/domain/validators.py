from __future__ import annotations

from .errors import ValidationError
from .models import FormatChoice, JobStage


_ALLOWED_TRANSITIONS: dict[JobStage, set[JobStage]] = {
    JobStage.QUEUED: {JobStage.ANALYZING, JobStage.CANCELED, JobStage.FAILED},
    JobStage.ANALYZING: {JobStage.DOWNLOADING, JobStage.CANCELED, JobStage.FAILED},
    JobStage.DOWNLOADING: {JobStage.MERGING, JobStage.CANCELED, JobStage.FAILED},
    JobStage.MERGING: {JobStage.VALIDATING, JobStage.CANCELED, JobStage.FAILED},
    JobStage.VALIDATING: {JobStage.SENDING, JobStage.CANCELED, JobStage.FAILED},
    JobStage.SENDING: {JobStage.DONE, JobStage.FAILED},
    JobStage.DONE: set(),
    JobStage.FAILED: set(),
    JobStage.CANCELED: set(),
}


def validate_url(url: str) -> None:
    u = url.strip()
    if not u:
        raise ValidationError("Пустая ссылка.")
    if not (u.startswith("http://") or u.startswith("https://")):
        raise ValidationError("Ссылка должна начинаться с http:// или https://")
    if " " in u:
        raise ValidationError("Ссылка не должна содержать пробелы.")


def validate_choice(choice: FormatChoice) -> None:
    if not choice.choice_id.strip():
        raise ValidationError("Внутренняя ошибка: пустой идентификатор формата.")
    if not choice.label.strip():
        raise ValidationError("Внутренняя ошибка: пустая метка формата.")

    if choice.height <= 0:
        raise ValidationError("Внутренняя ошибка: некорректное разрешение.")
    if choice.fps_int < 0:
        raise ValidationError("Внутренняя ошибка: некорректный FPS.")

    if not choice.video.fmt.extractor_format_id.strip():
        raise ValidationError("Внутренняя ошибка: отсутствует video format id.")
    if not choice.audio.fmt.extractor_format_id.strip():
        raise ValidationError("Внутренняя ошибка: отсутствует audio format id.")


def validate_transition(old: JobStage, new: JobStage) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(old)
    if allowed is None:
        raise ValidationError("Внутренняя ошибка: неизвестная стадия.")
    if new not in allowed:
        raise ValidationError("Внутренняя ошибка: запрещённый переход статуса.")