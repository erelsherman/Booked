"""Catalog interface and two implementations: in-memory (tests, fixtures) and Open Library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx
from rapidfuzz import fuzz, process

from .text import normalize


@dataclass(frozen=True)
class CatalogWork:
    """A logical book (a Work), not a specific edition.

    ``alt_titles`` carries translated and transliterated titles so the Hebrew and English
    editions of the same book resolve to one Work.
    """

    id: str
    title: str
    authors: tuple[str, ...] = ()
    language: str = "en"
    alt_titles: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    year: int | None = None
    description: str = ""

    def all_titles(self) -> tuple[str, ...]:
        return (self.title, *self.alt_titles)


class Catalog(Protocol):
    def search(self, query: str, *, language: str | None = None, limit: int = 10) -> list[CatalogWork]:
        """Return candidate works for free text such as 'title author'. Ranking is done by the matcher."""
        ...


@dataclass
class InMemoryCatalog:
    works: list[CatalogWork] = field(default_factory=list)

    def add(self, *works: CatalogWork) -> None:
        self.works.extend(works)

    def search(self, query: str, *, language: str | None = None, limit: int = 10) -> list[CatalogWork]:
        q = normalize(query)
        if not q or not self.works:
            return []
        choices = {
            i: normalize(" ".join((*w.all_titles(), *w.authors)), strip_articles=False)
            for i, w in enumerate(self.works)
        }
        hits = process.extract(q, choices, scorer=fuzz.WRatio, limit=limit, score_cutoff=40)
        return [self.works[idx] for _choice, _score, idx in hits]


# Our language codes to the three-letter codes Open Library uses.
_OPENLIBRARY_LANG = {"he": "heb", "en": "eng", "fr": "fre", "es": "spa", "it": "ita", "de": "ger", "pt": "por"}
_OPENLIBRARY_BACK = {v: k for k, v in _OPENLIBRARY_LANG.items()}


class OpenLibraryCatalog:
    """Thin client for Open Library's search API.

    Open Library asks API users to identify themselves, so set ``user_agent`` to something with
    a contact address before using this at any volume.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://openlibrary.org",
        user_agent: str = "Booked/0.1 (prototype)",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url, headers={"User-Agent": user_agent}, transport=transport, timeout=timeout
        )

    def search(self, query: str, *, language: str | None = None, limit: int = 10) -> list[CatalogWork]:
        params: dict[str, str | int] = {
            "q": query,
            "limit": limit,
            "fields": "key,title,author_name,first_publish_year,language,subject",
        }
        if language and language in _OPENLIBRARY_LANG:
            params["language"] = _OPENLIBRARY_LANG[language]
        response = self._client.get("/search.json", params=params)
        response.raise_for_status()
        return [self._to_work(doc) for doc in response.json().get("docs", []) if doc.get("key") and doc.get("title")]

    @staticmethod
    def _to_work(doc: dict) -> CatalogWork:
        langs = [_OPENLIBRARY_BACK.get(code, code) for code in doc.get("language", [])]
        return CatalogWork(
            id=doc["key"],
            title=doc["title"],
            authors=tuple(doc.get("author_name", [])),
            language=langs[0] if langs else "und",
            subjects=tuple(doc.get("subject", [])[:12]),
            year=doc.get("first_publish_year"),
        )
