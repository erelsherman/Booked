import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from booked.web.app import Settings, create_app
from booked.web.demo import demo_catalog
from booked.web.identity import IdentityBook, build_identity, clean_subjects
from scan_eval.cloud import ScanResult
from scan_eval.cli import main as cli_main
from scan_eval.truth import rows_from_session


def jpeg(size=(800, 600)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (180, 120, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def photos(n=1):
    return [("files", (f"shelf{i}.jpg", jpeg(), "image/jpeg")) for i in range(n)]


@pytest.fixture
def demo_client():
    return TestClient(create_app(Settings(demo=True)))


# ------------------------------------------------------------------ basics


def test_index_and_static_are_served(demo_client):
    page = demo_client.get("/")
    assert page.status_code == 200 and "Booked" in page.text
    assert demo_client.get("/static/app.js").status_code == 200
    assert demo_client.get("/static/app.css").status_code == 200


def test_config(demo_client):
    cfg = demo_client.get("/api/config").json()
    assert cfg["demo"] is True and cfg["max_photos"] == 8 and cfg["spent_usd"] == 0


def test_demo_scan_returns_all_three_decisions_and_hebrew_matches(demo_client):
    data = demo_client.post("/api/scan", files=photos(1)).json()
    items = data["photos"][0]["items"]
    by_title = {i["read"]["title"]: i for i in items}
    assert by_title["Norwegian Wood"]["decision"] == "auto"
    assert by_title["בדנהיים עיר נופש"]["decision"] == "auto"
    assert by_title["Sapiens"]["decision"] == "auto"  # subtitle in the catalog does not block it
    assert by_title["Kafka on the Shre"]["decision"] == "confirm"
    assert by_title["Unknown Quiet Novel"]["decision"] == "manual"
    assert data["cost_usd"] == 0 and data["photos"][0]["unreadable"] == 1
    assert by_title["Norwegian Wood"]["candidates"][0]["work_id"] == "demo-nw"


# ------------------------------------------------------------------ limits and safety


def test_too_many_photos_is_rejected(demo_client):
    r = demo_client.post("/api/scan", files=photos(9))
    assert r.status_code == 400 and "at most 8" in r.json()["detail"]


def test_oversize_photo_is_rejected():
    client = TestClient(create_app(Settings(demo=True, max_photo_bytes=1000)))
    assert client.post("/api/scan", files=photos(1)).status_code == 413


def test_unknown_model_is_rejected_in_real_mode():
    reader = SimpleNamespace(read_bytes=lambda name, raw: ScanResult(name, "m"))
    client = TestClient(create_app(Settings(), reader_factory=lambda m: reader, catalog=demo_catalog()))
    r = client.post("/api/scan", files=photos(1), data={"model": "gpt-9"})
    assert r.status_code == 400


def test_access_token_protects_the_api():
    client = TestClient(create_app(Settings(demo=True, access_token="s3cret")))
    assert client.get("/api/config").status_code == 401
    assert client.get("/api/config", headers={"X-Access-Token": "wrong"}).status_code == 401
    assert client.get("/api/config", headers={"X-Access-Token": "s3cret"}).status_code == 200
    assert client.get("/").status_code == 200  # the page itself loads; only the API needs the token


def test_spending_cap_stops_further_scans():
    class Pricey:
        def read_bytes(self, name, raw):
            return ScanResult(name, "claude-haiku-4-5", reads=[], cost_usd=2.0)

    client = TestClient(create_app(Settings(max_spend_usd=3.0), reader_factory=lambda m: Pricey(), catalog=demo_catalog()))
    assert client.post("/api/scan", files=photos(2)).status_code == 200  # $4.00 spent, now over the cap
    blocked = client.post("/api/scan", files=photos(1))
    assert blocked.status_code == 429 and "cap" in blocked.json()["detail"]
    assert client.get("/api/config").json()["spent_usd"] == 4.0


def test_a_failed_photo_is_reported_not_fatal():
    class Flaky:
        def read_bytes(self, name, raw):
            return ScanResult(name, "m", error="ValueError: not a supported image")

    client = TestClient(create_app(Settings(), reader_factory=lambda m: Flaky(), catalog=demo_catalog()))
    data = client.post("/api/scan", files=photos(1)).json()
    assert data["photos"][0]["error"].startswith("ValueError") and data["photos"][0]["items"] == []


# ------------------------------------------------------------------ search, identity, log


def test_search_finds_hebrew_alt_titles(demo_client):
    results = demo_client.get("/api/search", params={"q": "רומן רוסי"}).json()
    assert results and results[0]["work_id"] == "demo-rr"
    assert demo_client.get("/api/search", params={"q": "x"}).status_code == 422


def test_identity_endpoint(demo_client):
    books = [
        {"title": "A", "authors": ["X"], "language": "he", "subjects": ["literary fiction", "israel"]},
        {"title": "B", "authors": ["X"], "language": "en", "subjects": ["literary fiction"]},
    ]
    data = demo_client.post("/api/identity", json={"books": books}).json()
    assert data["books"] == 2 and data["confidence"] == "low"
    assert data["subjects"][0]["name"] == "literary fiction"
    assert data["authors"][0] == {"name": "X", "count": 2, "share": 1.0}


def test_log_only_saved_when_a_data_dir_is_set(tmp_path):
    off = TestClient(create_app(Settings(demo=True)))
    assert off.post("/api/log", json={"items": []}).json() == {"saved": False}
    on = TestClient(create_app(Settings(demo=True, data_dir=str(tmp_path))))
    out = on.post("/api/log", json={"items": [{"photo": "a.jpg", "action": "auto"}]}).json()
    assert out["saved"] and (tmp_path / out["file"]).exists()


# ------------------------------------------------------------------ identity logic


def test_identity_statement_grows_with_data():
    assert build_identity([])["statement"].startswith("Scan a shelf")
    many = [IdentityBook(f"w{i}", f"T{i}", ("A",), "en", ("history", "science")) for i in range(10)]
    got = build_identity(many)
    assert got["confidence"] == "medium" and got["statement"] == "Mostly history and science."


def test_housekeeping_subjects_are_dropped():
    assert clean_subjects(["Accessible book", "Protected DAISY", "Reading Level-Grade 11", "Israel", "israel", "nyt:hardcover=2020"]) == ["israel"]


# ------------------------------------------------------------------ lean-mode ground truth


def test_session_log_becomes_ground_truth(tmp_path, capsys):
    session = {
        "items": [
            {"photo": "a.jpg", "position": 1, "action": "auto", "read": {"title": "Norwegian Wood"}, "final": {"work_id": "w1", "title": "Norwegian Wood", "authors": ["Haruki Murakami"], "language": "en"}},
            {"photo": "a.jpg", "position": 2, "action": "confirmed", "read": {"title": "רומן רוסי"}, "final": {"work_id": "w2", "title": "רומן רוסי", "authors": ["מאיר שלו"], "language": "he"}},
            {"photo": "a.jpg", "position": 3, "action": "removed", "read": {"title": "Accounting"}, "final": None},
            {"photo": "a.jpg", "position": 4, "action": "unmatched", "read": {"title": "???"}, "final": None},
        ]
    }
    assert [r.title for r in rows_from_session(session)] == ["Norwegian Wood", "רומן רוסי"]
    folder = tmp_path / "logs"
    folder.mkdir()
    (folder / "session-1.json").write_text(json.dumps(session, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "truth.csv"
    assert cli_main(["truth-from-log", "--logs", str(folder), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("photo,position,title") and "מאיר שלו" in text and "Accounting" not in text
