# Booked backend

Python 3.11+. Two packages in `src/`:

- `booked`: domain logic (library rules, text normalisation, matching, taste engine)
- `scan_eval`: the harness that answers "can we read Hebrew and English spines well enough, at what cost?"

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Running the scan evaluation on your own shelves

This is the prototype from `docs/PROTOTYPE_PLAN.md`. It is split in two so the paid step runs once.

1. **Photos.** Put JPEG, PNG or WebP photos in a folder outside the repo, for example `~/booked-data/photos/` (`data/` is git-ignored if you keep it inside the repo). Convert HEIC to JPEG first. Take them as the app will: one shelf, or a wall in a few passes.
2. **Ground truth.** A CSV with one row per visible spine, in `~/booked-data/truth.csv`:

   ```
   photo,position,title,author,language,work_id,unreadable
   IMG_0412.jpg,1,בדנהיים עיר נופש,אהרן אפלפלד,he,,0
   IMG_0412.jpg,2,Norwegian Wood,Haruki Murakami,en,,0
   IMG_0412.jpg,3,,,,,1
   ```

   `work_id` is optional (an Open Library id such as `/works/OL45883W`); without it a book counts as correct when the title is at least 85% similar. Mark spines nobody could read with `unreadable=1`. For your own library this is about an hour of typing for a few dozen books, and it is the most valuable hour in the project.
3. **Read** (costs money; needs an API key via `ANTHROPIC_API_KEY`, or `ant auth login`):

   ```bash
   python -m scan_eval read --photos ~/booked-data/photos --model haiku  --out ~/booked-data/haiku.jsonl
   python -m scan_eval read --photos ~/booked-data/photos --model sonnet --out ~/booked-data/sonnet.jsonl
   ```

   Expect roughly a couple of cents per photo; the command prints the exact cost per photo and a total. Prices in `scan_eval/pricing.py` were cached on 2026-09-25: check them.
4. **Score** (free, repeatable):

   ```bash
   python -m scan_eval score --reads ~/booked-data/haiku.jsonl --truth ~/booked-data/truth.csv --catalog openlibrary
   ```

   You get recall, candidate recall at 3, auto-accept precision per language, cost per photo, cost per correct book, cost per 3-photo onboarding and latency. Compare them with the bars in `docs/PROTOTYPE_PLAN.md` section 2.

   Use `--catalog fixture:catalog.json` to score against a small hand-made catalog (`id`, `title`, `authors`, `language`, `alt_titles`, `subjects`), for example if Open Library coverage of a Hebrew book is poor. That is itself a finding.

## Web prototype: try it with your own shelves from your phone

Yes, a web app can use the phone camera. The page has a **Take a photo** button (opens the native camera, works over plain http on a phone) and **Choose photos** (upload from the gallery). A live in-page viewfinder (`getUserMedia`) needs https and is a later improvement; photo upload is the simplest and most reliable path, and it is what this prototype uses.

```bash
pip install -e ".[web]"

# 1. No key, no network: try the flow with built-in demo data
BOOKED_DEMO=1 uvicorn booked.web.app:create_app --factory --host 127.0.0.1 --port 8000

# 2. For real: your key, your photos, Open Library as the catalog
export ANTHROPIC_API_KEY=...
export BOOKED_CONTACT=you@example.com        # Open Library asks API users to identify themselves
export BOOKED_DATA_DIR=~/booked-data/logs    # optional: saves what you confirmed, as ground truth
uvicorn booked.web.app:create_app --factory --host 0.0.0.0 --port 8000
```

Open `http://<your-computer-ip>:8000` on the phone (same Wi-Fi). Flow: take or choose photos, read, fix anything wrong (pick the right candidate, search, add by hand, remove books that are not yours), see your Reader Identity, download your books as JSON or CSV.

Safety: there are no accounts, and every scan spends API money.
- Run it on your own machine and your own network only. To use it from anywhere, put it behind https and set `BOOKED_ACCESS_TOKEN=<random string>`, then open `https://host/#token=<random string>`.
- `BOOKED_MAX_SPEND_USD` (default 5) stops scans once the session spend reaches it; restart to reset.
- `?model=sonnet` in the URL switches model for a comparison (`haiku` is the default).
- Photos are processed in memory and not written to disk. With `BOOKED_DATA_DIR` set, only the list of books you confirmed is saved.

**Lean-mode ground truth:** after a few sessions, turn your confirmations into a truth file and score any model against it:

```bash
python -m scan_eval truth-from-log --logs ~/booked-data/logs --out ~/booked-data/truth.csv
python -m scan_eval score --reads ~/booked-data/haiku.jsonl --truth ~/booked-data/truth.csv
```

`scripts/smoke_web.py` is a browser walkthrough of the demo flow (needs Playwright).

## Things to know

- **Hebrew author names.** Catalog entries need author aliases in each script (for example from Wikidata). Without them, a Hebrew spine author cannot be verified against "Aharon Appelfeld", so the match is sent to the user to confirm instead of auto-accepted. This is deliberate: it favours asking over silently adding the wrong book.
- **Auto-accept precision is the number to watch.** A wrong auto-accept silently pollutes someone's library; a confirm costs a tap.
- **Not yet tested for real:** the model calls (only a fake client in tests), and the Open Library client against the live service. First real run may need small fixes (for example if a model rejects a request parameter; the reader falls back from structured output to plain JSON on its own).
- The on-device half of the hybrid pipeline (Apple Vision) is iOS-only and is not in this repo yet.
