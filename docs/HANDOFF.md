# HANDOFF — FPL Insights

Last updated: 1 November 2026 (full redesign built on main, all four tabs; not pushed). Older checkpoint detail lives in git history (`git log -p docs/HANDOFF.md`).

## State

- Live: [fpl-insights-jm.vercel.app](https://fpl-insights-jm.vercel.app/), built by GitHub Actions from origin/main. It does not yet have the redesign or the transfer planner.
- Local main is 33 commits ahead of origin/main and 35 behind (scheduled bot commits). Not pushed. Before publishing: fetch, integrate the bot commits, run a fresh full build plus tests and browser checks, then push. Don't publish until Jonno says so.
- Main holds the transfer planner and the full redesign (commits `0925aa2`..HEAD). Last verified 1 Nov: 112 tests, `node --check` on all `.js`, fresh `cli.py dashboard --out .cache/ui/final.html` with every source OK, headless Chromium at 1440/1024/375/320 with no page overflow or console errors, and scripted checks of the brief-to-plan jump, week tiles and arrow keys, deck buttons (real mouse clicks)/drag/list, fixture-run switch, player dialog and transfer preview.
- Owners: Claude owns frontend and planner. Codex owns the data-research audit under `research/` (entry point `research/log.md`; production code untouched by it).

## Separate track: managed account experiment

29 October 2026: entry **11195024** has a researched GW9 squad entered and saved,
verified after reload. All strategy, rules, frozen decisions, live state and
operating details are isolated in [`account-management/HANDOFF.md`](../account-management/HANDOFF.md).
An active local review heartbeat is configured; its first unattended execution
is not yet verified. Dashboard entry/configuration, product code, alert project
and publication are unchanged. Existing staged research remains separate.

## Now: redesign built, awaiting Jonno's review (1 November 2026)

Spec: [`docs/design.md`](design.md) (F-Kit with Noto Sans; "Where it is implemented" maps each part to code). Boards in `docs/design-reference/`. Built in one session on main, all four tabs, commits `0925aa2`..HEAD:

- Shell: purple side rail with the goal-chart mark and icon tabs (selected = white tile, heavier label, green notch), night glass tab bar on phones, sticky chapter rail, paper ground. Icons: generated set packed by `scripts/pack_icons.py` into `assets/icons.png` (90 KB, embedded). Portraits now alpha WebP.
- Squad: night score card, season and league tiles, green up-next panel, next move as transfer cards with cut-outs and opponent crests, captain card with ring behind, purple pitch, iconed findings without coloured edges.
- Planning: eight week tiles over one stage (moves, roll coin, chip bench; squad pitch per week in a disclosure), purple plan summary, swipe deck of other options on the green panel (replaced the old single/pair card lists, now deleted), chip coins, Buy/Sell/Keep/Avoid on four fills, odds tiles by fill, knee-jerk with cut-out, night band of glass crest tiles for fixture runs.
- League: place card plus gaps to leader and next place, grey rivals and named line ends on the position chart, purple "you" row, league-owns gaps beside the template, your starters tagged "You".
- Scout: inherits tokens, ramps and type; fixture card retitled.
- Ramps redrawn night-grey-paper-green-deep green (greyscale test passes); every hue-only signal found was given a shape, line style, word or fill change.

Next: Jonno reviews the local build (`python cli.py dashboard --open`, or the README screenshots, regenerated). Known gaps worth his eye:
- Logo is still the draft geometry, used in the rail and favicon; 16/24/32px review not done.
- Icons are as delivered (thin lines on a few; yellow card's bar). Jonno: "sort icons after".
- Captaincy radar and the Scout heatmap were restyled through tokens only, not rebuilt.
- F-Desktop's "Rising soon" aside and white last-week card were not carried over (squad tab already shows last week).

Decisions needed from Jonno (recommendation first):
- Faint icons: thicken corners, saves, free kicks and injured at pack time (dilation keeps the generated drawing) vs regenerate them.
- Yellow card: drop the inner bar so it reads as a card, not a phone.

Canvas mechanics:
- Artboard files live in the session scratchpad and are lost on `/clear`. Re-read with `Artifact read` (url, then `path` of each `project/*.dc.html`). Read the latest version before publishing or it is refused.
- Player and badge `/_blob/` ids are in the artboard files. Portraits: PL CDN `110x140` path (returns 220×280 cut-outs). Crests: `badges/100/t{code}@x2.png` (200 px).
- Comment threads can't be replied to or resolved by Claude unless Jonno sends them to Claude.

## Jonno's design rules (from all feedback to 28 Oct)

- Red-green colourblind: no meaning by hue alone (lightness, shape, text; blue/orange if two hues). No pill tags. Sofascore's red-orange-green rating scale is out.
- Type: Noto Sans only, chosen 1 Nov 2026 (plain letters and numbers, plain zero, real weights; tabular figures page-wide). Never a face with a slashed or dotted zero (IBM Plex Mono), nor thin figures (Schibsted at 500), nor Archivo.
- Tacky, never again: cards with one edge in a different colour; purple chapter bands with a green edge; lilac, and lilac inside lilac; small grey help or info lines; ticket-stub shapes; large decorative gradient washes.
- Cut-outs never end in a hard edge inside a card (sit on the edge or fade). Breakouts only on large hero cards.
- Show the opponent's badge, not the player's own club. Use badges, faces and icons generously.
- Plan shows transfers and chips, not weekly team xP. Don't cram data into small areas (sparklines).
- Laptop view needs colour variation between sections.
- Rings, glows and floor marks always sit behind a cut-out, never across the body.
- Liked: glassmorphism, C's image spill and colour balance, a swipe deck for suggested transfers (not for the hero or captain card), click-to-reveal over scrolling. Fine as is: green rank bars, money tags.
- References: Instagram stat graphics of @sofascore_football (first) and @gradient_sports, a bit of FotMob. Notes: `docs/audits/2026-10-27-instagram-reference.md`.
- Copy: low-key, no boasting. Keep the published-squad, no-double-gameweek and data-unavailable caveats visible once each.

## Awaiting Jonno

1. Review the built redesign; two icon decisions (see "Now").
2. Push/publish (see State).
3. Build the Wildcard + Bench Boost comparison? (analysis below)
4. Sanity check on Cherki, sold in GW9 for Palmer.

## Seen, not fixed

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

- Fast design loop: build once with `dashboard.build(...)` at `ttl=10**9` and `PRICE_HISTORY_PATH` pointed at a scratch copy, pickle the result, then re-run `dashboard.render(d)` after CSS/JS/render edits (card markup changes need the build again, about 50 s cached).
- Long `python - <<'EOF'` heredocs in Git Bash break on f-strings here; write the script to a file.

- Bot commits can land mid-work; fetch and integrate before pushing, never force-push. Generated-file conflicts resolve with verified regenerated output.
- FFS team-news: parse only `<li class="team-news-item">` blocks; sidebar widgets once parsed as a club. A player read as "unknown" falls back to a 75% start, hiding benched players.
- Some PL portraits return 403; existing fallbacks handle it, don't retry. Provider photos can lag transfers (Isak still shows a Newcastle shirt).
- Probing the planner on real data: wrap `planner.build` during a cached build (`--ttl 99999999`, price history redirected to scratch) and pickle its arguments.
- Vercel CLI isn't logged in; publishing works through the Git integration, so it isn't needed.
- GitHub auth errors inside a sandbox can be sandbox network limits, not a bad token; check with approved host access before asking Jonno to re-auth.

## Resume prompt

```text
Read AGENTS.md, docs/HANDOFF.md and docs/design.md. Work on main in C:/Users/jonno/code/fpl-insights. The full redesign is built and committed locally; ask Jonno for his review of it before changing direction, then act on his notes. Dev loop: a cached build plus pickled data lets CSS/JS changes re-render in seconds (see Gotchas). Commit by explicit path only (Codex has files staged; never git add -A, stash, reset or checkout). Do not push or publish until Jonno says so; before pushing, fetch and integrate the bot commits.
```
