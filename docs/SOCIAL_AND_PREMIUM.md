# Booked — Premium, Feed, Bravo and Scan Guidance

Companion to `docs/SPEC.md` and `docs/DESIGN.md`. Screens: https://claude.ai/artifact/SWpb3fcJKAqLq9ez2yfBhp (private).

## 1. Premium: where to put walls

### Principles
1. **No wall inside the core loop** — scan → Reader Identity overview and cards → recommendations → follow → feed → wishlist stay free. Habit loops are never taken away.
2. **Charge for depth, control and convenience at scale**, not for access to the basics.
3. **Show value before asking.** A free preview of the premium thing (blurred depth behind the first insight), never a trial that later removes something the user got used to.
4. **Don't paywall trust.** Basic privacy and data portability stay free.
5. **Be honest about cost.** Scanning costs cents per shelf (see `SPEC.md` §13), so MVP scanning should not be capped except for abuse. The costs that grow with engagement are LLM-written analysis, an AI librarian and heavy recommendation features — those are the natural premium surface.

### Free vs Premium

| Area | Free | Premium |
|---|---|---|
| Scanning | Unlimited onboarding scans; generous fair use after | Higher fair-use ceilings for bulk work |
| Reader Identity | Overview + 6 cards (gist) | **Your full identity**: books behind each insight, themes, authors, taste evolution, monthly refresh |
| Recommendations | Home carousels, Discover, "why this" | Filters (language mix, length, mood), "how far to branch out", AI librarian (Phase 2) |
| Library | Unlimited books, wishlist, collections | Household shelf (family plan) |
| Social | Follow, feed, Bravo, comments, posting | Granular sharing rules (see §3) |
| Recaps | Yearly recap (shareable, drives growth) | Monthly recaps, deeper yearly breakdown |
| Data | Import and export | — (never paywall a user's own data) |

### Avoid
Caps on number of books, collections, wishlist, follows or likes; locking the Reader Identity overview; paywalls before the first Reader Identity; locking export; time-limited trials that remove features.

### Conversion moments
After the Reader Identity overview (curiosity gap), when taste evolution has something to show, before the yearly recap, when using advanced filters, when inviting a household member.

### Guardrails and metrics
No paywall before day 7 in the core loop; A/B any wall against free retention; track conversion by trigger, refund/cancel rate, and share of paying users who also post/follow. Prices are placeholders until a willingness-to-pay test.

## 2. Community feed

**Structure:** two feeds — *Following* (people you follow) and *Community* (public posts only, opt-in). Entry points: auto-activity, manual posts, and "Share → Booked feed" from the Reader Identity share sheet.

**Auto-shared activity (user's choice at onboarding and in Settings):** finished books, books you really liked, milestones; optionally wishlist adds and new shelves. Presets: *Everything*, *Highlights* (recommended), *Only what I post*. Collections set aside (e.g. "Dana's books", "Work") are never auto-shared.

**Privacy and premium (position):** I recommend **not** making "keep things private from the feed" premium-only. Free: the three presets, a master "only what I post" mode, and removing any post later. Premium: granular rules (by collection, genre, audience such as close friends, delay). Reason: paywalling basic privacy hurts trust and invites backlash; the fine-grained control is the real power-user value.

**Ideas borrowed from Strava:**
- Reactions on every activity (Bravo), plus comments.
- Group activity merging ("Dana and Yuval both finished …").
- Milestones/trophies (100th book, first book in a new language).
- Challenges and goals (monthly: "3 translated books"); gentle streaks, no guilt mechanics.
- Clubs → reading groups (Phase 2).
- Flyby-style discovery: "Readers who also read this".
- Privacy zones → privacy rules (premium granular).
- Shareable cards (Reader Identity, yearly recap) as the social growth loop.
- Follow requests and private profiles, mute/block/report from day one.
- Photos: post a shelf photo (opt-in, never automatic).

**Risks:** feed feels empty with few friends (use "Community" and the Reader Identity/recap posts to seed it); moderation and harassment (report/block, comment controls); auto-posts feeling surveillance-y (explicit first-run choice, visible "shared" state, easy delete).

## 3. Bravo (kudos)

- **Name:** "Bravo" (clear, celebratory, translatable). Alternatives: "Dog-ear" (bookish but ambiguous), "Cheers" (Vivino's; wine-flavoured).
- **Can be given on:** finishing a book, a "really like", a milestone, a new Reader Identity, a shelf post, a manual post.
- **Differentiator:** a feed item about a book also offers **+ Wishlist**, so a reaction can turn into an action.
- **Notifications:** batched ("Dana and 2 others gave you Bravo"), never one per reaction.

## 4. Scanning a wall

A wall can be scanned in principle; accuracy depends on spine resolution, not on intent. A phone photo of a wide wall often leaves spines too small to read, so the guidance is **scan a wall in a few passes, or one shelf at a time**, with live hints ("Spines small? Move closer") and a multi-shelf session. The prototype (`PROTOTYPE_PLAN.md`) should measure the minimum legible spine height in pixels so the app can warn automatically; a pan/video mode that stitches rows is a candidate improvement.

## 5. Colour decision

Orange is the **action** colour (CTAs, scan button, active states); teal stays the **insight** colour (Reader Identity, "why this"). White text on bright orange fails contrast (≈2.6:1), so orange fills use ink text (≈6.9:1) and orange text on white uses a darker burnt orange (≈5.4:1). The orange is amber-leaning, not Strava's red-orange, to avoid looking like a copy.
