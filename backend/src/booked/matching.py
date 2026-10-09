"""Match noisy spine reads to catalog works and decide how much to trust the match.

Three outcomes (see docs/SPEC.md section 6):
  AUTO     high confidence, added without asking
  CONFIRM  plausible, the user taps to confirm or pick between candidates
  MANUAL   not found, the user searches or adds by hand (never a dead end)

Auto-accept precision matters more than recall: a wrong auto-accept silently pollutes
someone's library, a CONFIRM only costs a tap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from rapidfuzz import fuzz

from .catalog import Catalog, CatalogWork
from .text import dominant_script, normalize, tokens


class Decision(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    MANUAL = "manual"


@dataclass(frozen=True)
class SpineRead:
    """What the scanner read from one spine."""

    title: str
    author: str = ""
    language: str = ""  # best guess, e.g. "he", "en"; may be empty
    confidence: float = 1.0  # the reader's own confidence, 0 to 1


@dataclass(frozen=True)
class Thresholds:
    auto: float = 0.92
    confirm: float = 0.60
    margin: float = 0.08  # the top candidate must beat the runner-up by this much to auto-accept
    min_read_confidence: float = 0.6


@dataclass(frozen=True)
class Candidate:
    work: CatalogWork
    score: float


@dataclass(frozen=True)
class MatchResult:
    read: SpineRead
    candidates: tuple[Candidate, ...] = ()
    decision: Decision = Decision.MANUAL
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def top(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None


def title_similarity(a: str, b: str) -> float:
    """0..1 similarity of two titles after normalisation.

    Strict on purpose: a subset ("Dune" vs "Dune Messiah") gets partial credit only, so a
    shortened spine title never auto-accepts on title alone.
    """
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    score = max(fuzz.ratio(na, nb), fuzz.token_sort_ratio(na, nb)) / 100.0
    ta, tb = set(na.split()), set(nb.split())
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if short and short <= long_ and short != long_:
        score = max(score, 0.80 * len(short) / len(long_) + 0.05)
    return min(score, 1.0)


def author_similarity(read_author: str, authors: tuple[str, ...]) -> float:
    """Author names come in either order and often as surname only, so compare token sets."""
    na = normalize(read_author, strip_articles=False)
    if not na or not authors:
        return 0.0
    return max(fuzz.token_set_ratio(na, normalize(a, strip_articles=False)) for a in authors) / 100.0


def _author_comparable(read_author: str, work: CatalogWork) -> bool:
    """An author written in a script the catalog entry has no name for says nothing either way.

    A Hebrew spine author against a catalog that only stores "Aharon Appelfeld" is not a
    contradiction, it is missing data (the fix is aliases in each script, for example from Wikidata).
    """
    if not work.authors:
        return False
    scripts = {dominant_script(a) for a in work.authors}
    return dominant_script(read_author) in scripts or "none" in scripts


def score_candidate(read: SpineRead, work: CatalogWork) -> float:
    title = max((title_similarity(read.title, t) for t in work.all_titles()), default=0.0)
    if read.author.strip() and _author_comparable(read.author, work):
        author = author_similarity(read.author, work.authors)
        score = 0.6 * title + 0.4 * author
        if author < 0.5:  # the author contradicts the catalog entry
            score *= 0.7
        return score
    return 0.9 * title  # no author on the spine: never fully certain


def match(
    read: SpineRead,
    catalog: Catalog,
    *,
    thresholds: Thresholds = Thresholds(),
    k: int = 3,
    pool: int = 15,
) -> MatchResult:
    query = f"{read.title} {read.author}".strip()
    if not normalize(query):
        return MatchResult(read=read, decision=Decision.MANUAL, reasons=("empty read",))

    found = catalog.search(query, language=read.language or None, limit=pool)
    if not found and read.language:  # the language hint can be wrong, so retry without it
        found = catalog.search(query, limit=pool)
    scored = sorted((Candidate(w, score_candidate(read, w)) for w in found), key=lambda c: c.score, reverse=True)
    top_k = tuple(scored[:k])
    if not top_k or top_k[0].score < thresholds.confirm:
        return MatchResult(read=read, candidates=top_k, decision=Decision.MANUAL, reasons=("no plausible match",))

    best = top_k[0]
    runner_up = top_k[1].score if len(top_k) > 1 else 0.0
    reasons: list[str] = []
    auto = best.score >= thresholds.auto
    if not auto:
        reasons.append(f"score {best.score:.2f} below auto {thresholds.auto:.2f}")
    if best.score - runner_up < thresholds.margin:
        auto = False
        reasons.append("close runner-up")
    if read.confidence < thresholds.min_read_confidence:
        auto = False
        reasons.append("low read confidence")
    if not read.author.strip() and len(tokens(read.title)) < 2:
        auto = False  # a single-word title without an author is too ambiguous to add silently
        reasons.append("single-word title without author")

    return MatchResult(
        read=read,
        candidates=top_k,
        decision=Decision.AUTO if auto else Decision.CONFIRM,
        reasons=tuple(reasons),
    )
