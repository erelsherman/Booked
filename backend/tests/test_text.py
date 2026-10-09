from booked.text import dominant_script, normalize, tokens


def test_latin_accents_case_and_punctuation():
    assert normalize("L’Étranger") == "etranger"  # article "l" dropped, accent removed
    assert normalize("Norwegian Wood!") == "norwegian wood"
    assert normalize("  The   Wind-Up  Bird Chronicle ") == "wind up bird chronicle"


def test_leading_article_kept_when_it_is_the_whole_title():
    assert normalize("The") == "the"
    assert normalize("A") == "a"


def test_hebrew_niqqud_is_removed():
    assert normalize("בְּדֶנְהַיִם") == normalize("בדנהים")


def test_hebrew_final_letters_unify():
    assert normalize("עיר נופש") == normalize("עיר נופש".replace("ר", "ר"))
    assert normalize("שלום") == normalize("שלומ")  # final mem equals regular mem


def test_hebrew_punctuation_is_stripped():
    assert normalize("ג׳ורג׳ אורוול") == "גורג אורוול"
    assert normalize("בן־גוריון") == "בנ גוריונ"


def test_tokens():
    assert tokens("Sapiens: A Brief History") == ["sapiens", "a", "brief", "history"]
    assert tokens("") == []


def test_dominant_script():
    assert dominant_script("אישה בורחת מבשורה") == "he"
    assert dominant_script("Norwegian Wood") == "latin"
    assert dominant_script("123 !!!") == "none"
    assert dominant_script("Haruki הרוקי Murakami") == "latin"
