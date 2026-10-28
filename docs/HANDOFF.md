# HANDOFF — FPL Insights

Last updated: 28 October 2026. Older checkpoint detail lives in git history (`git log -p docs/HANDOFF.md`).

## State

- Live: [fpl-insights-jm.vercel.app](https://fpl-insights-jm.vercel.app/), built by GitHub Actions from origin/main. It does not yet have the redesigned UI or the transfer planner.
- Local main is 33 commits ahead of origin/main and 35 behind (scheduled bot commits). Not pushed. Before publishing: fetch, integrate the bot commits, run a fresh full build plus tests and browser checks, then push. Don't publish until Jonno says so.
- Main holds: Codex's compact UI, Claude's transfer planner, plan moves as transfer cards (`b16cce6`), copy cuts (`d5c10b3`). Last verified: 112 tests, `node --check` on all `.js`, full build with 10 sources OK, headless Chromium at 1440/375/320.
- Owners: Claude owns frontend and planner. Codex owns the data-research audit under `research/` (entry point `research/log.md`; production code untouched by it).

## Now: brand refresh (awaiting Jonno's pick)

Canvas: [FPL Insights brand directions](https://claude.ai/artifact/9paQtGhWZJ4K6NS4gmYzAn). Rows top to bottom: four first directions (Jonno picked C, "FPL flat"), C round 2 (y 8500), Round 3 (y 11800).

Round 3, each variant at desktop 1280 and phone 390, real GW9 data:
- **A Floodlit glass bento:** dark purple, floodlight glows, frosted tiles of mixed spans, timeline of faces and chip coins to GW16.
- **B Matchday bands:** full-width purple/green/white/black bands, broadcast-style stage with pitch lines and floor rings, working swipe deck of seven suggested moves, chips as casino-chip tokens, full league table.
- **C App shell:** side rail plus clickable GW9–GW16 week rail; the stage swaps per week (transfer, Bench Boost bench, roll, Free Hit note). Phone has a floating tab bar.
- B and C are interactive (Play on the canvas). Verified locally in headless Chromium across deck positions and weeks; live canvas runtime and real dragging not tested (Claude's browser isn't signed in to claude.ai).

**Next:** Jonno picks or mixes a layout, style and interaction. Then write the brand kit and `docs/design.md`, then restyle Planning > Your moves against `.cache/ui/moves-before-{1440,375}.png`.

Canvas mechanics:
- Artboard files live in the session scratchpad and are lost on `/clear`. Re-read with `Artifact read` (url, then `path` of each `project/*.dc.html`). Read the latest version before publishing or it is refused.
- Player and badge `/_blob/` ids are in the artboard files. Portraits: PL CDN `110x140` path (returns 220×280 cut-outs). Crests: `badges/100/t{code}@x2.png` (200 px).
- Comment threads can't be replied to or resolved by Claude unless Jonno sends them to Claude.

## Jonno's design rules (from all feedback to 28 Oct)

- Red-green colourblind: no meaning by hue alone (lightness, shape, text; blue/orange if two hues). No pill tags. Sofascore's red-orange-green rating scale is out.
- Type: Archivo only. Never IBM Plex Mono (dotted zero).
- Tacky, never again: cards with one edge in a different colour; purple chapter bands with a green edge; lilac, and lilac inside lilac; small grey help or info lines; ticket-stub shapes; large decorative gradient washes.
- Cut-outs never end in a hard edge inside a card (sit on the edge or fade). Breakouts only on large hero cards.
- Show the opponent's badge, not the player's own club. Use badges, faces and icons generously.
- Plan shows transfers and chips, not weekly team xP. Don't cram data into small areas (sparklines).
- Laptop view needs colour variation between sections.
- Liked: glassmorphism, C's image spill and colour balance, a swipe deck for suggested transfers (not for the hero or captain card). Fine as is: green rank bars, money tags.
- References: Instagram stat graphics of @sofascore_football (first) and @gradient_sports, a bit of FotMob. Notes: `docs/audits/2026-10-27-instagram-reference.md`.
- Copy: low-key, no boasting. Keep the published-squad, no-double-gameweek and data-unavailable caveats visible once each.

## Awaiting Jonno

1. Round 3 pick (above).
2. Push/publish (see State).
3. Build the Wildcard + Bench Boost comparison? (analysis below)
4. Sanity check on Cherki, sold in GW9 for Palmer.

## Seen, not fixed

- Scout: "Fixture runs" chapter band sits directly over a card of the same name.
- Mini-league: "The league has these, you do not" sits alone in a row.
- Goals-against-expected legend separates "owed goals" from "running hot" by green vs amber hue alone.
- Three grids still use a bare 300px minimum (price watch `.pw-cols`, `.fxruns`, an `auto-fill` grid in `dashboard.css`); unchecked at 320px. The fix used on `.tflist` is `minmax(min(100%,300px),1fr)`.
- Chip planner's Wildcard total (470.0 → 509.4 over GW9–16) disagrees with the transfer plan's 549 for the same window; likely a different scorer or no captain/bench. Check before showing both together.
- Two scorers: Squad pitch uses match-history xP, the plan uses the season-based transfer scorer (66.1 vs 70.0 for the same XI on 21 Oct). The Starting XI disclosure says so. Consolidation not started.
- Remaining copy issues: `docs/audits/2026-10-21-repetitive-copy.md` (the clear cuts are done in `d5c10b3`).

## Transfer planner (current rules)

- `planner.py`: beam search over 8 GWs, moves in the first 6. Per week roll or make 1–2 moves. Objective: best XI, captain doubled, weighted bench (0.21/0.06/0.02, reserve GK 0.03; whole bench on Bench Boost), 4 per hit, 3-point margin per move, 1.5 per banked FT at the end, 0.9 weekly discount.
- Hits: only in the coming week and only when urgent (starter-priced player ruled out or ≤25% chance, or a must-have signing: top-five xGI/90 at his position, 450+ minutes, MID/FWD, next fixture difficulty ≤3).
- Enablers: cheap = position's cheapest starting price + 0.5. Never upgrade an enabler who stays on the bench, unless a Bench Boost follows in the plan. Enabler to a cheap starter is allowed.
- Chips: judged undiscounted against their best later week; played only if 2 points better. Bench Boost and Triple Captain planned; Free Hit and Wildcard not.
- Start chance: last 3 matches plus next week's predicted line-up, drifting 25% back to the season rate each week (`planner.start_chances`).
- Never sells a player it signed or buys back one it sold. Hero action comes from `next_action.choose(plan, ...)`; the next-week preview uses the plan's XI, bench and armbands via `next_squad.from_plan`.

### Wildcard + Bench Boost (analysis only, not built)

Two orders: (A) Wildcard week N to fifteen starters, Bench Boost N+1, then unwind; (B) build the bench with transfers, Bench Boost, then Wildcard back to the template (11 strong starters, one decent bench player, 3 enablers). Free transfers survive a Wildcard (cap 5); first-half chips expire after GW19.

Default view: B usually wins, because the Wildcard leaves the template squad. A wins when the Bench Boost week needs wholesale change (a double gameweek) and 4–5 free transfers are banked to unwind it. Build: a horizon-weighted best fifteen for the Wildcard week (check `squadbuilder` fits), then score A, B and "Bench Boost with ordinary transfers, Wildcard saved" over one window with the planner's week scorer; show winner and margin. Advice stays withheld while doubles are unmodelled.

## Hazards

- **Shared git index:** Codex has ~92 files staged (`research/**`). Commit by explicit path only. Never `git add -A`, stash, reset or checkout. Leave `price_history.json` (rewritten by every build), `.agents/` and `.playwright-mcp/` unstaged.
- Builds for checks go to `.cache/ui/` (gitignored): `python cli.py dashboard --out .cache/ui/after.html`.
- Browser checks: Playwright MCP has been unreliable; use the Python Playwright script (`from playwright.sync_api import sync_playwright`) against `python -m http.server`. Preview "dashboard" (`.claude/launch.json`) serves the main checkout root on 8795.

## Decisions that still hold

- Serve a full HTML document, never a fragment (phones scaled the 980px layout down).
- Recover real selling prices before affordability advice; withhold advice if recovery fails.
- Evaluate paired transfers together on the resulting squad; no per-leg standalone gains.
- No double-gameweek model: withhold planning advice when the window has doubles or mismatched fixtures.
- Snapshot age shown; overdue warning after six hours. Scheduling is best-effort.
- Keep `projections.json`'s public interface stable for the phone-alert project.
- Home/away is already priced into fixtures (FFS per-fixture xG, clean-sheet odds); a separate venue factor would double-count.

## Gotchas

- Bot commits can land mid-work; fetch and integrate before pushing, never force-push. Generated-file conflicts resolve with verified regenerated output.
- FFS team-news: parse only `<li class="team-news-item">` blocks; sidebar widgets once parsed as a club. A player read as "unknown" falls back to a 75% start, hiding benched players.
- Some PL portraits return 403; existing fallbacks handle it, don't retry. Provider photos can lag transfers (Isak still shows a Newcastle shirt).
- Probing the planner on real data: wrap `planner.build` during a cached build (`--ttl 99999999`, price history redirected to scratch) and pickle its arguments.
- Vercel CLI isn't logged in; publishing works through the Git integration, so it isn't needed.
- GitHub auth errors inside a sandbox can be sandbox network limits, not a bad token; check with approved host access before asking Jonno to re-auth.

## Resume prompt

```text
Read AGENTS.md and docs/HANDOFF.md. Work on main in C:/Users/jonno/code/fpl-insights. Brand refresh is waiting on Jonno's round 3 pick from the canvas https://claude.ai/artifact/9paQtGhWZJ4K6NS4gmYzAn. Once he picks: write the brand kit and docs/design.md following "Jonno's design rules", then restyle Planning > Your moves and compare with .cache/ui/moves-before-*.png. Commit by explicit path only (Codex has files staged; never git add -A, stash, reset or checkout). Do not push or publish until Jonno says so.
```
