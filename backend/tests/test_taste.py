from booked.library import Collection, LibraryEntry, Signal, Visibility
from booked.taste import HashingEmbedder, LibraryItem, build_profile, recommend


def items(catalog, spec):
    """spec: list of (work_id, LibraryEntry kwargs)"""
    by_id = {w.id: w for w in catalog.works}
    return [LibraryItem(LibraryEntry(id=f"e{i}", work_id=wid, **kw), by_id[wid]) for i, (wid, kw) in enumerate(spec)]


def test_profile_ignores_set_aside_books(catalog):
    colls = {"dana": Collection("dana", "Dana's books", Visibility.PRIVATE, counts_toward_taste=False)}
    prof = build_profile(
        items(catalog, [("w-nw", {}), ("w-kafka", {}), ("w-acc", {"collection_ids": ("dana",)})]),
        colls,
        HashingEmbedder(),
    )
    assert prof.counted == 2
    assert prof.set_aside == 1
    assert "accounting" not in {s for s, _ in prof.top_subjects}


def test_empty_profile_has_no_recommendations(catalog):
    prof = build_profile([], {}, HashingEmbedder())
    assert prof.is_empty and prof.confidence == "low"
    assert recommend(prof, catalog.works, owned_work_ids=set(), embedder=HashingEmbedder()) == []


def test_recommendations_follow_taste_and_exclude_owned(catalog):
    emb = HashingEmbedder()
    prof = build_profile(
        items(catalog, [("w-nw", {"signal": Signal.REALLY_LIKE}), ("w-wub", {"signal": Signal.LIKE})]), {}, emb
    )
    recs = recommend(prof, catalog.works, owned_work_ids={"w-nw", "w-wub"}, embedder=emb, limit=3)
    ids = [r.work.id for r in recs]
    assert "w-nw" not in ids and "w-wub" not in ids
    assert ids[0] == "w-kafka"  # same author, subjects and setting
    assert ids.index("w-kafka") < ids.index("w-acc") if "w-acc" in ids else True


def test_not_for_me_pushes_similar_books_down(catalog):
    emb = HashingEmbedder()
    liked = items(catalog, [("w-hobbit", {"signal": Signal.LIKE}), ("w-nw", {"signal": Signal.LIKE})])
    disliked = liked + items(catalog, [("w-dune", {"signal": Signal.NOT_FOR_ME})])
    base = build_profile(liked, {}, emb)
    with_dislike = build_profile(disliked, {}, emb)
    pool = [w for w in catalog.works if w.id in {"w-dune2", "w-lotr"}]
    own = {"w-hobbit", "w-nw", "w-dune"}
    r_base = {r.work.id: r.score for r in recommend(base, pool, owned_work_ids=own, embedder=emb)}
    r_dis = {r.work.id: r.score for r in recommend(with_dislike, pool, owned_work_ids=own, embedder=emb)}
    assert r_dis["w-dune2"] < r_base["w-dune2"]


def test_friend_boost_and_structured_reasons(catalog):
    emb = HashingEmbedder()
    prof = build_profile(items(catalog, [("w-nw", {"signal": Signal.LIKE})]), {}, emb)
    pool = [w for w in catalog.works if w.id in {"w-wub", "w-kafka"}]
    plain = {r.work.id: r.score for r in recommend(prof, pool, owned_work_ids={"w-nw"}, embedder=emb)}
    boosted = recommend(prof, pool, owned_work_ids={"w-nw"}, embedder=emb, friend_counts={"w-wub": 3})
    top = next(r for r in boosted if r.work.id == "w-wub")
    assert top.score > plain["w-wub"]
    assert any(r.kind == "friends" and r.detail == "3" for r in top.reasons)
    assert any(r.kind == "subject" for r in top.reasons)


def test_confidence_levels(catalog):
    emb = HashingEmbedder()
    one = build_profile(items(catalog, [("w-nw", {})]), {}, emb)
    assert one.confidence == "low"
