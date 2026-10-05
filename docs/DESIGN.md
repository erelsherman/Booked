# Booked — Design Direction, Flow v2 and Review

Companion to `docs/SPEC.md`. Visual designs live on the design canvas (13 iPhone screens): https://claude.ai/artifact/SWpb3fcJKAqLq9ez2yfBhp (private; share from the page's Share menu).

## 1. Design review of v1 and v2-draft

What was wrong, in order of importance:

1. **Tone.** Saturated multi-color blocks, thick outlines and hard shadows read as playful/childish, not authoritative. The product's job is trusted taste, so the look must feel calm and editorial.
2. **The Reader Identity looked like a physical object and a promotion.** Tilted card, seal stamp, barcode strip and a lime button read as marketing. A taste profile should feel like *information about you*, not a collectible.
3. **Too many competing colors.** Five accents fought each other and the book covers (which are the only color a book app should have).
4. **Archetype nicknames ("Quiet Wanderer") were gimmicky.** A data-grounded statement ("Literary and reflective, not fast-paced") is more credible and is the pattern that worked for Vivino's Reader Identity.
5. **Social was decorative.** A bubbly "People" page with archetype tags. Strava's model — a real activity feed with stats and reactions — makes social the daily habit.

## 2. Direction

**References:** Vivino (white canvas, soft rounded cards, one brand color, floating pill nav with a separate scan button, a "Reader Identity" card with a statement headline and line illustrations, a "Shape your taste" like/dislike stack, collections as cover mosaics) and Strava (activity feed with compact stats and reactions, calm typography, restraint).

