# Booked — Habit Loops

Companion to `docs/SPEC.md` §8. Visuals: the "Habit loops" section of the design canvas (https://claude.ai/artifact/SWpb3fcJKAqLq9ez2yfBhp, private).

Each loop uses the Hook model: **Trigger → Action → Variable reward → Investment**. Reward types: *hunt* (finding the right book), *tribe* (social recognition), *self* (learning something true about yourself).

## Three core loops (diagrammed)

**A · Scan to insight** — the core loop.
Trigger: first run, then "Scan more to sharpen your Reader ID". Action: scan a shelf. Reward: Reader ID gets sharper (new cards, higher confidence). Investment: library grows, taste data improves.

**B · Insight to friends**
Trigger: Reader ID ready; "Readers like you" suggestions. Action: follow friends and readers like you. Reward: their stories and posts, Bravo on yours. Investment: your follows, posts and shared shelves.

**C · Insight to action**
Trigger: "Next for you" with a one-line reason. Action: add to wishlist, then borrow or buy. Reward: finish it, like it, get better picks. Investment: likes, ratings and wishlist teach the engine.

## Four more loops (table)

| Loop | Frequency | Trigger | Action | Reward | Investment | Metric |
|---|---|---|---|---|---|---|
| 4 · Weekly return | Weekly | Weekly new picks; friends' stories; batched notification | Open, browse stories and picks, react | New picks and stories, never the same twice (hunt, tribe) | Reactions, wishlist, follows | Week-1 and week-4 retention |
| 5 · Social reciprocity | Several times a week | Bravo or comment received (batched) | React back, post, add to story | Recognition from people who read like you (tribe) | Audience, posts, followers | Posts per user; Bravo given to received |
| 6 · Evolution and recaps | Monthly, yearly | Monthly taste update; yearly recap | View identity, share card | Learning something true about yourself (self) | History (the longer you stay, the richer) | Recap shares; Premium conversion |
| 7 · Share to new readers | Continuous | Reader ID or recap ready to share | Share card, story or invite | Friends respond and join (tribe) | A bigger network | Invite acceptance; new users per sharer |

Loops 1–3 are rows 1–3 of the canvas table ("All seven habit loops"); loops 4–7 above complete the set.

## How the loops connect

A feeds B and C (more books means better people and picks). C feeds A (a finished book often prompts a new scan or a like). B feeds 5 and 7 (friends create reciprocity and growth). 6 closes the long loop (history makes the identity richer, which Premium sells). Premium never sits inside A, B or C.

## Stories and the community widgets

Stories are 24-hour, manual posts (now reading, finished, a quote, a shelf photo, Reader ID, a recommendation to a friend), with a nudge when a book is finished. They sit on top of the Community and Following feeds and as a row on Home. Home also carries a feed snippet, a monthly challenge, "Your community reads" and "Readers like you", so the social loops (B, 4, 5) are reachable from the first screen.

## Guardrails
- No streak-guilt, no countdown pressure; challenges are optional and monthly.
- Notifications are batched and respect quiet hours; one per loop per day at most.
- Every trigger has an off switch; every post can be removed.
- Measure retention and satisfaction, not just time in app.
