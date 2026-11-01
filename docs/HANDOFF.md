# HANDOFF — FPL Insights

Last updated: 1 November 2026 (redesign direction agreed; design.md written; icon set assessed). Older checkpoint detail lives in git history (`git log -p docs/HANDOFF.md`).

## State

- Live: [fpl-insights-jm.vercel.app](https://fpl-insights-jm.vercel.app/), built by GitHub Actions from origin/main. It does not yet have the redesigned UI or the transfer planner.
- Local main is 33 commits ahead of origin/main and 35 behind (scheduled bot commits). Not pushed. Before publishing: fetch, integrate the bot commits, run a fresh full build plus tests and browser checks, then push. Don't publish until Jonno says so.
- Main holds: Codex's compact UI, Claude's transfer planner, plan moves as transfer cards (`b16cce6`), copy cuts (`d5c10b3`). Last verified: 112 tests, `node --check` on all `.js`, full build with 10 sources OK, headless Chromium at 1440/375/320.
- Owners: Claude owns frontend and planner. Codex owns the data-research audit under `research/` (entry point `research/log.md`; production code untouched by it).

## Separate track: managed account experiment

29 October 2026: entry **11195024** has a researched GW9 squad entered and saved,
verified after reload. All strategy, rules, frozen decisions, live state and
operating details are isolated in [`account-management/HANDOFF.md`](../account-management/HANDOFF.md).
An active local review heartbeat is configured; its first unattended execution
is not yet verified. Dashboard entry/configuration, product code, alert project
and publication are unchanged. Existing staged research remains separate.

## Now: full redesign (direction agreed 1 November 2026)

Spec: [`docs/design.md`](design.md), written from the F-Kit board with Noto Sans in place of Archivo, plus the icon-set assessment. Boards copied to `docs/design-reference/` (F-Kit, F-Desktop, F-Phone; images are canvas blob ids and don't render locally). Canvas comments are all from 27-28 Oct and already folded into the rules below; none on the final draft.

Icon set (`brand-handoff/transparent-suite/`, 40 generated icons, Codex delivery of 1 Nov): good fit, adopt it, with four pack-time fixes listed in design.md (Planning crop, faint strokes on corners/saves/free kicks/injured, yellow card's phone-like bar, 3.19MB of atlases packed to one 56KB sprite). Rejected `vector-suite/` and old `drafts/` stay unused. Logo geometry still a draft.

Build order (one phase per session, commit at each gate, nothing pushed until Jonno says):

0. Integrate origin first: local main was 33 ahead / 35 behind (bot commits). Fetch, merge, regenerate generated files, run tests. Then the icon packer: `assets/icons.png` + names, embedded by `dashboard.py` as a data URI; `.ico` classes. Unit test that every name resolves to a non-empty cell.
1. Foundation: replace the CSS tokens with design.md's (drop lilac scale and every hue-coded state token), Noto 400-900, shape/shadow/motion variables; rail with logo and icon tabs plus distinct selected state; phone bottom tab bar. Check logo at 16/24/32px.
2. Planning tab to F-Desktop/F-Phone: week stage, hero transfer card, captain card, green panel with swipe deck, night band with crest tiles, last-week card. Compare with `.cache/ui/moves-before-{1440,375}.png`. **Show Jonno the live build here before rolling out.**
3. Squad tab, 4. Mini-league, 5. Scout: no boards exist; build from the kit components, absorb the "Seen, not fixed" layout items, show Jonno each.
6. Clean-up: delete dead CSS (dashboard.css is 2,758 lines), regenerate `docs/og.png`, update README, full build, tests, browser checks at 1440/375/320.

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

1. Two icon decisions (see "Now: full redesign").
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
Read AGENTS.md, docs/HANDOFF.md and docs/design.md. Work on main in C:/Users/jonno/code/fpl-insights. Redesign direction is agreed; start the next phase in "Now: full redesign" (phase 0 first: integrate origin, then the icon packer). Commit by explicit path only (Codex has files staged; never git add -A, stash, reset or checkout). Do not push or publish until Jonno says so.
```
