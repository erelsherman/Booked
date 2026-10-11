# Booked

**Your world of books.** Scan your shelf. See what your friends are reading. Discover what to read next.

Status: planning and design are done for the first loop (scan, identity, friends circle). Coding has started with the parts that carry the most risk, plus a prototype that runs inside Claude.

## Where things are

| Path | What it is |
|---|---|
| `docs/SPEC.md` | Product spec and build prompt |
| `docs/PROTOTYPE_PLAN.md` | The scanning and taste prototype, including "lean mode" (your own library is the dataset) |
| `docs/DESIGN.md`, `SOCIAL_AND_PREMIUM.md`, `HABIT_LOOPS.md`, `PAYWALLS.md` | Design direction, social and premium decisions, habit loops, paywall map |
| `docs/SOCIAL_ADDITIONS.md` | Seven additions to the friends circle (status and rating, now reading, friends on the book page, ask your circle, closing the loop, Blend, digest and recap): reasoning and flows |
| `docs/DEPLOY.md` | Step-by-step: put the prototype online for friends, with spending limits |
| `backend/` | Python: domain rules, matching, taste engine, and the scan evaluation harness |
| Design canvas | https://claude.ai/artifact/SWpb3fcJKAqLq9ez2yfBhp (private). Includes the friends flow (boards 3c and 22 to 22m), the plan board "Build your circle: plan" and the Paywall map |
| Live prototype in Claude | https://claude.ai/artifact/L84fhVCYBu9QysTMiUmatu (private). Built from `backend/src/booked/web/` with `python -m booked.web.standalone --live` |

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
| Web prototype (`backend/src/booked/web/`): take or upload photos, confirm books, Reader Identity | Implemented. API tested; UI walked through in a phone-sized browser in demo mode. **Not yet run with a real model or the live catalog** |
| Live prototype in Claude (`standalone.py --live`): sign-in with the Claude account, scan by photo, check books, identity drawer on Home, private library, wishlist, stories, friends and following, feed with Bravo, "Your next read" (a book three or more followed friends have on their shared shelves, otherwise a pick from Claude) and recommendations (asked from Claude), sharing presets, delete my data | Implemented. Walkthrough tested in a browser with fakes for Claude's sign-in, storage and "ask Claude" (`backend/scripts/smoke_social.py`). **Not yet run on real shelf photos or by real friends** |
| Render deployment with invite codes and spending limits (`render.yaml`, `docs/DEPLOY.md`) | Written. The Docker image has not been built and the app has not run with a real key |
| Postgres schema, real API, auth, iOS app, phone and email contact import, push notifications, real invite links | Not started |

Nothing here has been run on real shelf photos yet. That is the next step and the point of the prototype.

Product rule: scanning and building your circle are never capped, metered or paywalled (see `docs/PAYWALLS.md`). Inside your circle is free; curiosity about people outside it, or deeper analysis, is Premium.

## Quick start

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See `backend/README.md` for running the scan evaluation on your own shelf photos.
