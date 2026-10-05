# Booked — Scanning & Taste Prototype Plan (1–2 weeks)

Status: plan only. Companion to `docs/SPEC.md` (§13.5). The prototype is a throwaway test harness, **not** the app: it exists to answer a few risky questions with real data before we commit to the architecture.

## 0. Lean mode (current decision)

There is no one available for 10–15 hours of labeling, so we evolve as we go. Instead of a separate labeled dataset, **the product's own confirm step becomes the labeling tool**:

- Start with **the founder's own home library** (dozens of Hebrew books plus English/Latin). Scan it shelf by shelf with the early harness; every correction the user makes in the confirm step (fix a title, pick the right match, mark "unreadable", manual add) is logged as ground truth together with the crop and the pipeline's guess. Expected user effort: ~1–2 hours, spread over a few sessions, and it is also the first real use of the product.
- Add shelves opportunistically from friends and family as they volunteer, using the same flow; no dedicated labeling sessions.
- Metrics are computed from the logged corrections (candidate recall, auto-accept precision, cost per correct book), per language. Treat results as **directional** with small samples and wide error bars; report counts, not just percentages.
- Hold-out discipline is relaxed but not dropped: freeze the first full shelf-set as a "test" and don't tune on it.
- The recommendations test shrinks to the founders' libraries plus 3–5 friends (blind rating of 10 recs each); skip the offline hold-out comparison if libraries are too small.
- Go/no-go bars in §2 stay, but are read as "good enough to continue" signals, not statistical proof.

The rest of this document describes the fuller version; use §0 wherever they conflict.

## 1. Why this prototype

The product depends on one thing working: **photo → mostly-right list of books → instant taste → good recommendations**, including in **Hebrew**. If scanning is unreliable or too expensive, the thesis fails; if it works, everything else is conventional engineering.

## 2. Questions to answer (and proposed go/no-go bars)

Bars are proposals — adjust before running, then don't move them after seeing results.

| # | Question | Metric | Proposed bar |
|---|---|---|---|
| Q1 | Can we find the book spines at all? | Spine detection recall on the labeled set | ≥ 90% |
| Q2 | Can we read them, per language? | **Candidate recall**: true book appears in the top-3 matches for a spine | EN/Latin ≥ 85%; Hebrew ≥ 75% |
| Q3 | Can we avoid wrong auto-accepts? | **Auto-accept precision** (matches shown as "confirmed" without user action) | ≥ 97% |
| Q4 | Does on-device OCR handle Hebrew and rotated text? | Same metrics, on-device only | Informational: decides whether Hebrew needs cloud |
| Q5 | What does it cost? | Cost per correctly identified book; cost per 3-photo onboarding | ≤ $0.03 per onboarding (hybrid) |
| Q6 | Is it fast enough? | Photo → results latency (p50/p90) | p90 ≤ 15 s per photo |
| Q7 | Does catalog matching cover Hebrew? | % of true books resolvable to a Work in the catalog | ≥ 80% EN, ≥ 60% Hebrew (rest handled by manual add) |
| Q8 | Do the recommendations feel good? | Blind friend ratings; offline hold-out recall | See §6 |

## 3. Dataset

**Shelf photos (target 60):**
- ~25 English/Latin-script, ~25 Hebrew, ~10 mixed.
- Vary on purpose: neat vs cluttered, tall/narrow shelves, horizontal stacks, rotated or vertical spine text (note the different reading direction conventions), glare, low light, near vs far, partially hidden spines, shelves with non-book items.
- Sources: founders, friends and family (with consent; faces/rooms cropped out). Store locally, not in the repo.

**Ground truth:** every visible spine labeled with its ISBN or catalog Work ID (plus "unreadable even for a human" flag). Use a simple labeling spreadsheet or small tool. Estimated effort: ~10 min per photo, ~10 hours total — the most important investment in this plan. Hold out 20% of photos as a test set that is not used to tune anything.

**Libraries for the recommendations test:** 10–15 friends who each provide ≥ 30 books (from the scans plus a few they add by hand) and are willing to rate recommendations blind.

## 4. Pipelines to compare (scan)

| Pipeline | What it is |
|---|---|
| **A. On-device only** | Apple Vision spine/text detection + text recognition → fuzzy catalog match |
| **B. Cloud only (full photo)** | Whole photo to a vision-language model → structured list of title/author/language/confidence → catalog match |
| **C. Hybrid (expected winner)** | On-device spine segmentation + OCR; confident spines go straight to matching; low-confidence spines are **cropped** and sent to the cloud model; then matching |
| **D. Barcode/search baseline** | Reference only: what a no-scan flow would cost the user in effort |

Models to test in B/C: a small model (Haiku 4.5) and a larger one (Sonnet 5.5). Notes: use structured output for the list; keep thinking/effort low for this extraction task; record token usage from every response; try both whole-photo and per-crop prompts.

