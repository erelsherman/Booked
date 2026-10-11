# Booked: seven additions to the friends circle

Why and how each addition works. Flows are on the design canvas (https://claude.ai/artifact/SWpb3fcJKAqLq9ez2yfBhp, boards 24 to 29b).

**Home answers "what should I do now?" and the Feed answers "what did everyone do?"** (`SPEC.md` §3.6).

| Addition | Lives in |
|---|---|
| Now reading (2), moments from friends, caught up | Home |
| Status and rating (1), friends who read this (3) | Book page |
| Tips that landed (5) | Activity |
| Blend (6) | Friend profile |
| Ask your circle (4), weekly digest and yearly recap (7) | Push and share |

Order: 1, then 2 and 3, then 4 and 5, then 6 and 7.

## 1. Reading status and rating (first)

**What.** Every book can be Want to read, Reading or Finished, with 1 to 5 stars, a quick tag and an optional line for friends.

**Why.** It is the data the social layer runs on. Today only scanning and posting create events, so “Johan just finished this”, “3 friends loved it” and tips that land cannot exist. It also gives recommendations an honest signal. Letterboxd and StoryGraph are built on this.

**Flow.** Book detail (24) → Mark as finished → Rate it (24b) → What next (24c)

**We will measure.** Share of library books with a status; ratings per reader per week.

**Free or Premium.** Free. It is core.

**Needs.** Nothing. Everything else depends on it.

## 2. A “Now reading” row on Home (first)

**What.** The top of Home shows what you are reading, with progress, a one-tap Update and I finished it.

**Why.** Home answers “what should I do now?”, and for a reading app the first answer is the book in your hands. It is the daily habit, and each Finished creates the moment friends see.

**Flow.** Home (25) → Update (25c) → Where are you? → Save, or I finished it → Rate (24b)

**We will measure.** Weekly return to Home; progress updates per reader.

**Free or Premium.** Free.

**Needs.** 1.

## 3. Friends on the book page (first)

**What.** Every book page shows “Friends who read this”: stars, a line, and who has it on their wishlist.

**Why.** A friend’s opinion matters most at the moment of choosing a book, and this adds nothing to Home. It is the strongest social proof for Add to wishlist.

**Flow.** Book detail (24) → See all → Friends who read this (24d)

**We will measure.** Wishlist adds from pages that show friends.

**Free or Premium.** Free. Only what friends chose to share appears.

**Needs.** 1.

## 4. Ask your circle (next)

**What.** After a book, ask friends “what should I read next?”, with a mood. Friends answer with a book from their shelf, and you choose.

**Why.** It is the brief itself: recommendations as if you had asked a friend when you met. It gives friends a reason to open the app (someone asked me), and answers are better than any algorithm.

**Flow.** Finished (24c) → Ask your circle (26) → Friend’s phone (26b) → Answers (26c) → Add to wishlist or start reading

**We will measure.** Answer rate; wishlist adds and starts from answers.

**Free or Premium.** Free. One open question at a time, at most two a week, and friends may skip silently. Offered once the circle has two friends.

**Needs.** 1 and 3.

## 5. Close the loop for the person who recommends (next)

**What.** Tell the person whose tip landed: added to a wishlist, started, finished, with the rating. A Tips tab in Activity and a line in the weekly digest.

**Why.** Giving tips has to feel rewarded, or people stop. It is Strava’s kudos idea applied to recommending. Names from inside your circle are free; names beyond it follow the Premium rule.

**Flow.** Activity › Tips (27) → Say thanks or Bravo back

**We will measure.** Tips given per reader per month.

**Free or Premium.** Free inside your circle.

**Needs.** 1 and 4.

## 6. Reading Blend with a friend (later)

**What.** A shared list of books you would both likely enjoy, from two shelves, with why. Shareable.

**Why.** A concrete reason to invite one specific person. Spotify’s Blend shows the pattern. It is lighter and warmer than a side-by-side comparison, which stays Premium.

**Flow.** Friend profile (28) → Blend with Dana → Reading Blend (28b) → Add all, or share

**We will measure.** Blends created per connection; invites after a shared Blend.

**Free or Premium.** Free. Compare Reader Identities stays Premium.

**Needs.** 1; a friend who shares a shelf.

## 7. Weekly digest and yearly recap (later)

**What.** A gentle weekly note: books your circle finished, the most loved, your week, a pick for Sunday. A shareable yearly recap card.

**Why.** A weekly rhythm without streak pressure (streaks can feel punishing for reading), and a recap people want to share, which brings in new readers.

**Flow.** Notification → Weekly digest (29) → Open Home → Yearly recap (29b) → Share

**We will measure.** Digest opens; recap shares and the installs they bring.

**Free or Premium.** Free. Monthly recaps stay Premium.

**Needs.** 1; circle activity.
