# Booked — Product Spec & Build Prompt (v0.1, planning only)

> **Your world of books.**
> Scan your shelf. See what your friends are reading. Discover what to read next.

Status: planning. Nothing is built. This document is both the product spec and the brief to hand to an engineering/design effort (human or AI).

Origin: strategy feedback on Velato (a friend's book app) — Booked is a separate app by a different team with the same passion; the two may collaborate later.

---

## 1. Thesis

The core user problem is **deciding what to read next**. It is *not* tracking books.

The library is the **cold-start solution**: scanning a shelf makes taste onboarding nearly zero effort, and taste is the engine for recommendations and for finding people like you.

```
Photo → ~100 books → instant taste graph → immediate recommendations
      → "find people with my taste" → invite / follow → better recommendations
```

Think *Spotify Discover Weekly + Strava social graph, applied to books.*

### Principles
1. **Every feature must tighten the loop above**, or it is out.
2. **Taste is the product.** Recommendations are available from the first minute after onboarding.
3. **Social is the multiplier**, not a bolt-on: friends and similar readers are the strongest signal.
4. **Never a dead end.** If a book can't be found, the user can still add it, and it gets resolved over time.
5. **Privacy by default.** A shelf reveals a lot about a person; the user controls exposure at the book / collection level.
6. **Not a wine cellar.** No emphasis on physical location, loaning, or shelf management.

### Non-goals (explicitly out)
Physical shelf-location management, loaning/lending tracking, premium/monetization, hosting or distributing copyrighted files, B2B.

---

## 2. Target & platform

- **Platform:** iOS first, native SwiftUI (camera + Vision/VisionKit control matters for the scan, which is the differentiator). Android later against the same backend.
- **Languages (MVP):** English, Hebrew (RTL first-class), and other Latin-script languages (French, Spanish, Italian, German, …). Everything else: best effort. *(Assumption: "Latin languages" = Latin-script languages, not the Latin language itself — confirm.)*
- **Initial users:** founders' and friends' circles (~50–100 readers) as a seeded network.

---

## 3. Core user flow

### 3.1 Onboarding & scan
1. Sign in (Sign in with Apple / email). Offer **follow friends** (contacts / invite link) during sign-up.
2. **Scan a shelf**: one or several photos. Assume shelves are messy — spines may be rotated, partially hidden, multi-language.
3. Scanner proposes matches with confidence scores; low-confidence items go to a quick confirm.
4. After the scan: *"Anything missing?"* → add by **search**, **barcode**, or **one-at-a-time scan**, or **manual add** (see §5.3).
5. **Triage the shelf** (swipe/tap, fast): for each book —
   - *Keep in my library* (default),
   - *Move to a collection* (e.g. "Dana's books", "Work", "Kids"),
   - *Skip entirely* (don't add).
   Optionally signal **like / really like / not for me** per book (cheap taste data).

### 3.2 "We know your taste"
Immediate, celebratory taste summary (genres, authors, languages, eras, themes) and a shareable **taste card**. This is the first "wow" moment and replaces an empty home screen.

### 3.3 Recommendations (immediately)
Carousels / bands rather than a single list:
- Because you love *X*
- More like this
- Your friends read this / liked by people you follow
- (Later) People with your taste love this · *91% match*

Every recommendation carries a one-line **"Why this?"** (model-generated, grounded in the user's actual shelf and signals).

### 3.4 People
Invite friends, follow by library, view friends' shelves (what they've chosen to share). Match percentages and "people like you" discovery are **Phase 2** (they need critical mass to be honest).

### 3.5 Discover → Wishlist → Find it
Add to wishlist from anywhere. **Find it** shows legal options only: borrow (Libby/OverDrive deep link), buy elsewhere (affiliate-capable links), and free public-domain editions where they exist. No hosted downloads.

### 3.6 Home screen order
1. Digital library snippet (with "see all")
2. Recommendations & taste insights
3. Community around me (friends' activity)

Physical shelf view is an optional lens, never the default.

---

## 4. Library model: collections, visibility, taste, sharing

This replaces a simple "remove from library" with a richer, still-simple model.

### 4.1 Collections (tag / move to a named section)
- Every book lives in **My Library** and can belong to **zero or more named collections** ("Dana's books", "Work", "Kids", "To lend", "Unread", user-defined).
- Collections have: name, optional emoji/color, **visibility**, and a **"counts toward my taste"** toggle.
- Quick-create during triage: "Move these to a new collection called…".
- Default smart collections (auto, editable): by genre, language, author, and "Wishlist".

### 4.2 Two independent controls (important)
| Control | Question it answers | Levels |
|---|---|---|
| **Visibility** | Who can see this? | Private · Specific people · Followers · Public |
| **Taste inclusion** | Does this shape *my* recommendations/profile? | Counts · Doesn't count |

Set at **book** level, with **collection** level as the default for its members. Example: "Dana's books" → *Specific people: Dana* + *Doesn't count toward my taste*. Her professional books stay in the shelf but never pollute recommendations or what followers see.

Rule of thumb: sharing-level defaults to **private** for new collections; the app never publishes a whole library implicitly.

### 4.3 Sharing with a specific person (e.g. a spouse)
- **MVP:** share a **collection** or the **entire library** with specific people as **view access**. Works for people not yet on Booked (invite link → they see the shared view after joining).
- Each person keeps their **own taste profile and signals**. Sharing a shelf does *not* merge taste.
- **Phase 2 — Household shelf:** a jointly-owned library where both can add/edit books; each member's relationship to a book (read / like / not mine) is individual. Scan flow gets a "scanning for: me / us / someone else" selector.

### 4.4 Signals
- **Private like** (for you / your recommendations): *like · really like · not for me*.
- **Public rating** (for the community / wisdom of the crowd) — optional, separate from the private like.

---

## 5. Catalog & data

### 5.1 Sources (open)
Open Library, Wikidata, Google Books API, national library catalogs; ISBN/barcode lookup. Public-domain texts and free editions: Project Gutenberg, Standard Ebooks, Internet Archive. (Audio is Phase 3.)

### 5.2 Data model essentials
- **Work** vs **Edition**: one logical book across translations/editions (the Hebrew and English editions of the same novel are one Work). Recommendations operate on Works.
- **Author** entities with name variants and transliterations (Hebrew ↔ Latin).
- Per-user **LibraryEntry**: user, work (or unresolved book), edition (optional), collections[], visibility, taste-inclusion, signal (like level), private rating, public rating, timestamps.
- **Collection**, **ShareGrant** (resource, grantee user-or-invite, access level), **Follow**.
- **UnresolvedBook**: user-supplied title/author/language/optional cover photo; see §5.3.
- Language is a first-class field everywhere; RTL-safe UI and text handling.

### 5.3 Manual add & async resolution (no dead ends)
- User adds a book not found in the catalog (title, author, language, optional cover photo). It exists **immediately** in their private library and contributes to their taste at **reduced weight**.
- A background job re-matches unresolved books against the catalog as coverage improves; on a probable match the app asks the user to **confirm**.
- Persistently unresolved books enter a **resolution queue** (team now, community later), which also improves the shared catalog.
- No files are uploaded or hosted → no copyright exposure.

---

## 6. Scanning pipeline

1. **Capture:** guided camera (hold steady, good lighting, multiple passes per shelf). On-device spine detection via Vision/VisionKit to segment spines.
2. **Read:** per-spine text via on-device OCR, with a vision-language model fallback for hard cases (rotated/vertical text, stylized fonts, Hebrew, mixed scripts).
3. **Match:** fuzzy-match (title/author, multilingual normalization, transliteration) against the catalog → resolve to **Work**. Return top candidates with confidence.
4. **Confirm:** auto-accept high confidence; quick-confirm medium; send low to "fix or add manually".
5. **Fallbacks:** barcode scan, search, one-at-a-time cover scan, manual add.
- Track scan accuracy per language as a first-class metric.

---

## 7. Taste & recommendation engine (staged)

| Stage | Approach | When |
|---|---|---|
| 1 | **Content-based:** book embeddings from metadata, descriptions, subjects, author; user profile = weighted aggregate of library + signals (respecting taste-inclusion). | MVP — works with zero friends |
| 2 | **Social signals:** friends/followed readers' libraries and signals boost ranking. | MVP (basic) |
| 3 | **Collaborative filtering** + similar-reader matching; match percentages; "people with your taste love this". | Phase 2, once library volume allows |

**"Why this?"** is generated by an LLM from structured evidence (shared authors/themes, friends who read it) — grounded, never invented.
**Taste evolution:** track profile changes over time (e.g. "you're reading more fantasy", "you've started reading Murakami") — feeds celebrations and recaps.

---

## 8. Habit loops (Hook model)

Trigger → Action → Variable reward → Investment.
- **Triggers:** weekly "new for you" drop, friend activity, taste-change nudges.
- **Action:** like/dislike a book (swipe-style, low effort), add to wishlist, scan another shelf.
- **Variable reward:** surprising high-match recs, "your taste is evolving" moments, friends who loved the same book.
- **Investment:** every like/rating/shelf improves recommendations and the social graph.
- Celebrate **taste discovery and taste change**. Recaps are periodic, not just annual ("Wrapped"-style, e.g. "Your first 100 books were mostly…").
- MVP ships the first celebration (taste card) and the weekly drop; deeper loops are Phase 3, but hypotheses and instrumentation start now.

---

## 9. Scope

### MVP
1. Scan + add by search / barcode / manual add (with async resolution)
2. Shelf triage with **collections**, visibility, and taste-inclusion
3. Share a collection or full library with specific people (view access)
4. Taste summary + shareable taste card
5. Recommendations in carousels with "Why this?"
6. Wishlist + "Find it" (borrow / buy / free) links
7. Invite & follow friends; see friends' shared shelves; "friends read this" on recs

### Phase 2
Match percentages and people-discovery · household (co-owned) shelf · groups · AI librarian (talk about taste, correct the app, build reading lists) · collaborative filtering.

### Phase 3
Richer multilingual coverage · audio (public-domain first) · wrapped-style recaps & deeper habit loops · contributed uploads (only if a legally safe model exists) · Android.

### Deferred / ignored for now
Premium/monetization (keep affiliate links as the lightweight option), anything legally risky.

---

## 10. Success metrics

- **Scan:** % users completing a scan; avg books added; match accuracy by language; time to first recommendations.
- **Aha:** % who view taste summary and act on a recommendation (wishlist/like) in session one.
- **Social:** invites sent per user; % follow ≥1 person within 7 days.
- **Retention:** week-1/week-4 return; weekly-drop open rate.
- **Quality:** like-rate on recommendations; "not for me" rate.
- **Privacy health:** % libraries with non-private content; share-setting changes (signals confusion).

---

## 11. Risks

1. Scan accuracy on non-English / Hebrew spines and cluttered shelves.
2. Cold network — mitigated by strong content-based recs from day one.
3. Privacy comfort — mitigated by collections + per-item visibility.
4. Catalog coverage gaps for Hebrew/long-tail — mitigated by manual add + async resolution.
5. Scope creep back toward tracking / shelf management / loaning.
6. Naming/trademark — "Booked" not yet checked (domain, App Store, trademark).

---

## 12. Open questions

- Confirm "Latin languages" = Latin-script languages.
- Backend stack and hosting choice (not yet decided).
- Embedding / LLM provider choices and cost envelope per scan.
- Auth approach for non-user share invites.
- Relationship with Velato (collaboration vs. independent) — revisit later.
- Name check for "Booked".

---

## 13. Build prompt (for an engineering/design agent)

> Build **Booked**, an iOS-first (SwiftUI) app: *"Your world of books. Scan your shelf. See what your friends are reading. Discover what to read next."* The product exists to solve "what should I read next"; the library is the cold-start mechanism, not the goal. Implement the MVP in §9 following the flows in §3, the library model in §4 (collections, visibility vs. taste inclusion, sharing with specific people), the data model in §5, the scan pipeline in §6, and Stage 1–2 recommendations in §7. Support English, Hebrew (RTL) and Latin-script languages from day one; never create dead ends (manual add + async resolution). Do not build: groups, AI librarian, audio, uploads, premium, physical shelf-location management, loaning. Start with a thin vertical slice: scan → triage → taste summary → recommendations → follow a friend; instrument every step per §10.
