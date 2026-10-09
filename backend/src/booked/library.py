"""Library rules: collections, visibility, and what counts toward a reader's taste.

These are the rules from docs/SPEC.md section 4, kept as pure functions so the API, the
recommendation engine and the clients all agree on them.

Two independent controls on every book:
  * visibility: who can see it
  * taste inclusion: whether it shapes my recommendations and Reader Identity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Iterable, Mapping


class Visibility(IntEnum):
    """Ordered from most to least restrictive so the safest option is the minimum."""

    PRIVATE = 0
    SPECIFIC = 1
    FOLLOWERS = 2
    PUBLIC = 3


class Signal(str, Enum):
    NOT_FOR_ME = "not_for_me"
    LIKE = "like"
    REALLY_LIKE = "really_like"


@dataclass(frozen=True)
class Collection:
    id: str
    name: str
    visibility: Visibility = Visibility.PRIVATE  # new collections are private by default
    counts_toward_taste: bool = True
    shared_with: frozenset[str] = frozenset()  # user ids, used when visibility is SPECIFIC


@dataclass(frozen=True)
class LibraryEntry:
    id: str
    work_id: str
    collection_ids: tuple[str, ...] = ()
    visibility_override: Visibility | None = None
    shared_with_override: frozenset[str] = frozenset()
    taste_override: bool | None = None  # explicit per-book on/off
    signal: Signal | None = None
    unresolved: bool = False  # user-added book not yet matched to the catalog


# ------------------------------------------------------------------ taste inclusion


def counts_toward_taste(entry: LibraryEntry, collections: Mapping[str, Collection]) -> bool:
    """Does this book shape the owner's taste?

    Order of precedence:
      1. An explicit per-book setting wins.
      2. A "not for me" always counts: a deliberate negative signal.
      3. An explicit positive like on a book in a "doesn't count" collection counts
         (explicit beats inherited).
      4. Otherwise a book in any "doesn't count" collection is excluded
         (when collections disagree, excluding wins so taste is never polluted by accident).
      5. Otherwise it counts.
    """
    if entry.taste_override is not None:
        return entry.taste_override
    if entry.signal is Signal.NOT_FOR_ME:
        return True
    excluded = any(
        not collections[cid].counts_toward_taste for cid in entry.collection_ids if cid in collections
    )
    if excluded and entry.signal in (Signal.LIKE, Signal.REALLY_LIKE):
        return True
    return not excluded


SIGNAL_WEIGHTS: dict[Signal | None, float] = {
    None: 0.5,  # owning a book is weak evidence of taste
    Signal.NOT_FOR_ME: -1.0,
    Signal.LIKE: 1.0,
    Signal.REALLY_LIKE: 1.5,
}
UNRESOLVED_WEIGHT_FACTOR = 0.5  # books the catalog does not know yet count for less


def taste_weight(entry: LibraryEntry) -> float:
    weight = SIGNAL_WEIGHTS[entry.signal]
    return weight * UNRESOLVED_WEIGHT_FACTOR if entry.unresolved else weight


# ------------------------------------------------------------------ visibility


@dataclass(frozen=True)
class Audience:
    level: Visibility
    allowed: frozenset[str] = frozenset()  # meaningful when level is SPECIFIC


def effective_audience(
    entry: LibraryEntry,
    collections: Mapping[str, Collection],
    *,
    library_default: Visibility = Visibility.PRIVATE,
) -> Audience:
    """Who may see an entry.

    A per-book override wins. Otherwise the most restrictive collection wins; among collections
    that share the same restrictive level, a SPECIFIC audience is the intersection of their lists.
    A book in no collection falls back to the library default, which is private unless the owner
    changes it: the app never publishes a library implicitly.
    """
    if entry.visibility_override is not None:
        return Audience(entry.visibility_override, entry.shared_with_override)

    governing = [collections[cid] for cid in entry.collection_ids if cid in collections]
    if not governing:
        return Audience(library_default)
    lowest = min(c.visibility for c in governing)
    same = [c for c in governing if c.visibility == lowest]
    if lowest is Visibility.SPECIFIC:
        allowed = frozenset.intersection(*(c.shared_with for c in same))
        return Audience(lowest, allowed)
    return Audience(lowest)


def can_view(
    viewer_id: str,
    owner_id: str,
    audience: Audience,
    *,
    viewer_follows_owner: bool = False,
) -> bool:
    if viewer_id == owner_id:
        return True
    if audience.level is Visibility.PUBLIC:
        return True
    if audience.level is Visibility.FOLLOWERS:
        return viewer_follows_owner
    if audience.level is Visibility.SPECIFIC:
        return viewer_id in audience.allowed
    return False


def visible_entries(
    viewer_id: str,
    owner_id: str,
    entries: Iterable[LibraryEntry],
    collections: Mapping[str, Collection],
    *,
    viewer_follows_owner: bool = False,
    library_default: Visibility = Visibility.PRIVATE,
) -> list[LibraryEntry]:
    return [
        e
        for e in entries
        if can_view(
            viewer_id,
            owner_id,
            effective_audience(e, collections, library_default=library_default),
            viewer_follows_owner=viewer_follows_owner,
        )
    ]


# ------------------------------------------------------------------ auto-share rules


class SharingPreset(str, Enum):
    EVERYTHING = "everything"
    HIGHLIGHTS = "highlights"
    ONLY_WHAT_I_POST = "only_what_i_post"


class ActivityKind(str, Enum):
    FINISHED = "finished"
    REALLY_LIKED = "really_liked"
    MILESTONE = "milestone"
    WISHLIST_ADD = "wishlist_add"
    NEW_SHELF = "new_shelf"


_PRESET_KINDS: dict[SharingPreset, frozenset[ActivityKind]] = {
    SharingPreset.EVERYTHING: frozenset(ActivityKind),
    SharingPreset.HIGHLIGHTS: frozenset({ActivityKind.FINISHED, ActivityKind.REALLY_LIKED, ActivityKind.MILESTONE}),
    SharingPreset.ONLY_WHAT_I_POST: frozenset(),
}


def should_auto_share(
    preset: SharingPreset,
    kind: ActivityKind,
    entry: LibraryEntry | None,
    collections: Mapping[str, Collection],
) -> bool:
    """Decide whether an activity is posted automatically.

    Books the owner has set aside (any collection that does not count toward taste, or any
    collection that is private) are never auto-shared, whatever the preset says.
    """
    if kind not in _PRESET_KINDS[preset]:
        return False
    if entry is None:
        return True
    if entry.taste_override is False:
        return False
    for cid in entry.collection_ids:
        coll = collections.get(cid)
        if coll and (not coll.counts_toward_taste or coll.visibility is Visibility.PRIVATE):
            return False
    return True
