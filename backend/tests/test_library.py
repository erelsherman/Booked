from booked.library import (
    ActivityKind,
    Audience,
    Collection,
    LibraryEntry,
    SharingPreset,
    Signal,
    Visibility,
    can_view,
    counts_toward_taste,
    effective_audience,
    should_auto_share,
    taste_weight,
    visible_entries,
)

DANA = Collection("dana", "Dana's books", Visibility.SPECIFIC, counts_toward_taste=False, shared_with=frozenset({"dana"}))
WORK = Collection("work", "Work", Visibility.PRIVATE, counts_toward_taste=False)
FICTION = Collection("fic", "Fiction", Visibility.PUBLIC, counts_toward_taste=True)
COLLS = {c.id: c for c in (DANA, WORK, FICTION)}


def entry(**kw) -> LibraryEntry:
    kw.setdefault("id", "e1")
    kw.setdefault("work_id", "w1")
    return LibraryEntry(**kw)


# ---------------------------------------------------------------- taste inclusion


def test_book_in_no_collection_counts():
    assert counts_toward_taste(entry(), COLLS)


def test_book_in_set_aside_collection_does_not_count():
    assert not counts_toward_taste(entry(collection_ids=("dana",)), COLLS)


def test_explicit_book_override_beats_collection_default_both_ways():
    assert counts_toward_taste(entry(collection_ids=("dana",), taste_override=True), COLLS)
    assert not counts_toward_taste(entry(collection_ids=("fic",), taste_override=False), COLLS)


def test_conflicting_collections_exclude_wins():
    assert not counts_toward_taste(entry(collection_ids=("fic", "dana")), COLLS)


def test_explicit_like_counts_even_in_set_aside_collection():
    assert counts_toward_taste(entry(collection_ids=("dana",), signal=Signal.LIKE), COLLS)
    assert counts_toward_taste(entry(collection_ids=("dana",), signal=Signal.REALLY_LIKE), COLLS)


def test_not_for_me_always_counts_as_a_negative_signal():
    assert counts_toward_taste(entry(collection_ids=("dana",), signal=Signal.NOT_FOR_ME), COLLS)


def test_explicit_off_beats_a_like():
    e = entry(collection_ids=("fic",), signal=Signal.LIKE, taste_override=False)
    assert not counts_toward_taste(e, COLLS)


def test_taste_weights():
    assert taste_weight(entry(signal=Signal.REALLY_LIKE)) > taste_weight(entry(signal=Signal.LIKE)) > taste_weight(entry())
    assert taste_weight(entry(signal=Signal.NOT_FOR_ME)) < 0
    assert taste_weight(entry(unresolved=True, signal=Signal.LIKE)) == taste_weight(entry(signal=Signal.LIKE)) * 0.5


# ---------------------------------------------------------------- visibility


def test_no_collection_defaults_to_private():
    assert effective_audience(entry(), COLLS).level is Visibility.PRIVATE


def test_most_restrictive_collection_wins():
    aud = effective_audience(entry(collection_ids=("fic", "work")), COLLS)
    assert aud.level is Visibility.PRIVATE


def test_specific_audiences_intersect():
    a = Collection("a", "A", Visibility.SPECIFIC, shared_with=frozenset({"x", "y"}))
    b = Collection("b", "B", Visibility.SPECIFIC, shared_with=frozenset({"y", "z"}))
    aud = effective_audience(entry(collection_ids=("a", "b")), {"a": a, "b": b})
    assert aud == Audience(Visibility.SPECIFIC, frozenset({"y"}))


def test_book_override_beats_collection_visibility():
    e = entry(collection_ids=("dana",), visibility_override=Visibility.PUBLIC)
    assert effective_audience(e, COLLS).level is Visibility.PUBLIC


def test_can_view_rules():
    owner = "me"
    assert can_view(owner, owner, Audience(Visibility.PRIVATE))
    assert not can_view("friend", owner, Audience(Visibility.PRIVATE))
    assert can_view("anyone", owner, Audience(Visibility.PUBLIC))
    assert can_view("fan", owner, Audience(Visibility.FOLLOWERS), viewer_follows_owner=True)
    assert not can_view("stranger", owner, Audience(Visibility.FOLLOWERS), viewer_follows_owner=False)
    assert can_view("dana", owner, Audience(Visibility.SPECIFIC, frozenset({"dana"})))
    assert not can_view("noa", owner, Audience(Visibility.SPECIFIC, frozenset({"dana"})))


def test_danas_books_scenario_end_to_end():
    entries = [
        entry(id="1", work_id="acct", collection_ids=("dana",)),
        entry(id="2", work_id="novel", collection_ids=("fic",)),
        entry(id="3", work_id="solo"),
    ]
    dana_sees = visible_entries("dana", "me", entries, COLLS)
    stranger_sees = visible_entries("stranger", "me", entries, COLLS)
    assert [e.id for e in dana_sees] == ["1", "2"]
    assert [e.id for e in stranger_sees] == ["2"]
    assert [e.id for e in visible_entries("me", "me", entries, COLLS)] == ["1", "2", "3"]


# ---------------------------------------------------------------- auto-share


def test_presets_filter_activity_kinds():
    plain = entry(collection_ids=("fic",))
    assert should_auto_share(SharingPreset.HIGHLIGHTS, ActivityKind.FINISHED, plain, COLLS)
    assert not should_auto_share(SharingPreset.HIGHLIGHTS, ActivityKind.WISHLIST_ADD, plain, COLLS)
    assert should_auto_share(SharingPreset.EVERYTHING, ActivityKind.WISHLIST_ADD, plain, COLLS)
    assert not should_auto_share(SharingPreset.ONLY_WHAT_I_POST, ActivityKind.FINISHED, plain, COLLS)


def test_set_aside_and_private_books_are_never_auto_shared():
    assert not should_auto_share(SharingPreset.EVERYTHING, ActivityKind.FINISHED, entry(collection_ids=("dana",)), COLLS)
    assert not should_auto_share(SharingPreset.EVERYTHING, ActivityKind.FINISHED, entry(collection_ids=("work",)), COLLS)
    assert not should_auto_share(SharingPreset.EVERYTHING, ActivityKind.FINISHED, entry(taste_override=False), COLLS)


def test_milestones_without_a_book_can_share():
    assert should_auto_share(SharingPreset.HIGHLIGHTS, ActivityKind.MILESTONE, None, COLLS)
