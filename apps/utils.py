"""Reusable helpers for IdeaMix."""

import re

TAG_SPLIT_RE = re.compile(r'[,;#]+')
TAG_CLEAN_RE = re.compile(r'[^\w\s\-+#.]', re.UNICODE)

_TRANSLITERATION = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g',
}


def transliterate(value: str) -> str:
    """Transliterate Cyrillic text so slugs stay readable and URL-safe."""
    return ''.join(_TRANSLITERATION.get(char.lower(), char) for char in value)


def split_tags(raw: str | None) -> list[str]:
    """Split a comma separated tag string into unique tags."""
    if not raw:
        return []
    seen: set[str] = set()
    tags: list[str] = []
    for chunk in TAG_SPLIT_RE.split(raw):
        tag = TAG_CLEAN_RE.sub('', chunk).strip().strip('.').lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag[:25])
    return tags


def normalize_tags(raw: str | None, max_tags: int = 5) -> str:
    """Return a canonical comma separated tag string."""
    return ', '.join(split_tags(raw)[:max_tags])


def compact_number(value) -> str:
    """Compact representation of large counters (1200 -> 1,2 тыс.)."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return '0'
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f}'.rstrip('0').rstrip('.').replace('.', ',') + ' млн'
    if value >= 1_000:
        return f'{value / 1_000:.1f}'.rstrip('0').rstrip('.').replace('.', ',') + ' тыс.'
    return str(value)