**System (v2):**
- White/off-white canvas; soft gray (#F3F3EF) surfaces; hairline borders; soft shadows only on floating elements.
- **One accent:** deep teal (#0F5F58) with a pale tint (#E4F0EE), used for state, links, the scan button and the Reader Identity rule line. Primary buttons are near-black pills. The only other color is the book covers.
- Type: Figtree for UI, Newsreader (with Frank Ruhl Libre as the Hebrew serif) for statements and titles, so the Hebrew experience is first-class and consistent.
- Cards: radius 20–24, no outlines heavier than 1px, no tilt, no stamps, no badges that look like promos.
- Real-feeling book covers (color + title typography) instead of flat colored boxes.
- Icons: thin-stroke line icons; no emoji.

**Reader Identity (the hero element):** a flat card, not an object. Statement headline in serif, short teal rule, three informational rows (*For the bookseller*, *Likes the feel of*, *Authors to try*), line illustrations of book spines at the edges, a one-line provenance ("Based on 12 books · 2 set aside") and one action. It is never styled as an ad. Archetype names are dropped; the headline is generated from signals ("X, not Y" built from likes and not-for-me).

## 3. Flow v2 (and why it changed)

| # | Screen | Purpose |
|---|---|---|
| 1 | Welcome | One value statement, three one-line promises, Sign in with Apple. No friction before value. |
| 2 | Scan | One shelf row at a time; modes: Shelf / Barcode / Search / By hand. |
| 3 | Check your shelf | Only exceptions need attention (matched collapse to a quiet ✓). "Select" lets users set aside books that aren't theirs. |
| 3b | Set books aside (sheet) | Move to a new/existing collection; *Count toward my taste* switch; visibility. Optional, in context, not a separate step. |
| 4 | Reader Identity | Immediate reward right after confirm. |
| 5 | Shape your taste | Vivino-style like / didn't like / haven't read stack over books they just scanned; each answer sharpens recommendations. Skippable. |
| 6 | Share Reader Identity | Shares the statement only; library stays private (explicit copy). |
| 7 | Home | Friends row (new activity rings), Next for you carousel with "why", compact Reader Identity. |
| 8 | My library | Collections as cover mosaics, with state pills (From scans · Shared, not in taste · Only me). |
| 9 | Collection settings | Visibility (segmented), shared-with people, collection taste switch, per-book overrides. |
| 10 | Book detail (+ Hebrew RTL) | "Why this?", wishlist / not for me, private like (Not for me / Like / Really like), borrow / buy. |
| 11 | Friends | Strava-style activity feed: stats strip, reactions, quoted notes. Quiet "Invite a friend" row, not a banner. |

**Changes vs previous flow:**
- Sorting is no longer a separate full step between scan and reward; it lives inside "Check your shelf" as Select → Set aside, so the Reader Identity appears one step sooner.
- "Shape your taste" added as the bridge from taste to recommendations; it also collects the like signals the engine needs.
- Welcome/sign-in added (a first-run gap).
- Friends is now a real feed; match percentages remain out of the MVP.

## 4. Honest review of the new design and flow

**Works well**
- Tone is calmer and more credible; covers carry the color.
- The Reader Identity is information-first and shareable without exposing the library.
- The reward comes within three screens of the scan.
- The collection model (visibility vs. taste inclusion, per-book override) is visible in the UI and not hidden in settings.
- Hebrew/RTL is considered from the start (serif, mirrored layout, neutral phrasing).

**Open risks / things I'd test**
1. **Statement quality.** "Literary and reflective, not fast-paced" must come from real signals; with <15 books it will be generic or wrong. Needs a minimum-data state ("Add 5 more books to sharpen your Reader Identity") and a confidence indicator.
2. **Shape your taste before recommendations** adds a step. If the scan already yields likes (e.g. from past reads), skip it. Test drop-off here.
3. **"Select → Set aside" discoverability.** It's a text link; many users may never find it. Consider an inline hint on first scan when a mix of genres is detected ("Some of these look different — set them aside?").
4. **Home is dense.** Friends row + carousel + Taste card is a lot above the fold when the user has no friends yet. Needs an empty state: replace the friends row with "Invite a friend" and show a library snippet instead.
5. **No empty/error states yet:** unreadable scan, low confidence, no camera permission, offline, zero friends, zero wishlist.
6. **Privacy clarity.** Visibility is shown as pills and a switch; usability test whether people understand "shared, not in taste".
7. **Accessibility not yet verified.** Contrast was chosen for ≥4.5:1 but not measured; covers contain decorative small text; Dynamic Type and VoiceOver not designed.
8. **Placeholder content.** All names, counts and book matches are illustrative.

## 5. Next steps
- Empty/error/low-data states, wishlist, settings, one-at-a-time and manual-add flows.
- Real-copy and archetype/statement generation rules (what signals produce which headline).
- Clickable prototype of the first-run path and a 5-person hallway test.

## 6. Update: Reader Identity, scanning, sign-in and Home (round 3)

- **Name:** "Reader Identity" (not "Taste ID"). "ID" can read as an ID number or login identity, so the screen carries the subtitle "Your reading identity" and the term is tested in user research. Fallback names: "Reader profile", "Your reading identity".
- **Reader Identity is a story of cards, not a Vivino copy.** A stack of 6 swipeable cards: (1) at a glance, (2) what you read, (3) languages and places, (4) how you like a story told, (5) authors and themes, (6) how your taste is changing. Each card has a one-line gist, and "Read the full analysis" opens a detailed page with evidence (the books behind each claim), a confidence indicator and what is set aside. No "for the bookseller" row, no sub-category tabs, no recommendations inside the Reader Identity.
- **Recommendations live in Home and Discover**, not inside the Reader Identity. The Reader Identity only links out ("Explore").
- **Scan:** warmer message ("Let's scan your library"), a multi-shelf session (scanned shelves tray, "Next shelf", "Done · 31 books") and the option to come back later.
- **Sign-in:** Apple, Google, phone number, and email as a quiet fallback.
- **Home:** library widget (102 books · 12 on wishlist), Reader Identity widget, Recommended for you, Because you love…, Your friends like, Your community reads. **Discover:** For you / Friends / Community / Explore, with "Branch out" collections.

## 7. Naming update

"Reader ID" is now **Reader Identity** ("Your Reader Identity" as the screen title), because "ID" could read as an ID number or login. The subtitle is "Who you are as a reader". The premium deep view stays "Your full identity". Keep testing the name with a few readers; fallback: "Reading identity".
