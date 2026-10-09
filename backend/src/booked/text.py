"""Text normalisation for matching titles and authors across Hebrew and Latin scripts.

Spine OCR is noisy and catalogs spell things differently, so everything that is
compared goes through ``normalize`` first.
"""

from __future__ import annotations

import re
import unicodedata

# Hebrew final letters map to their regular forms so "ם" and "מ" compare equal.
_HEBREW_FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})

# Geresh and gershayim mark transliterated sounds (ג׳ורג׳) and must not split a word.
_HEBREW_MARKS = str.maketrans("", "", "\u05f3\u05f4")

# Anything that is not a word character or whitespace becomes a space.
# \w covers Hebrew and Latin letters and digits; geresh, gershayim and maqaf are punctuation.
_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)
_SPACES = re.compile(r"\s+")

# Leading articles that spines often drop or keep inconsistently.
_LATIN_ARTICLES = frozenset(
    {"the", "a", "an", "le", "la", "les", "l", "un", "une", "el", "los", "las", "der", "die", "das", "il"}
)


def normalize(text: str, *, strip_articles: bool = True) -> str:
    """Casefold, drop diacritics and Hebrew niqqud, unify final letters, remove punctuation."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    # Mn removes Latin accents, Hebrew niqqud and cantillation marks.
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    folded = stripped.casefold().translate(_HEBREW_FINALS).translate(_HEBREW_MARKS)
    spaced = _PUNCT.sub(" ", folded)
    collapsed = _SPACES.sub(" ", spaced).strip()
    if strip_articles:
        tokens = collapsed.split(" ")
        if len(tokens) > 1 and tokens[0] in _LATIN_ARTICLES:
            collapsed = " ".join(tokens[1:])
    return collapsed


def tokens(text: str) -> list[str]:
    n = normalize(text)
    return n.split(" ") if n else []


def _script_of(ch: str) -> str | None:
    code = ord(ch)
    if 0x0590 <= code <= 0x05FF or 0xFB1D <= code <= 0xFB4F:
        return "he"
    if not ch.isalpha():
        return None
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return "other"
    return "latin" if name.startswith("LATIN") else "other"


def dominant_script(text: str) -> str:
    """Return 'he', 'latin', 'other' or 'none' for the script with most letters."""
    counts: dict[str, int] = {}
    for ch in text:
        script = _script_of(ch)
        if script and ch.isalpha():
            counts[script] = counts.get(script, 0) + 1
    if not counts:
        return "none"
    return max(counts, key=counts.__getitem__)
