"""Ground truth for scan evaluation.

CSV columns: photo, position, title, author, language, work_id, unreadable
  - photo:      file name of the photo, e.g. IMG_0412.jpg
  - position:   any integer, only used for ordering and debugging
  - title, author: as the book is properly titled (Hebrew stays Hebrew)
  - language:   he, en, fr, ...
  - work_id:    optional catalog id (for example /works/OL45883W); leave empty to match by title
  - unreadable: 1 if even a person could not read the spine, else 0

In "lean mode" (docs/PROTOTYPE_PLAN.md section 0) the same rows are produced from the corrections
made in the confirm step, so nobody has to label photos separately.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TruthSpine:
    photo: str
    position: int
    title: str
    author: str = ""
    language: str = ""
    work_id: str = ""
    unreadable: bool = False


def load_truth(path: Path) -> list[TruthSpine]:
    rows: list[TruthSpine] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            rows.append(
                TruthSpine(
                    photo=raw["photo"].strip(),
                    position=int(raw.get("position") or 0),
                    title=(raw.get("title") or "").strip(),
                    author=(raw.get("author") or "").strip(),
                    language=(raw.get("language") or "").strip(),
                    work_id=(raw.get("work_id") or "").strip(),
                    unreadable=(raw.get("unreadable") or "0").strip() in ("1", "true", "True"),
                )
            )
    return rows


_KEEP = {"accepted", "auto", "confirm", "confirmed", "manual"}


def rows_from_session(payload: dict) -> list[TruthSpine]:
    """Turn one web session log into ground truth (lean mode: the user's confirmations are the labels).

    Removed books are not truth (the user said they are not on the shelf or not theirs), and books
    nobody matched are skipped because we do not know what they are.
    """
    rows: list[TruthSpine] = []
    for item in payload.get("items", []):
        final = item.get("final")
        if item.get("action") not in _KEEP or not final:
            continue
        authors = final.get("authors") or []
        rows.append(
            TruthSpine(
                photo=item.get("photo", ""),
                position=int(item.get("position") or 0),
                title=final.get("title", ""),
                author=authors[0] if authors else "",
                language=final.get("language", ""),
                work_id=final.get("work_id", ""),
            )
        )
    return rows


def write_truth(path: Path, rows: list[TruthSpine]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["photo", "position", "title", "author", "language", "work_id", "unreadable"])
        for r in rows:
            writer.writerow([r.photo, r.position, r.title, r.author, r.language, r.work_id, int(r.unreadable)])
