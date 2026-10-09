"""Offline demo mode: a small catalog and a fake reader so the UI can be tried without an API key or network."""

from __future__ import annotations

from booked.catalog import CatalogWork, InMemoryCatalog
from scan_eval.cloud import ScanResult


def demo_catalog() -> InMemoryCatalog:
    c = InMemoryCatalog()
    c.add(
        CatalogWork("demo-nw", "Norwegian Wood", ("Haruki Murakami",), "en", subjects=("literary fiction", "japan", "coming of age"), year=1987),
        CatalogWork("demo-kafka", "Kafka on the Shore", ("Haruki Murakami",), "en", subjects=("literary fiction", "magical realism", "japan"), year=2002),
        CatalogWork("demo-bad", "Badenheim 1939", ("Aharon Appelfeld", "אהרן אפלפלד"), "he", alt_titles=("בדנהיים עיר נופש",), subjects=("historical fiction", "holocaust", "literary fiction"), year=1975),
        CatalogWork("demo-rr", "A Russian Novel", ("Meir Shalev", "מאיר שלו"), "he", alt_titles=("רומן רוסי",), subjects=("literary fiction", "israel", "family"), year=1988),
        CatalogWork("demo-rr2", "Russian Novel (collected)", ("Someone Else",), "en", subjects=("anthology",)),
        CatalogWork("demo-gro", "A Woman Fleeing Tidings", ("David Grossman", "דוד גרוסמן"), "he", alt_titles=("אישה בורחת מבשורה",), subjects=("literary fiction", "israel", "family"), year=2008),
        CatalogWork("demo-sap", "Sapiens: A Brief History of Humankind", ("Yuval Noah Harari", "יובל נח הררי"), "he", alt_titles=("ספיינס",), subjects=("history", "anthropology", "non-fiction"), year=2011),
        CatalogWork("demo-etr", "L'Étranger", ("Albert Camus",), "fr", alt_titles=("The Stranger",), subjects=("literary fiction", "philosophy"), year=1942),
        CatalogWork("demo-oz", "A Tale of Love and Darkness", ("Amos Oz", "עמוס עוז"), "he", alt_titles=("סיפור על אהבה וחושך",), subjects=("memoir", "israel", "history"), year=2002),
    )
    return c


_DEMO_READS = [
    {"title": "Norwegian Wood", "author": "Haruki Murakami", "language": "en", "confidence": 0.95},
    {"title": "בדנהיים עיר נופש", "author": "אהרן אפלפלד", "language": "he", "confidence": 0.9},
    {"title": "Sapiens", "author": "Yuval Noah Harari", "language": "en", "confidence": 0.9},
    {"title": "L'Etranger", "author": "Albert Camus", "language": "fr", "confidence": 0.85},
    {"title": "רומן רוסי", "author": "שלו", "language": "he", "confidence": 0.7},
    {"title": "Kafka on the Shre", "author": "Murakami", "language": "en", "confidence": 0.55},
    {"title": "Unknown Quiet Novel", "author": "", "language": "en", "confidence": 0.5},
]


class DemoReader:
    """Returns the same plausible reads for any photo, at zero cost."""

    def read_bytes(self, name: str, raw: bytes) -> ScanResult:  # noqa: ARG002 (the photo is ignored)
        return ScanResult(photo=name, model="demo", reads=[dict(r) for r in _DEMO_READS], unreadable=1, latency_s=0.2)
