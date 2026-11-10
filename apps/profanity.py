"""Profanity detection used to keep public content readable.

The filter is deliberately pragmatic rather than exhaustive:

* Russian obscenities are matched by roots so inflected forms are covered.
* Common obfuscation is normalised first: ``ё`` → ``е``, Latin look-alikes,
  digit/symbol substitutions, inserted punctuation and repeated letters.
* A short list of English words and Latin transliterations is checked as well.

The goal is to stop obvious abuse without blocking legitimate words such as
«хлеб», «себе», «небо», «сукно», «бляха» or «команда».
"""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError

PROFANITY_MESSAGE = (
    'В тексте есть нецензурная лексика. Переформулируйте без мата — '
    'после этого материал можно будет опубликовать.'
)

# Characters that are unambiguously used instead of Cyrillic letters.
_LEET_TRANSLATION = str.maketrans(
    {
        '0': 'о',
        '6': 'б',
        '7': 'т',
        '8': 'в',
        '9': 'д',
        '$': 'с',
        '!': 'и',
        '|': 'и',
        '*': '',
        'ё': 'е',
    }
)

# Ambiguous substitutions: a character can stand for more than one letter.
# Every combination is checked, but the number of variants is capped.
_AMBIGUOUS_SUBSTITUTIONS = (
    ('@', ('а', 'я')),
    ('3', ('з', 'е')),
    ('4', ('ч', 'а')),
    ('1', ('и', 'л')),
)

# Latin letters that look like Cyrillic ones in obfuscated writing.
_LOOKALIKE_MAP = {
    'a': 'а',
    'b': 'в',
    'c': 'с',
    'd': 'д',
    'e': 'е',
    'f': 'ф',
    'g': 'г',
    'h': 'н',
    'i': 'и',
    'j': 'й',
    'k': 'к',
    'l': 'л',
    'm': 'м',
    'n': 'п',
    'o': 'о',
    'p': 'р',
    'q': 'к',
    'r': 'р',
    's': 'с',
    't': 'т',
    'u': 'у',
    'v': 'в',
    'w': 'в',
    'x': 'х',
    'y': 'у',
    'z': 'з',
}

_LOOKALIKE_TRANSLATION = str.maketrans(_LOOKALIKE_MAP)

# «u» is sometimes typed instead of «и» inside a Russian word (пuздa).
_LOOKALIKE_TRANSLATION_ALT = str.maketrans({**_LOOKALIKE_MAP, 'u': 'и'})

# Prefixes that can precede an «еб» root without a hard sign.
_EB_PREFIXES = (
    'недо',
    'пере',
    'про',
    'при',
    'вы',
    'за',
    'на',
    'по',
    'до',
    'из',
    'ис',
    'у',
)

# Prefixes that need a hard sign before the root (съебал, разъебать…).
_EB_HARD_PREFIXES = ('раз', 'под', 'от', 'об', 'вз', 'из', 'с', 'в')

_EB_SUFFIXES = (
    'ать',
    'ала',
    'ало',
    'али',
    'ана',
    'ано',
    'ани',
    'ану',
    'анут',
    'ацк',
    'учи',
    'учк',
    'ись',
    'ланк',
    'ство',
    'ище',
    'ырь',
    'ал',
    'ан',
    'ат',
    'ац',
    'уч',
    'ет',
    'ут',
    'утс',
    'лан',
    'ло',
    'ля',
    'ну',
    'нул',
    'ши',
    'ок',
    'а',
    'у',
    'и',
    'о',
    'ы',
)

_EB_PREFIX_PATTERN = '|'.join(
    re.escape(prefix)
    for prefix in sorted(_EB_PREFIXES, key=len, reverse=True)
)
_EB_HARD_PREFIX_PATTERN = '|'.join(
    re.escape(prefix)
    for prefix in sorted(_EB_HARD_PREFIXES, key=len, reverse=True)
)
_EB_SUFFIX_PATTERN = '|'.join(
    re.escape(suffix)
    for suffix in sorted(_EB_SUFFIXES, key=len, reverse=True)
)

