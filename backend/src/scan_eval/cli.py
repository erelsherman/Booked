"""Command line for the scan evaluation.

    python -m scan_eval read  --photos DIR --model haiku --out data/haiku.jsonl
    python -m scan_eval score --reads data/haiku.jsonl --truth data/truth.csv --catalog openlibrary

``read`` calls a model and costs money (set ANTHROPIC_API_KEY, or log in with `ant auth login`).
``score`` is free and can be re-run with different thresholds or catalogs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from booked.catalog import Catalog, CatalogWork, InMemoryCatalog, OpenLibraryCatalog
from booked.matching import Thresholds

from .cloud import CloudSpineReader, ScanResult
from .metrics import evaluate
from .pricing import MODELS
from .truth import load_truth, rows_from_session, write_truth

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def load_fixture_catalog(path: Path) -> InMemoryCatalog:
    """JSON list of works: {id, title, authors, language, alt_titles, subjects}."""
    catalog = InMemoryCatalog()
    for raw in json.loads(path.read_text(encoding="utf-8")):
        catalog.add(
            CatalogWork(
                id=raw["id"],
                title=raw["title"],
                authors=tuple(raw.get("authors", ())),
                language=raw.get("language", "en"),
                alt_titles=tuple(raw.get("alt_titles", ())),
                subjects=tuple(raw.get("subjects", ())),
            )
        )
    return catalog


def build_catalog(spec: str) -> Catalog:
    if spec == "openlibrary":
        return OpenLibraryCatalog()
    if spec.startswith("fixture:"):
        return load_fixture_catalog(Path(spec.removeprefix("fixture:")))
    raise SystemExit(f"unknown catalog {spec!r}: use 'openlibrary' or 'fixture:PATH'")


def cmd_read(args: argparse.Namespace) -> int:
    import anthropic  # imported here so `score` works without credentials

    photos = sorted(p for p in Path(args.photos).iterdir() if p.suffix.lower() in PHOTO_SUFFIXES)
    if not photos:
        raise SystemExit(f"no photos found in {args.photos}")
    reader = CloudSpineReader(anthropic.Anthropic(), MODELS[args.model], max_edge=args.max_edge)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0.0
    with out.open("w", encoding="utf-8") as fh:
        for photo in photos:
            result = reader.read_photo(photo)
            fh.write(result.to_json() + "\n")
            total += result.cost_usd
            status = result.error or f"{len(result.reads)} read, {result.unreadable} unreadable"
            print(f"{photo.name}: {status} (${result.cost_usd:.4f})", file=sys.stderr)
    print(f"done: {len(photos)} photos, ${total:.4f}", file=sys.stderr)
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    results = [
        ScanResult.from_json(line)
        for line in Path(args.reads).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = evaluate(load_truth(Path(args.truth)), results, build_catalog(args.catalog), thresholds=Thresholds(auto=args.auto))
    print(report.to_markdown())
    return 0


def cmd_truth_from_log(args: argparse.Namespace) -> int:
    rows = []
    for log in sorted(Path(args.logs).glob("session-*.json")):
        rows.extend(rows_from_session(json.loads(log.read_text(encoding="utf-8"))))
    write_truth(Path(args.out), rows)
    print(f"wrote {len(rows)} rows to {args.out}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scan_eval")
    sub = parser.add_subparsers(dest="command", required=True)

    read = sub.add_parser("read", help="photos to spine reads (costs money)")
    read.add_argument("--photos", required=True)
    read.add_argument("--model", choices=sorted(MODELS), default="haiku")
    read.add_argument("--out", required=True)
    read.add_argument("--max-edge", type=int, default=2000)
    read.set_defaults(func=cmd_read)

    score = sub.add_parser("score", help="reads plus truth to a report (free)")
    score.add_argument("--reads", required=True)
    score.add_argument("--truth", required=True)
    score.add_argument("--catalog", default="openlibrary")
    score.add_argument("--auto", type=float, default=Thresholds().auto)
    score.set_defaults(func=cmd_score)

    log = sub.add_parser("truth-from-log", help="web session logs to a ground-truth CSV (lean mode)")
    log.add_argument("--logs", required=True, help="the BOOKED_DATA_DIR folder")
    log.add_argument("--out", required=True)
    log.set_defaults(func=cmd_truth_from_log)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
