import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from booked.catalog import OpenLibraryCatalog
from scan_eval.cli import build_catalog, main
from scan_eval.cloud import CloudSpineReader, ScanResult, extract_json, prepare_image
from scan_eval.metrics import evaluate
from scan_eval.pricing import MODELS, Usage, compute_cost
from scan_eval.truth import TruthSpine, load_truth


def make_photo(tmp_path: Path, name="shelf.jpg", size=(3000, 1500)) -> Path:
    p = tmp_path / name
    Image.new("RGB", size, (200, 120, 60)).save(p)
    return p


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create"""

    def __init__(self, reply: dict | str, *, fail_structured: bool = False, stop_reason="end_turn"):
        self.reply = reply if isinstance(reply, str) else json.dumps(reply)
        self.fail_structured = fail_structured
        self.stop_reason = stop_reason
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_structured and "format" in kwargs.get("output_config", {}):
            raise RuntimeError("output_config.format is not supported for this model")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.reply)],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=2000, output_tokens=500, cache_read_input_tokens=0, cache_creation_input_tokens=0),
        )


SPINES = {
    "spines": [
        {"shelf": 1, "position": 1, "title": "Norwegian Wood", "author": "Haruki Murakami", "language": "en", "confidence": 0.95, "legible": True},
        {"shelf": 1, "position": 2, "title": "בדנהיים עיר נופש", "author": "אהרן אפלפלד", "language": "he", "confidence": 0.9, "legible": True},
        {"shelf": 1, "position": 3, "title": "", "author": "", "language": "", "confidence": 0.1, "legible": False},
    ]
}


# ------------------------------------------------------------------ pricing


def test_cost_computation():
    spec = MODELS["haiku"]
    cost = compute_cost(spec, Usage(input_tokens=2000, output_tokens=500))
    assert cost == pytest.approx(2000 * 1.0 / 1e6 + 500 * 5.0 / 1e6)
    cached = compute_cost(spec, Usage(cache_read_tokens=10_000))
    assert cached == pytest.approx(10_000 * 1.0 / 1e6 * 0.1)


# ------------------------------------------------------------------ reader


def test_reader_request_shape_and_result(tmp_path):
    client = FakeClient(SPINES)
    result = CloudSpineReader(client, MODELS["haiku"]).read_photo(make_photo(tmp_path))
    call = client.calls[0]
    assert call["model"] == "claude-haiku-4-5"
    assert "effort" not in call["output_config"]  # not supported on Haiku
    assert call["output_config"]["format"]["type"] == "json_schema"
    image = call["messages"][0]["content"][0]
    assert image["source"]["media_type"] == "image/jpeg"
    assert len(result.reads) == 2 and result.unreadable == 1
    assert result.cost_usd == pytest.approx(2000 / 1e6 + 500 * 5 / 1e6)
    assert not result.error


def test_sonnet_request_turns_thinking_off_and_effort_low(tmp_path):
    client = FakeClient(SPINES)
    CloudSpineReader(client, MODELS["sonnet"]).read_photo(make_photo(tmp_path))
    call = client.calls[0]
    assert call["thinking"] == {"type": "between_tools"}
    assert call["output_config"]["effort"] == "low"


def test_falls_back_to_plain_json_when_structured_output_is_rejected(tmp_path):
    client = FakeClient("Here you go:\n```json\n" + json.dumps(SPINES, ensure_ascii=False) + "\n```", fail_structured=True)
    result = CloudSpineReader(client, MODELS["haiku"]).read_photo(make_photo(tmp_path))
    assert len(client.calls) == 2 and "format" not in client.calls[1].get("output_config", {})
    assert len(result.reads) == 2


def test_refusal_and_bad_json_are_recorded_not_raised(tmp_path):
    refused = CloudSpineReader(FakeClient(SPINES, stop_reason="refusal"), MODELS["haiku"]).read_photo(make_photo(tmp_path))
    assert "refusal" in refused.error and refused.cost_usd > 0
    broken = CloudSpineReader(FakeClient("not json"), MODELS["haiku"]).read_photo(make_photo(tmp_path, "b.jpg"))
    assert broken.error


def test_image_is_downscaled(tmp_path):
    data, media = prepare_image(make_photo(tmp_path, size=(4000, 3000)), max_edge=1000)
    from io import BytesIO

    assert max(Image.open(BytesIO(data)).size) == 1000 and media == "image/jpeg"


def test_unsupported_image_type(tmp_path):
    p = tmp_path / "x.heic"
    p.write_bytes(b"x")
    with pytest.raises(ValueError, match="HEIC"):
        prepare_image(p)


def test_extract_json_variants():
    assert extract_json('prefix {"a": 1} suffix') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("nothing here")


def test_scan_result_roundtrip():
    r = ScanResult("p.jpg", "m", reads=[{"title": "T", "author": "A", "language": "en", "confidence": 0.9}], cost_usd=0.01)
    again = ScanResult.from_json(r.to_json())
    assert again == r and again.spine_reads()[0].title == "T"


# ------------------------------------------------------------------ metrics


def truth_rows():
    return [
        TruthSpine("shelf.jpg", 1, "Norwegian Wood", "Haruki Murakami", "en"),
        TruthSpine("shelf.jpg", 2, "בדנהיים עיר נופש", "אהרן אפלפלד", "he", work_id="w-bad"),
        TruthSpine("shelf.jpg", 3, "Dune", "Frank Herbert", "en"),  # the reader missed this one
        TruthSpine("shelf.jpg", 4, "???", "", "", unreadable=True),
    ]


def result_with(reads, **kw):
    return ScanResult("shelf.jpg", "claude-haiku-4-5", reads=reads, cost_usd=0.02, latency_s=3.0, **kw)


def test_evaluate_counts_recall_precision_and_cost(catalog):
    reads = [
        {"title": "Norwegian Wood", "author": "Haruki Murakami", "language": "en", "confidence": 0.95},
        {"title": "בדנהיים עיר נופש", "author": "אהרן אפלפלד", "language": "he", "confidence": 0.9},
        {"title": "Some Invented Book", "author": "Nobody", "language": "en", "confidence": 0.9},
    ]
    report = evaluate(truth_rows(), [result_with(reads)], catalog)
    assert report.overall.truth == 3 and report.unreadable_truth == 1
    assert report.overall.found == 2 and report.overall.spine_recall == pytest.approx(2 / 3)
    assert report.overall.candidate_recall == 1.0
    assert report.by_language["he"].auto_precision == 1.0
    assert report.overall.auto_precision == 1.0
    assert report.cost_per_photo == pytest.approx(0.02)
    assert report.cost_per_correct_book == pytest.approx(0.02 / 2)
    assert report.cost_per_three_photo_onboarding == pytest.approx(0.06)
    md = report.to_markdown()
    assert "| he |" in md and "per 3-photo onboarding" in md


def test_wrong_auto_accept_lowers_precision(catalog):
    reads = [{"title": "Norwegian Wood", "author": "Haruki Murakami", "language": "en", "confidence": 0.95}]
    truth = [TruthSpine("shelf.jpg", 1, "Norwegian Wood", "Haruki Murakami", "en", work_id="w-wub")]  # truth says another work
    report = evaluate(truth, [result_with(reads)], catalog)
    assert report.overall.auto == 1 and report.overall.auto_correct == 0
    assert report.overall.auto_precision == 0.0


def test_hallucinated_auto_accept_is_counted(catalog):
    reads = [{"title": "The Hobbit", "author": "J.R.R. Tolkien", "language": "en", "confidence": 0.99}]
    report = evaluate([TruthSpine("shelf.jpg", 1, "Dune", "Frank Herbert", "en")], [result_with(reads)], catalog)
    assert report.hallucinated_auto == 1
    assert report.overall.found == 0


# ------------------------------------------------------------------ truth, catalog, cli


def test_load_truth_csv(tmp_path):
    p = tmp_path / "truth.csv"
    p.write_text(
        "photo,position,title,author,language,work_id,unreadable\n"
        "a.jpg,1,בדנהיים עיר נופש,אהרן אפלפלד,he,/works/OL1W,0\n"
        "a.jpg,2,,,,,1\n",
        encoding="utf-8",
    )
    rows = load_truth(p)
    assert rows[0].work_id == "/works/OL1W" and rows[0].language == "he"
    assert rows[1].unreadable


def test_openlibrary_mapping_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search.json"
        assert request.url.params["language"] == "heb"
        assert "Booked" in request.headers["user-agent"]
        return httpx.Response(
            200,
            json={"docs": [{"key": "/works/OL1W", "title": "אישה בורחת מבשורה", "author_name": ["דוד גרוסמן"], "language": ["heb"], "first_publish_year": 2008, "subject": ["Israel"]}, {"title": "no key"}]},
        )

    cat = OpenLibraryCatalog(transport=httpx.MockTransport(handler))
    works = cat.search("אישה בורחת מבשורה", language="he")
    assert len(works) == 1
    assert works[0].id == "/works/OL1W" and works[0].language == "he" and works[0].year == 2008


def test_cli_score_end_to_end(tmp_path, capsys):
    fixture = tmp_path / "catalog.json"
    fixture.write_text(
        json.dumps([{"id": "w-nw", "title": "Norwegian Wood", "authors": ["Haruki Murakami"], "language": "en"}]), encoding="utf-8"
    )
    reads = tmp_path / "reads.jsonl"
    reads.write_text(
        result_with([{"title": "Norwegian Wood", "author": "Haruki Murakami", "language": "en", "confidence": 0.9}]).to_json() + "\n",
        encoding="utf-8",
    )
    truth = tmp_path / "truth.csv"
    truth.write_text("photo,position,title,author,language,work_id,unreadable\nshelf.jpg,1,Norwegian Wood,Haruki Murakami,en,,0\n", encoding="utf-8")
    code = main(["score", "--reads", str(reads), "--truth", str(truth), "--catalog", f"fixture:{fixture}"])
    out = capsys.readouterr().out
    assert code == 0 and "| en |" in out and "100%" in out


def test_build_catalog_rejects_unknown():
    with pytest.raises(SystemExit):
        build_catalog("nope")
