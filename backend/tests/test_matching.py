from booked.matching import Decision, SpineRead, Thresholds, match, title_similarity


def test_exact_title_and_author_is_auto_accepted(catalog):
    result = match(SpineRead("Norwegian Wood", "Haruki Murakami"), catalog)
    assert result.decision is Decision.AUTO
    assert result.top.work.id == "w-nw"


def test_surname_only_author_still_matches(catalog):
    result = match(SpineRead("Kafka on the Shore", "Murakami"), catalog)
    assert result.top.work.id == "w-kafka"
    assert result.decision is Decision.AUTO


def test_one_character_typo_with_matching_author_is_still_found(catalog):
    result = match(SpineRead("Norwegian Wod", "H. Murakami"), catalog)
    assert result.top.work.id == "w-nw"
    assert result.decision is not Decision.MANUAL


def test_heavier_ocr_noise_goes_to_confirm_not_auto(catalog):
    result = match(SpineRead("Norwegn Wd", "Murakami"), catalog)
    assert result.top.work.id == "w-nw"
    assert result.decision is Decision.CONFIRM


def test_hebrew_author_without_hebrew_alias_is_not_a_contradiction():
    from booked.catalog import CatalogWork, InMemoryCatalog

    only_latin = InMemoryCatalog([CatalogWork("w", "Badenheim 1939", ("Aharon Appelfeld",), "en", alt_titles=("בדנהיים עיר נופש",))])
    result = match(SpineRead("בדנהיים עיר נופש", "אהרן אפלפלד"), only_latin)
    assert result.decision is Decision.CONFIRM  # right book, but we cannot verify the author, so ask


def test_hebrew_author_with_alias_auto_accepts(catalog):
    result = match(SpineRead("בדנהיים עיר נופש", "אהרן אפלפלד", language="he"), catalog)
    assert result.decision is Decision.AUTO and result.top.work.id == "w-bad"


def test_hebrew_title_matches_via_alt_title(catalog):
    result = match(SpineRead("בדנהיים עיר נופש", "אהרן אפלפלד", language="he"), catalog)
    assert result.top.work.id == "w-bad"


def test_hebrew_niqqud_and_final_letter_variants_match(catalog):
    result = match(SpineRead("בְּדֶנְהַיִים עִיר נוֹפֶשׁ"), catalog)
    assert result.top.work.id == "w-bad"


def test_hebrew_title_without_author_is_not_auto_when_it_is_one_word(catalog):
    result = match(SpineRead("ספיינס", language="he"), catalog)
    assert result.top.work.id == "w-sap"
    assert result.decision is Decision.CONFIRM  # single word, no author


def test_translated_title_found_through_catalog_alt_title(catalog):
    result = match(SpineRead("The Stranger", "Albert Camus"), catalog)
    assert result.top.work.id == "w-etr"


def test_garbage_goes_to_manual(catalog):
    result = match(SpineRead("zzqxv kjwp"), catalog)
    assert result.decision is Decision.MANUAL


def test_empty_read_goes_to_manual(catalog):
    assert match(SpineRead(""), catalog).decision is Decision.MANUAL


def test_shortened_title_never_auto_accepts_on_title_alone(catalog):
    # "Dune" is a subset of "Dune Messiah": must not be treated as an exact match.
    assert title_similarity("Dune", "Dune Messiah") < 0.92
    result = match(SpineRead("Dune"), catalog)
    assert result.decision is not Decision.AUTO


def test_close_runner_up_blocks_auto(catalog):
    result = match(SpineRead("The Lord of the Ring", "Tolkien"), catalog, thresholds=Thresholds(auto=0.5, margin=0.5))
    assert result.decision is Decision.CONFIRM
    assert "close runner-up" in result.reasons


def test_low_read_confidence_blocks_auto(catalog):
    result = match(SpineRead("Norwegian Wood", "Haruki Murakami", confidence=0.3), catalog)
    assert result.decision is Decision.CONFIRM
    assert "low read confidence" in result.reasons


def test_wrong_author_is_penalised(catalog):
    right = match(SpineRead("Norwegian Wood", "Haruki Murakami"), catalog).top.score
    wrong = match(SpineRead("Norwegian Wood", "Stephen King"), catalog).top.score
    assert wrong < right * 0.8
