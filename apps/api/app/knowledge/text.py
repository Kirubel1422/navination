"""Bilingual text normalisation for small-catalog keyword retrieval."""

import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_TOKEN = re.compile(r"[\w]+", re.UNICODE)
_ARABIC_LETTERS = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}
)
_ARABIC_RANGE = re.compile(r"[؀-ۿ]")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(_ARABIC_LETTERS)
    text = re.sub(r"[’'`]", "", text)
    return " ".join(_TOKEN.findall(text.replace("_", " ")))


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def strip_arabic_prefix(token: str) -> str:
    """Remove common Arabic proclitics (و، ب، ل، ف، ك) and the definite article for matching."""
    if not _ARABIC_RANGE.search(token):
        return token
    for prefix in ("وال", "بال", "لل", "فال", "كال", "ال"):
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            return token[len(prefix) :]
    if token[0] in "وبلفك" and len(token) >= 5:
        return token[1:]
    return token


def is_arabic(text: str) -> bool:
    return bool(_ARABIC_RANGE.search(text))