_RU_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        # хуй, хуя, хую, хуе, хуи, нахуй, похуй…
        r'ху[йяеуюи]',
        # пизда, пиздец, пиздить, распиздяй…
        r'пизд',
        # бля, блядь, блядский; «бляха», «бляшка», «блямба» исключены.
        r'бля(?!х|ш|мб)',
        # сука, суку, сукой, сукин, сучка, сучара (но не «сукно»).
        r'сук(?:а|у|е|ой|ин)|суч(?:к|ар|ан)',
        # мудак, мудачизм, мудила, мудозвон.
        r'мудак|мудач|мудил|мудозвон',
        # пидор, пидар, пидер, педик, пидорас.
        r'пидор|пидар|пидер|педик|пидр',
        r'гандон|гондон',
        r'залуп',
        r'дроч',
        r'жоп',
        r'говн',
        # срать, срал, срака, срач, срут (но не «сразу», «сравнить»).
        r'срать|срал|срака|срач|срут|срущ',
        # херня, херов, похер, нахер (сам «хер» проверяется отдельно).
        r'херн|херов|похер|нахер|хере',
        r'шлюх',
        r'ублюд',
        r'мраз',
        r'падл',
        # долбоёб и подобные, где корень стоит в середине слова.
        r'долбоеб',
        # Производные от «ебать»: заебал, выёбываться, уебище, еблан…
        rf'(?:^|(?:{_EB_PREFIX_PATTERN}))(?:еб)(?:{_EB_SUFFIX_PATTERN})',
        # Формы с твёрдым знаком: съебал, разъебать, подъебнуть…
        rf'(?:{_EB_HARD_PREFIX_PATTERN})ъ(?:еб)',
    )
]

# Short words and ambiguous stems that are only obscene as a whole token.
_RU_EXACT = {
    'хер',
    'манда',
    'манде',
    'манду',
    'мандой',
    'манды',
    'мандам',
    'мандами',
    'мандах',
    'суки',
    'сукам',
    'суках',
    'суками',
    'чмо',
    'падла',
    'падло',
}

# Latin transliterations of Russian obscenities.
_LATIN_PATTERN = re.compile(
    r'\b(?:'
    r'huy\w*|hui\w*|huylo\w*|'
    r'pizd\w*|'
    r'blya(?:d|t)\w*|'
    r'(?:za|na|u|y|vye|vyo|po|pro|do|pere|pri)?y?eb\w*|'
    r'ebat\w*|ebal\w*|eblan\w*|'
    r'suka(?:chka)?\w*|suchka\w*|'
    r'mudak\w*|mudil\w*|'
    r'pidor\w*|pidar\w*|pidr\w*|'
    r'govn\w*|zhop\w*|zalup\w*|'
    r'g[ao]ndon\w*|drach\w*|droch\w*|'
    r'dolboeb\w*|ublyudok\w*|mraz\w*|shlyuh\w*'
    r')\b'
)

# English obscenities and slurs. Word boundaries keep "class" and "pass" safe.
_ENGLISH_PATTERN = re.compile(
    r'\b(?:'
    r'fuck\w*|motherfuck\w*|'
    r'shit\w*|bullshit\w*|'
    r'bitch\w*|asshole\w*|bastard\w*|'
    r'cunt\w*|whore\w*|slut\w*|'
    r'nigg(?:er|a)\w*|faggot\w*'
    r')\b'
)


def _normalised_variants(text: str) -> set[str]:
    """Return possible readings of ambiguous substitutions."""
    variants = {text}
    for character, replacements in _AMBIGUOUS_SUBSTITUTIONS:
        if character not in text:
            continue
        variants = {
            variant.replace(character, replacement)
            for variant in variants
            for replacement in replacements
        }
        if len(variants) >= 16:
            break
    return variants


def _tokens(text: str) -> list[str]:
    """Split normalised text into letter-only tokens."""
    tokens = []
    for chunk in text.translate(_LEET_TRANSLATION).split():
        token = re.sub(r'[^а-я]', '', chunk)
        if not token:
            continue
        # «хуууй», «бляяядь» → «хуй», «блядь»; normal double letters survive.
        tokens.append(re.sub(r'(.)\1{2,}', r'\1', token))
    return tokens


def contains_profanity(value) -> bool:
    """Return ``True`` when *value* contains blocked language."""
    text = str(value or '')
    if not text.strip():
        return False

    lowered = text.lower()
    if _LATIN_PATTERN.search(lowered) or _ENGLISH_PATTERN.search(lowered):
        return True

    for variant in _normalised_variants(lowered.replace('ё', 'е')):
        for translator in (_LOOKALIKE_TRANSLATION, _LOOKALIKE_TRANSLATION_ALT):
            normalised = variant.translate(translator)
            for token in _tokens(normalised):
                if token in _RU_EXACT:
                    return True
                if any(pattern.search(token) for pattern in _RU_PATTERNS):
                    return True
    return False


def validate_no_profanity(value) -> None:
    """Model/form validator that rejects obscene language."""
    if not getattr(settings, 'PROFANITY_FILTER_ENABLED', True):
        return
    if contains_profanity(value):
        raise ValidationError(PROFANITY_MESSAGE, code='profanity')
