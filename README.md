# Booked

**Your world of books.** Scan your shelf. See what your friends are reading. Discover what to read next.

Status: planning is done, coding has started with the parts that carry the most risk.

## Where things are

| Path | What it is |
|---|---|
| `docs/SPEC.md` | Product spec and build prompt |
| `docs/PROTOTYPE_PLAN.md` | The scanning and taste prototype, including "lean mode" (your own library is the dataset) |
| `docs/DESIGN.md`, `SOCIAL_AND_PREMIUM.md`, `HABIT_LOOPS.md`, `PAYWALLS.md` | Design direction, social and premium decisions, habit loops, paywall map |
| `backend/` | Python: domain rules, matching, taste engine, and the scan evaluation harness |
| Design canvas | https://claude.ai/artifact/SWpb3fcJKAqLq9ez2yfBhp (private) |

The iOS app (SwiftUI) is not started. It needs macOS and Xcode, so it is written on a Mac against the API contract the backend will publish.

## What exists today (and how much of it is verified)

| Piece | State |
|---|---|
| Library rules: collections, visibility, taste inclusion, auto-share (`backend/src/booked/library.py`) | Implemented, unit tested |
| Text normalisation for Hebrew and Latin (`text.py`) | Implemented, unit tested |
| Matching spine reads to catalog works, with auto / confirm / manual decisions (`matching.py`) | Implemented, unit tested on a small fixture catalog |
| Taste profile and recommendations, stage 1 (`taste.py`) | Implemented with a stand-in embedder, unit tested. The real multilingual embedding model is not wired in |
| Scan evaluation harness (`backend/src/scan_eval/`) | Implemented. Tested against a **fake** model client only |
| Open Library client (`catalog.py`) | Tested against a mock only. **Not yet run against the live service** |
| Postgres schema, API, auth, iOS app | Not started |

Nothing here has been run on real shelf photos yet. That is the next step and the point of the prototype.

## Quick start

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See `backend/README.md` for running the scan evaluation on your own shelf photos.
