"""A deterministic first version of the Reader Identity summary (docs/DESIGN.md section 6).

No model is involved: it summarises what is in the confirmed library. The written statement is a
plain template for now; the "X, not Y" headline needs likes and dislikes, and the model-written
version comes later from this same structured evidence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

# Open Library subjects include housekeeping tags that say nothing about taste.
_NOISE_PREFIXES = ("reading level", "nyt:", "in library", "accessible", "protected daisy", "overdrive", "internet archive", "large type", "open library", "lending library")
_NOISE_EXACT = {"fiction in english", "english language", "english fiction", "books and reading"}


def clean_subjects(subjects: list[str] | tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    for raw in subjects:
        s = raw.strip().lower()
        if not s or s in _NOISE_EXACT or s.startswith(_NOISE_PREFIXES) or len(s) > 40:
            continue
        if s not in cleaned:
            cleaned.append(s)
    return cleaned


@dataclass(frozen=True)
class IdentityBook:
    work_id: str
    title: str
    authors: tuple[str, ...] = ()
    language: str = ""
    subjects: tuple[str, ...] = ()


def _shares(counter: Counter, top: int) -> list[dict]:
    total = sum(counter.values())
    return [{"name": k, "count": v, "share": round(v / total, 3)} for k, v in counter.most_common(top)] if total else []


def build_identity(books: list[IdentityBook]) -> dict:
    n = len(books)
    languages: Counter = Counter(b.language or "und" for b in books)
    subjects: Counter = Counter()
    authors: Counter = Counter()
    for b in books:
        for s in clean_subjects(b.subjects)[:6]:
            subjects[s] += 1
        if b.authors:
            authors[b.authors[0]] += 1

    confidence = "low" if n < 8 else "medium" if n < 30 else "high"
    top_subjects = [s["name"] for s in _shares(subjects, 3)]
    if n == 0:
        statement = "Scan a shelf to see your Reader Identity."
    elif confidence == "low":
        statement = "A first sketch of your taste. Scan a few more shelves to sharpen it."
    elif len(top_subjects) >= 2:
        statement = f"Mostly {top_subjects[0]} and {top_subjects[1]}."
    elif top_subjects:
        statement = f"Mostly {top_subjects[0]}."
    else:
        statement = "A varied shelf."

    return {
        "books": n,
        "confidence": confidence,
        "statement": statement,
        "languages": _shares(languages, 5),
        "subjects": _shares(subjects, 6),
        "authors": [a for a in _shares(authors, 5) if a["count"] >= 1],
        "note": f"Based on {n} book{'s' if n != 1 else ''}.",
    }
