"""Stage 1 taste engine: content-based profile and recommendations (docs/SPEC.md section 7).

Works with zero friends. Social signals only add a small boost. The ``Embedder`` is a seam:
tests use a deterministic hashing embedder, production plugs in a multilingual model
(for example bge-m3 or multilingual-e5, which cover Hebrew).
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol, Sequence

from .catalog import CatalogWork
from .library import Collection, LibraryEntry, counts_toward_taste, taste_weight
from .text import tokens


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic bag-of-words embedding with signed feature hashing. For tests and local runs."""

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in tokens(text):
            digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
            h = int.from_bytes(digest, "big")
            vec[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        return _normalized(vec)


def _normalized(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def work_text(work: CatalogWork) -> str:
    return ". ".join(
        part for part in (work.title, ", ".join(work.authors), ", ".join(work.subjects), work.description) if part
    )


@dataclass(frozen=True)
class LibraryItem:
    entry: LibraryEntry
    work: CatalogWork


@dataclass(frozen=True)
class TasteProfile:
    vector: tuple[float, ...]
    counted: int  # books that shaped the profile
    set_aside: int  # books excluded from taste
    top_subjects: tuple[tuple[str, float], ...]  # (subject, share), strongest first
    languages: tuple[tuple[str, float], ...]  # (language, share)

    @property
    def confidence(self) -> str:
        """low under 8 books, medium under 30, high from 30 (the UI says "based on N books")."""
        if self.counted < 8:
            return "low"
        return "medium" if self.counted < 30 else "high"

    @property
    def is_empty(self) -> bool:
        return self.counted == 0


def _shares(counter: Counter, top: int) -> tuple[tuple[str, float], ...]:
    total = sum(counter.values())
    if not total:
        return ()
    return tuple((k, v / total) for k, v in counter.most_common(top))


def build_profile(
    items: Iterable[LibraryItem],
    collections: Mapping[str, Collection],
    embedder: Embedder,
) -> TasteProfile:
    counted: list[tuple[LibraryItem, float]] = []
    set_aside = 0
    for item in items:
        if counts_toward_taste(item.entry, collections):
            counted.append((item, taste_weight(item.entry)))
        else:
            set_aside += 1
    if not counted:
        return TasteProfile((), 0, set_aside, (), ())

    vectors = embedder.embed([work_text(i.work) for i, _ in counted])
    dim = len(vectors[0])
    total = [0.0] * dim
    for (_, weight), vec in zip(counted, vectors):
        for k in range(dim):
            total[k] += weight * vec[k]

    subjects: Counter = Counter()
    languages: Counter = Counter()
    for item, weight in counted:
        if weight <= 0:
            continue  # negative signals shape the vector but are not "what you read"
        for subject in item.work.subjects:
            subjects[subject] += weight
        languages[item.work.language] += weight

    return TasteProfile(
        vector=tuple(_normalized(total)),
        counted=len(counted),
        set_aside=set_aside,
        top_subjects=_shares(subjects, 5),
        languages=_shares(languages, 4),
    )


@dataclass(frozen=True)
class Reason:
    kind: str  # "subject", "friends", "language"
    detail: str


@dataclass(frozen=True)
class Recommendation:
    work: CatalogWork
    score: float
    reasons: tuple[Reason, ...] = field(default_factory=tuple)


FRIEND_BOOST = 0.05
FRIEND_BOOST_CAP = 3


def recommend(
    profile: TasteProfile,
    candidates: Iterable[CatalogWork],
    *,
    owned_work_ids: set[str],
    embedder: Embedder,
    friend_counts: Mapping[str, int] | None = None,
    limit: int = 10,
) -> list[Recommendation]:
    """Rank candidates by similarity to the profile.

    Reasons are structured evidence, never prose: the "Why this?" sentence is written by a
    model from these facts, so it cannot invent anything.
    """
    if profile.is_empty:
        return []
    friend_counts = friend_counts or {}
    pool = [w for w in candidates if w.id not in owned_work_ids]
    if not pool:
        return []
    vectors = embedder.embed([work_text(w) for w in pool])
    liked_subjects = {s for s, _ in profile.top_subjects}
    liked_languages = {lang for lang, _ in profile.languages}

    scored: list[Recommendation] = []
    for work, vec in zip(pool, vectors):
        friends = friend_counts.get(work.id, 0)
        score = cosine(profile.vector, vec) + FRIEND_BOOST * min(friends, FRIEND_BOOST_CAP)
        reasons: list[Reason] = [Reason("subject", s) for s in work.subjects if s in liked_subjects][:2]
        if friends:
            reasons.append(Reason("friends", str(friends)))
        if work.language in liked_languages:
            reasons.append(Reason("language", work.language))
        scored.append(Recommendation(work, score, tuple(reasons)))
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:limit]
