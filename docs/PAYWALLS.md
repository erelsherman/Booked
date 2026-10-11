# Booked — Paywall Map

Companion to `docs/SOCIAL_AND_PREMIUM.md`. Visual version: the "Paywall map" board and the Premium section of the design canvas (https://claude.ai/artifact/SWpb3fcJKAqLq9ez2yfBhp, private). Prices are not set.

## Rules
- At most one wall per session; never inside core loops A, B, C in the first seven days.
- Preview before asking; always say what stays free; no countdown timers or fake scarcity.
- Never remove something a user already had; cancel in two taps.
- Scanning and building your circle (invites, contacts, follows, circle size, friends' picks and activity on Home) are the core offering: never capped, metered or paywalled.
- Never paywall Undo, removing a post, account deletion, import/export, basic privacy presets, or notification settings.

## Two decisions from review

**Inside your circle is free; curiosity about people outside it, or deeper analysis, is Premium.** "Who gave you Bravo" from friends in your circle is the reward in the social loop (loop 5): hiding those names would break reciprocity and feel manipulative, and in a small circle there is little to unlock. The LinkedIn-style wall goes on passive curiosity: names of people beyond your circle who gave you Bravo, who viewed your Reader Identity or profile, and deeper insights. Bravo counts stay free for everyone.

**Customize on auto-share is a Premium wall, with a free exit.** After an auto-share, a sheet says "Shared with your followers" with **Undo** (free) and **Customize** (Premium): choose audience, edit what is shown, post later, never share by collection or genre. Free users keep the three presets and can remove any post.

## Map

| Feature | Free | Premium | Wall | Trigger | Trust risk | When |
|---|---|---|---|---|---|---|
| Your full identity | Reader Identity overview + 6 cards | Books behind each insight, themes, authors, evolution, monthly refresh | Preview | Tap "View your full identity" | Low | MVP |
| Customized sharing | 3 presets, Undo, remove | Audience, edit, post later, never-share rules | Soft lock | After an auto-share | Medium | MVP |
| Post and story insights | Bravo and comments, with names from inside your circle | Names beyond your circle, reach, viewers, wishlist adds, best time | Soft lock | "Your week" on Activity | Low | MVP |
| Advanced discovery | Home, Discover, why this | Filters, branch-out dial, saved searches, hide read | Soft lock | Filter icon | Low | MVP |
| Who viewed you | Weekly counts | Names (opt-in viewers), trend | Preview | "See who viewed you" | Medium | Next |
| Compare Reader Identities | A friend's gist | Side by side, what you share, where you differ | Soft lock | "Compare" on a profile | Low | Next |
| Availability alerts | Manual Find it | Alert when free at your library, new from followed author | Soft lock | Bell on wishlist | Low | Next |
| Monthly recaps | Yearly card | Monthly, deeper yearly, time-lapse | Preview | Month end | Low | Next |
| Household shelf | Share a collection (view) | Shared library, up to 5, own taste each | Plan | Invite a partner | Low | Next |
| AI librarian | A few questions a month | Unlimited, remembers taste, builds lists | Meter | Allowance runs out | Low | Later |
| Reading groups | Join | Create and run private groups | Soft lock | "Start a group" | Low | Later |
| Reading stats | Counts | Pace, pages, goals, history | Soft lock | "See all stats" | Low | Later |
| Card and profile style | Standard | Themes, custom link, badges | Soft lock | Share sheet | Low | Later |
| Bravo from beyond your circle | Bravo and names of friends in your circle; counts from everyone | Names of people outside your circle who gave Bravo | Preview | Tap "+2 from beyond your circle" | Low | Next |

## Sequencing
- **MVP walls:** full identity, customized sharing, insights, advanced discovery.
- **Next:** viewers, compare, availability alerts, monthly recaps, household.
- **Later:** AI librarian, groups, stats, cosmetics.

## Privacy note on "who viewed you"
Showing viewers' names is a privacy feature as much as a revenue feature. Only people who allow it appear (default decided with legal review), the toggle is free, and the first-run copy explains it. Not legal advice; check local rules (including GDPR and Israeli privacy law) before shipping.
