"""Phone numbers and emails of real points of contact, taken only from pages the agent read.

A number the agent returns is accepted only if the same number (after normalising +971 / 00971 /
leading 0, spaces and dashes) appears in the text of an official page it fetched in that run.
That is what makes the numbers "valid": they are the entity's own published contact details.
"""

import re

_PHONE = re.compile(r"(?<![\w/])(?:\+|00)?\d[\d \-().]{3,18}\d(?![\w/])")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DATE_LIKE = re.compile(r"^\d{1,4}[./-]\d{1,2}[./-]\d{1,4}$")
MIN_DIGITS = 5
MAX_DIGITS = 12


def national(phone: str) -> str:
    """Digits of the number without UAE country code or trunk 0 ("+971 4 123 4567" -> 41234567)."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("971"):
        digits = digits[3:]
    return digits.lstrip("0")


def plausible(phone: str) -> bool:
    raw = phone.strip()
    if _DATE_LIKE.match(raw) or re.fullmatch(r"(19|20)\d\d", raw):
        return False
    digits = national(raw)
    return MIN_DIGITS <= len(digits) <= MAX_DIGITS


def tel_href(phone: str) -> str:
    """A tel: link that dials correctly from a UAE phone (toll-free 800 / 600 numbers stay local)."""
    raw = phone.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return f"tel:+{digits}"
    if digits.startswith("00"):
        return f"tel:+{digits[2:]}"
    if digits.startswith(("800", "600")):
        return f"tel:{digits}"
    return f"tel:+971{national(raw)}"


def extract(text: str, limit: int = 12) -> list[dict[str, str]]:
    """Phone-number candidates with the words around them, so the agent can label them."""
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _PHONE.finditer(text):
        raw = " ".join(match.group(0).split())
        key = national(raw)
        if not plausible(raw) or key in seen:
            continue
        seen.add(key)
        start, end = max(0, match.start() - 70), min(len(text), match.end() + 40)
        found.append({"phone": raw, "context": " ".join(text[start:end].split())})
        if len(found) >= limit:
            break
    return found


def emails(text: str, limit: int = 5) -> list[str]:
    return list(dict.fromkeys(m.group(0).rstrip(".") for m in _EMAIL.finditer(text)))[:limit]


def appears_in(phone: str, texts: list[str]) -> bool:
    target = national(phone)
    if not plausible(phone):
        return False
    return any(national(m.group(0)) == target for text in texts for m in _PHONE.finditer(text))
