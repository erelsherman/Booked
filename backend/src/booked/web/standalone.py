"""Build the single-page demo: the same UI as the web prototype, answering its own API calls with sample data.

    python -m booked.web.standalone out.html

No server and no API key: the page reads sample books for any photo, so the whole flow (scan, check,
Reader Identity, the Premium demo) can be tried from a phone. It cannot read real photos; for that,
run the server (backend/README.md). The output is a page fragment (title, style, body, scripts) that
can be published as is.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from .app import Settings, create_app
from .demo import demo_catalog

STATIC = Path(__file__).parent / "static"


def _json_for_script(data: object) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def build_page() -> str:
    client = TestClient(create_app(Settings(demo=True)))
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 120, 60)).save(buf, format="JPEG")
    scan = client.post("/api/scan", files=[("files", ("demo.jpg", buf.getvalue(), "image/jpeg"))]).json()
    scan["photos"][0]["photo"] = "your-photo.jpg"
    config = client.get("/api/config").json()
    config.update(max_spend_usd=0, spent_usd=0, logging=False)
    catalog = [
        {"id": w.id, "title": w.title, "authors": list(w.authors), "language": w.language,
         "alt_titles": list(w.alt_titles), "subjects": list(w.subjects), "year": w.year}
        for w in demo_catalog().works
    ]
    mock = {"config": config, "scan": scan, "catalog": catalog}
    fonts = (
        "https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600"
        "&family=Heebo:wght@400;500;600;700&family=Frank+Ruhl+Libre:wght@500;700&display=swap"
    )
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    return (
        "<title>Booked prototype</title>\n"
        f'<link href="{fonts}" rel="stylesheet">\n'
        f"<style>\n{css}\n</style>\n"
        '<main id="app" aria-live="polite"></main>\n'
        f"<script>window.BOOKED_MOCK = {_json_for_script(mock)};</script>\n"
        f"<script>\n{js}\n</script>\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m booked.web.standalone OUT.html", file=sys.stderr)
        return 2
    Path(args[0]).write_text(build_page(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