**Day-1 checks (cheap, decisive):**
1. Does the target iOS version's Vision text recognition list Hebrew among its supported languages? (query the supported recognition languages at runtime on a real device.)
2. How does it handle rotated spines (90° either way) in Latin and Hebrew?
3. Is any available on-device text-recognition accuracy on Hebrew good enough to skip cloud for Hebrew shelves?

## 5. Matching experiment

- Catalog sources to test: Open Library (API/dumps), Wikidata, Google Books API (check terms), plus a Hebrew-capable source (e.g. national library open data — to be investigated).
- Matching approach: normalization (case, punctuation, niqqud/diacritics, transliteration), trigram fuzzy search, then embedding rerank using an open multilingual embedding model.
- Measure: Work-level match accuracy (top-1 and top-3), failure categories (OCR error, missing from catalog, translation/edition confusion, author-only spines), and the share that falls through to **unresolved/manual add**.
- Include translation cases deliberately (same Work in Hebrew and English).

## 6. Taste & recommendation mini-test

- Build book embeddings for Works in the test libraries (two embedding models compared if time permits).
- **Offline:** hide 20% of each friend's library, build a taste profile from the rest, measure recall@10 of the hidden books against a "popular in same genre" baseline.
- **Blind rating:** each friend rates 10 recommendations (5 from our content-based method, 5 from the baseline, shuffled, unlabeled) as *would read / maybe / no*. Bar: ours beats baseline on "would read" and reaches ≥ 40% "would read" overall.
- **"Why this?"**: generate one-line explanations with a small model for 5 of the recs; friends rate whether the reason is accurate and persuasive. Check no invented facts.
- Taste summary: show each friend their generated summary/taste card; ask "does this sound like me?" (1–5). Bar: median ≥ 4.

## 7. Instrumentation and cost accounting

- Log for every model call: model, input/output tokens, latency, request type (full-photo / crop / why-this), and compute cost at list price.
- Report cost per photo, per correct book and per onboarding for each pipeline.
- Expected spend for the whole prototype: well under $50 (tens of photos × a few pipelines × two models, plus reruns). Set a hard budget cap before starting.

## 8. Timeline

| When | Work |
|---|---|
| Days 1–2 | Day-1 checks (§4); labeling tool; start photo collection and friend recruiting; set up repo for the throwaway harness (separate folder, clearly marked as prototype) |
| Days 3–5 | Finish dataset + ground truth; Pipeline A and B running on all photos; first accuracy and cost table |
| Days 6–8 | Pipeline C (hybrid); matching experiment; tune on the training split only |
| Days 9–10 | Final run on the held-out test set; recommendations tests (offline + blind friend ratings) |
| Days 11–12 | Report, go/no-go, spec updates |

## 9. Deliverables

1. Results report: metrics per pipeline × language, cost table, failure analysis with example images.
2. Go/no-go per question (§2) and the **recommended production scan architecture**.
3. Updated `SPEC.md` (§6 scan pipeline, §13 stack and cost) based on evidence.
4. Backlog of the highest-impact accuracy fixes (e.g. guided capture tweaks).

## 10. Decision gates and fallbacks

| If we find… | Then… |
|---|---|
| Hybrid meets Q1–Q3, Q5 | Proceed with MVP as specced |
| On-device Hebrew OCR is poor | Route Hebrew shelves (or Hebrew-looking spines) to cloud; re-cost, likely still fine |
| Cloud accuracy is poor on messy shelves | Strengthen guided capture (closer, multi-pass, one shelf row at a time), add barcode-first and "scan one at a time" prominence |
| Cost is above bar | More aggressive on-device first, smaller model, tighter crops, per-user scan caps |
| Hebrew catalog coverage is thin | Lean harder on manual add + async resolution; invest in a Hebrew data source |
| Recs don't beat the baseline | Improve embeddings/features before launch; consider a short taste-question step to complement the scan |

## 11. Risks and mitigations

- **Small, biased dataset** (friends' shelves skew similar): deliberately collect varied shelves; report confidence intervals; treat results as directional.
- **Overfitting to the test set:** tune only on the training split; touch the held-out set once.
- **Privacy:** photos contain homes and sometimes people; get consent, crop, keep local, delete after the prototype.
- **Provider terms/data handling:** confirm no-training and retention terms for the model provider before sending any friend's photos.
- **Scope creep:** no UI polish, no accounts, no social features in the prototype.

## 12. What we need from you

- Confirm or adjust the bars in §2.
- Who can supply shelf photos, especially Hebrew shelves, and the ~10–15 friends for the recommendation test.
- Whether a founder or friend can do the ground-truth labeling (~10 hours) or whether to budget for help.
- An iPhone running the target iOS version for the on-device checks, and a model provider account with a budget cap for the cloud tests.
