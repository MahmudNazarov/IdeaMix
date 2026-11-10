"""Validation helpers for uploaded files and user-generated text."""

from pathlib import Path

from django.core.exceptions import ValidationError

from .profanity import validate_no_profanity

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _validate_image(value, max_mb: int) -> None:
    if not value:
        return
    extension = Path(value.name).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            'Поддерживаются только изображения JPG, PNG, WebP или GIF.'
        )
    if getattr(value, 'size', 0) > max_mb * 1024 * 1024:
        raise ValidationError(
            f'Файл слишком большой. Максимальный размер — {max_mb} МБ.'
        )
    content_type = getattr(value, 'content_type', '') or ''
    if content_type and not content_type.startswith('image/'):
        raise ValidationError('Загруженный файл не является изображением.')


def validate_cover_image(value) -> None:
    _validate_image(value, 5)


def validate_avatar(value) -> None:
    _validate_image(value, 2)
