"""Web prototype server.

    uvicorn booked.web.app:create_app --factory --host 127.0.0.1 --port 8000

Configuration is by environment variable (see Settings). This is a prototype for trying the scan
with your own shelves: it has no accounts. If you expose it beyond your own machine, set
BOOKED_ACCESS_TOKEN, because every scan spends API money.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from booked.catalog import Catalog, CatalogWork, OpenLibraryCatalog
from booked.matching import MatchResult, match
from scan_eval.cli import build_catalog
from scan_eval.cloud import CloudSpineReader
from scan_eval.pricing import MODELS

from .demo import DemoReader, demo_catalog
from .identity import IdentityBook, build_identity
from .limits import Caps, Ledger, LimitReached, parse_invites, who_is

STATIC = Path(__file__).parent / "static"


@dataclass
class Settings:
    model: str = "haiku"
    catalog: str = "openlibrary"  # openlibrary | fixture:PATH
    demo: bool = False
    access_token: str = ""
    max_spend_usd: float = 5.0
    data_dir: str = ""
    max_photos: int = 8
    max_photo_bytes: int = 15 * 1024 * 1024
    contact: str = ""  # shown to Open Library in the User-Agent; set it to a real address
    invites: str = ""  # "anna=x7k2,ben=p9q4": one code per person, so limits and usage are per person
    require_invite: bool = False  # public deployments: refuse to start without any code
    state_dir: str = ""  # where the usage ledger lives; empty keeps it in memory
    per_person_photos_per_day: int = 12
    total_photos_per_day: int = 60
    max_daily_usd: float = 1.0

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            model=e("BOOKED_MODEL", "haiku"),
            catalog=e("BOOKED_CATALOG", "openlibrary"),
            demo=e("BOOKED_DEMO", "") in ("1", "true", "yes"),
            access_token=e("BOOKED_ACCESS_TOKEN", ""),
            max_spend_usd=float(e("BOOKED_MAX_SPEND_USD", "5")),
            data_dir=e("BOOKED_DATA_DIR", ""),
            contact=e("BOOKED_CONTACT", ""),
            invites=e("BOOKED_INVITE_CODES", ""),
            require_invite=e("BOOKED_REQUIRE_INVITE", "") in ("1", "true", "yes"),
            state_dir=e("BOOKED_STATE_DIR", ""),
            per_person_photos_per_day=int(e("BOOKED_PHOTOS_PER_PERSON_PER_DAY", "12")),
            total_photos_per_day=int(e("BOOKED_PHOTOS_PER_DAY", "60")),
            max_daily_usd=float(e("BOOKED_MAX_DAILY_USD", "1")),
        )


class WorkOut(BaseModel):
    work_id: str
    title: str
    authors: list[str] = []
    language: str = ""
    subjects: list[str] = []
    year: int | None = None
    score: float | None = None


def work_out(work: CatalogWork, score: float | None = None) -> WorkOut:
    return WorkOut(
        work_id=work.id, title=work.title, authors=list(work.authors), language=work.language,
        subjects=list(work.subjects), year=work.year, score=None if score is None else round(score, 3),
    )


class BookIn(BaseModel):
    work_id: str = ""
    title: str
    authors: list[str] = []
    language: str = ""
    subjects: list[str] = []


class IdentityIn(BaseModel):
    books: list[BookIn] = Field(max_length=2000)


class LogIn(BaseModel):
    """What the user confirmed, kept (only if BOOKED_DATA_DIR is set) as ground truth for evaluation."""

    items: list[dict[str, Any]] = Field(max_length=2000)


def _match_payload(idx: str, m: MatchResult) -> dict:
    return {
        "id": idx,
        "read": {"title": m.read.title, "author": m.read.author, "language": m.read.language, "confidence": m.read.confidence},
        "decision": m.decision.value,
        "reasons": list(m.reasons),
        "candidates": [work_out(c.work, c.score).model_dump() for c in m.candidates],
    }


def create_app(
    settings: Settings | None = None,
    *,
    reader_factory: Callable[[str], Any] | None = None,
    catalog: Catalog | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if catalog is None:
        if settings.demo:
            catalog = demo_catalog()
        elif settings.catalog == "openlibrary":
            ua = f"Booked/0.1 (prototype; {settings.contact or 'no contact set'})"
            catalog = OpenLibraryCatalog(user_agent=ua)
        else:
            catalog = build_catalog(settings.catalog)

    if reader_factory is None:
        if settings.demo:
            reader_factory = lambda _model: DemoReader()  # noqa: E731
        else:
            clients: dict[str, Any] = {}

            def reader_factory(model: str) -> CloudSpineReader:  # type: ignore[misc]
                if "client" not in clients:
                    import anthropic  # credentials come from ANTHROPIC_API_KEY or `ant auth login`

                    clients["client"] = anthropic.Anthropic()
                return CloudSpineReader(clients["client"], MODELS[model])

    app = FastAPI(title="Booked prototype", docs_url="/api/docs", openapi_url="/api/openapi.json")
    invites = parse_invites(settings.invites)
    open_access = not invites and not settings.access_token
    if settings.require_invite and open_access:
        raise RuntimeError("BOOKED_REQUIRE_INVITE is set but no BOOKED_INVITE_CODES or BOOKED_ACCESS_TOKEN: refusing to start an open server that spends money")
    ledger = Ledger(
        Path(settings.state_dir) / "usage.sqlite3" if settings.state_dir else None,
        Caps(settings.per_person_photos_per_day, settings.total_photos_per_day, settings.max_daily_usd, settings.max_spend_usd),
    )

    def require_token(x_access_token: str = Header(default="")) -> str:
        if open_access:
            return "local"
        who = who_is(x_access_token, settings.access_token, invites)
        if who is None:
            raise HTTPException(status_code=401, detail="missing or wrong invite code")
        return who

    guard = [Depends(require_token)]

    @app.get("/api/config")
    def config(who: str = Depends(require_token)) -> dict:
        today = ledger.today(who)
        return {
            "photos_left_today": today["photos_left_today"],
            "demo": settings.demo,
            "model": settings.model,
            "logging": bool(settings.data_dir),
            "max_photos": settings.max_photos,
            "spent_usd": today["spent_month_usd"],
            "max_spend_usd": settings.max_spend_usd,
        }

    @app.post("/api/scan")
    def scan(files: list[UploadFile] = File(...), model: str = Form(""), who: str = Depends(require_token)) -> dict:
        model = model or settings.model
        if not settings.demo and model not in MODELS:
            raise HTTPException(400, f"unknown model {model!r}; choose one of {sorted(MODELS)}")
        if not files:
            raise HTTPException(400, "no photos")
        if len(files) > settings.max_photos:
            raise HTTPException(400, f"at most {settings.max_photos} photos at a time")

        uploads: list[tuple[str, bytes]] = []
        for f in files:
            raw = f.file.read(settings.max_photo_bytes + 1)
            if len(raw) > settings.max_photo_bytes:
                raise HTTPException(413, f"{f.filename}: photo is larger than {settings.max_photo_bytes // 1024 // 1024} MB")
            uploads.append((f.filename or "photo.jpg", raw))

        try:
            ledger.reserve(who, len(uploads))
        except LimitReached as stop:
            raise HTTPException(429, stop.message) from None

        reader = reader_factory(model)
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=min(3, len(uploads))) as pool:
            results = list(pool.map(lambda u: reader.read_bytes(*u), uploads))

        photos: list[dict] = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for pi, res in enumerate(results):
                reads = res.spine_reads()
                matches = list(pool.map(lambda r: match(r, catalog), reads))
                photos.append(
                    {
                        "photo": res.photo,
                        "error": res.error,
                        "unreadable": res.unreadable,
                        "cost_usd": round(res.cost_usd, 5),
                        "latency_s": round(res.latency_s, 2),
                        "items": [_match_payload(f"{pi}-{i}", m) for i, m in enumerate(matches)],
                    }
                )
        cost = sum(r.cost_usd for r in results)
        ledger.record_cost(who, cost)
        return {
            "model": model,
            "photos": photos,
            "cost_usd": round(cost, 5),
            "elapsed_s": round(time.monotonic() - started, 2),
            "spent_usd": ledger.today(who)["spent_month_usd"],
            "photos_left_today": ledger.today(who)["photos_left_today"],
        }

    @app.get("/api/search", dependencies=guard)
    def search(q: str = Query(min_length=2, max_length=200)) -> list[WorkOut]:
        return [work_out(w) for w in catalog.search(q, limit=8)]

    @app.post("/api/identity", dependencies=guard)
    def identity(body: IdentityIn) -> dict:
        return build_identity(
            [IdentityBook(b.work_id, b.title, tuple(b.authors), b.language, tuple(b.subjects)) for b in body.books]
        )

    @app.post("/api/log", dependencies=guard)
    def log(body: LogIn) -> dict:
        if not settings.data_dir:
            return {"saved": False}
        folder = Path(settings.data_dir)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"session-{int(time.time())}.json"
        path.write_text(json.dumps(body.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": True, "file": path.name}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
