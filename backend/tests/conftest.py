import pytest

from booked.catalog import CatalogWork, InMemoryCatalog


@pytest.fixture
def catalog() -> InMemoryCatalog:
    c = InMemoryCatalog()
    c.add(
        CatalogWork("w-nw", "Norwegian Wood", ("Haruki Murakami",), "en", alt_titles=("נורווגיאן ווד", "Norwegian Wood (novel)"),
                    subjects=("literary fiction", "japan", "coming of age")),
        CatalogWork("w-wub", "The Wind-Up Bird Chronicle", ("Haruki Murakami",), "en", subjects=("literary fiction", "japan", "magical realism")),
        CatalogWork("w-kafka", "Kafka on the Shore", ("Haruki Murakami",), "en", subjects=("literary fiction", "japan", "magical realism")),
        CatalogWork("w-bad", "Badenheim 1939", ("Aharon Appelfeld", "אהרן אפלפלד"), "en", alt_titles=("בדנהיים עיר נופש",),
                    subjects=("literary fiction", "holocaust", "historical fiction")),
        CatalogWork("w-rr", "A Russian Novel", ("Meir Shalev", "מאיר שלו"), "en", alt_titles=("רומן רוסי",),
                    subjects=("literary fiction", "israel", "family")),
        CatalogWork("w-gro", "A Woman Fleeing Tidings", ("David Grossman", "דוד גרוסמן"), "en", alt_titles=("אישה בורחת מבשורה",),
                    subjects=("literary fiction", "israel", "family")),
        CatalogWork("w-dune", "Dune", ("Frank Herbert",), "en", subjects=("science fiction", "adventure")),
        CatalogWork("w-dune2", "Dune Messiah", ("Frank Herbert",), "en", subjects=("science fiction", "adventure")),
        CatalogWork("w-sap", "Sapiens: A Brief History of Humankind", ("Yuval Noah Harari", "יובל נח הררי"), "en", alt_titles=("ספיינס",),
                    subjects=("history", "anthropology", "non-fiction")),
        CatalogWork("w-etr", "L'Étranger", ("Albert Camus",), "fr", alt_titles=("The Stranger",), subjects=("literary fiction", "philosophy")),
        CatalogWork("w-hobbit", "The Hobbit", ("J.R.R. Tolkien",), "en", subjects=("fantasy", "adventure")),
        CatalogWork("w-lotr", "The Lord of the Rings", ("J.R.R. Tolkien",), "en", subjects=("fantasy", "adventure")),
        CatalogWork("w-acc", "Accounting Principles", ("Jerry J. Weygandt",), "en", subjects=("accounting", "business", "textbook")),
    )
    return c
