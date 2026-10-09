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
