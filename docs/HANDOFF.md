# HANDOFF — FPL Insights

Last updated: 4 November 2026 (player profile published to origin/main and live). Older checkpoint detail lives in git history (`git log -p docs/HANDOFF.md`).

## Hover hint on player pictures, published 5 November 2026

One CSS block at the end of `dashboard.css` ("Click for the profile"), on top of the `data-player` hooks and `profile.js`: pointer devices only; the person lifts from their feet, the disc or chevrons behind swell, the name underlines (picture and name linked with `:has`), pitch cards lift and the kit scales. Checked at 1440 and 375 px: hover, click-through to the profile, no clipping. Local `main` in the working checkout is a stale parallel line (its own click-through payload work is superseded by `profile.js`); reconcile it to `origin/main` rather than merging it.

## Fixes on `claude/plan-deck-fixes`, 4 November 2026 (not pushed)

- Planner rolled GW10–17 on the live 4 Nov data while the deck listed free moves worth +20 to +51. Cause: `Planner._select` ranked states waiting on a Bench Boost ("pending") with the rest; they filled the beam, and the "keep one non-pending" guard was met by the do-nothing state, so every finished plan with moves was dropped. Pending states now get their own `PENDING_KEEP` = 10 slots beside 30 finished ones. Same data: +61.4 xP over rolling (551.1 v 489.7), moves in GW10–12 and GW15 (Bench Boost). Regression test in `tests/test_planner.py`.
- Deck arrows opened a player profile from the second click at desktop width: the flung card sits over the buttons, and `.cut[data-player]{pointer-events:auto}` beat the card's inline `none`. Off-top cards are now `inert`.
- Scout DEF scatter: x = xGC per 90 (reversed, lower to the right, axis from the pool's lowest value), bubble = DefCon per 90. The DefCon hit-rate gate (`hero_x_key`) still drives the leaders board.
- Verified on fresh 4 Nov data: 141 tests, `node --check`, `git diff --check`, Python Playwright at 1440 and 375 (arrows step 1→2→3→4 and back, no profile opens; DEF scatter reversed, sizes follow DefCon/90; no console errors or page overflow).

## Then: one player profile, published 4 November 2026 (`1a87345`, CI rebuild `6e8d17b`, live)

Every face opens one view: `profile.js` + `playerprofile.py` (data) + `.pf-*` CSS. It replaced the Squad dialog (`playerview.js`, `cards_squad.player_payload/player_dialog`) and the Scout card (`scout.js` renderCard, `scout.PositionConfig` card_tiles/sparks/strip_marks/cs_outline); all deleted with their CSS.

- Hook: `cards_common.hook(pid, name)` puts `data-player` + `role="button"` + `tabindex` on the face itself (layouts unchanged; hooked `.cut` gets `pointer-events:auto`). Names use `<button data-player>`. One delegated listener: click, Enter/Space on non-buttons, Esc closes (native), focus returns to the face. Phone: bottom sheet under 700px.
- Hooked: Squad move cards (both), captain, pitch, Your 15, team news; Planning plan moves, chip bench, cheap slots, plan pitch shirts, deck (in, out, pair faces), chip planner shirts; League template, your differentials, watchlist, scoring against you, season best/worst and table; Scout leaders, explorer table and scatter, shortlist bars and fixtures. Not hooked on purpose: faces inside a week tile (`button.wk`) and the deck index (`button.deck-idx`), which are navigation buttons. Captain-options radar names are not hooked (no faces).
- Data: `playerprofile.build` makes a compact record for all players (1.1 s); `playerprofile.island(body, ...)` in `render()` keeps only ids hooked on the page plus the Scout pools (435 on 3 Nov data) and raises if a portrait image has no hook or a hook has no record, so a broken page never publishes. Scout pool rows no longer carry match history; the profile ships it once as short arrays. `script_json` now writes compact JSON. Profile crests are 64 px, once each.
- Page: 4,746,818 → 3,793,742 bytes (−953 KB). Scout islands 1,434 KB → 252 KB, old player-data 257 KB gone, profile-data 478 KB.
- xP: owned squad and previewed signings use the match-history scorer (same as the pitch); everyone else `transfers.candidate_score` (same as the Scout xP column, which now also returns team_xg). The "i" in Extended stats says which.
- Photo: the face already on the page; otherwise the PL CDN URL at view time (crest stays if it fails).
- Verified 4 Nov on cached data: 140 tests, `node --check` every `.js`, `git diff --check`, build `.cache/ui/profile.html`, Python Playwright at 1440 and 375: 122 checks pass (each listed face opens the right player, both expanders fill, Esc returns focus, keyboard Enter on a scatter point, deck drag still swipes without opening, no page or profile overflow, no console errors). Screenshots `.cache/ui/profile-*.png`.
- Publish 4 Nov: fresh build all sources ok, 140 tests, Playwright on it passed except move cards (plan rolls 3 FTs, so none exist); CI push run passed; live page opens the profile from the captain card at 1440 and 375, focus returns, no console errors.
- Seen, not fixed (pre-existing, also in the 3 Nov build): at 375 px the deck cards sit above the bottom tab bar mid-scroll and swallow taps on it.

## Then: dedupe pass, published 3 November 2026

Published as `6367a48` (merge of the four feature branches, the dedupe from [`docs/audits/2026-11-02-data-placement.md`](audits/2026-11-02-data-placement.md), and origin's bot/licence commits), followed by CI's rebuild `4497ea6`. Next: the unified player profile (one view for every player face).

Rule now: one home per stat. Squad = this week, Planning = the next weeks, League = rivals, Scout = finding players, the player profile = per-player detail. Figures, not sentences.

- Squad: score card, Season tile, Up next; the next move (one +xP for the whole move, figures per player, no per-leg gain); captain card; pitch opens on Next gameweek; collapsed "Captain options" radar; team news (Predicted line-ups only); collapsed "Your 15" table (no Next 3 column).
- Planning: plan (consecutive rolls share one tile, "BB prep" figure on moves made for the held Bench Boost, no weekly squad xP, plan rules in the "i"), deck (alternatives only; the plan's moves removed; knee-jerk pick tagged; gains to the plan's end week), chips (figures; Wildcard priced against the plan on the plan's scorer), fixture runs (tabs: model, clean sheets, goals, DefCon, FPL difficulty; 20-club grid collapsed under it), price watch.
- League: place card (no own total), standings, position chart, season review, template + your differentials, scoring against you, watchlist, chips used.
- Scout: position switch, leaders (3-start floor), explorer, shortlist; proven-managers card here, hidden until it has data.
- Cut: Squad league tile, Attacking returns, Big chances created, Fixture swings, Goals v xG, Defensive contribution, Set pieces, Price movement, Availability, Rotation risk, Big chances missed, Last season; Planning odds, Highest XI, Buy/Sell/Keep/Avoid, knee-jerk card, Season leaders, Value scatter, method card, all chapter bars; League lede, Who owns whom, "league has these"; Scout fixture card and chapters.
- One fixture scale (0–10, higher is better) everywhere except the band's FPL tab. `transfers.TRANSFER_HORIZON_WEEKS` = `planner.HORIZON` = 8 (test holds them equal).
- Season 600 v 598 (2 Nov): picks and standings endpoints cached at different times during a live round; the own total now shows only on Squad.
- Wildcard (3 Nov data): the rebuild is +22 over standing still on the plan's scorer, the plan +61, so the card reads "−35.5 xP v the plan" (it read "+70.1, Strong" against standing still on the chip model).
- "BB prep" tag: logic in `planner.describe` (`week["chip_prep"]`); no move in the 3 Nov plan qualifies, so it has not yet shown on real data.
- Verified 3 Nov on cached data: 130 tests, `node --check` on every `.js`, `git diff --check`, build `.cache/ui/build5.html` (every source OK), headless Chromium at 1440/1024/375/320: no page overflow, no console errors, player dialog opens, radar draws when expanded, fixture-band tabs and 20-club grid work, Scout shortlist strip renders. Screenshots in `.cache/ui/shots-dedupe/`.
- `_update_price_history` still writes `price_history.json` every build, but no card reads it since Price movement was cut. Keep (CI commits it) or remove: Jonno's call.

## State

- Live: [fpl-insights-jm.vercel.app](https://fpl-insights-jm.vercel.app/), built by GitHub Actions from origin/main; has the redesign, planner and dedupe since 3 Nov (CI push build passed).
- Local main checkout (`C:/Users/jonno/code/fpl-insights`) is still at `222e37a`: Codex's staged `research/**` index and the build-rewritten `price_history.json` block a fast-forward there. Work from `claude/dedupe-integration` or a fresh worktree off origin/main. Before every push: fetch, integrate bot commits, fresh full build, tests, browser check.
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

- Two scorers: Squad pitch uses match-history xP, the plan uses the season-based transfer scorer (66.1 vs 70.0 for the same XI on 21 Oct). The Starting XI "i" says so. Consolidation not started. The Wildcard card no longer mixes them (fixed 3 Nov: `planner.build(compare=...)` scores the rebuild on the plan's scorer); the chip model still picks the rebuild squad and its week.
- Remaining copy issues: `docs/audits/2026-10-21-repetitive-copy.md` (the clear cuts are done in `d5c10b3`).

## Transfer planner (current rules)

- `planner.py`: beam search over 8 GWs, moves allowed in any of them. Per week roll or make 1–2 moves. Objective: best XI, captain doubled, weighted bench (0.21/0.06/0.02, reserve GK 0.03; whole bench on Bench Boost), 4 per hit, 3-point margin per move, 1.5 per banked FT at the end, 0.9 weekly discount. Hits and margins are discounted with their week (the bar that week's own build will apply). The end squad is credited for the weeks after the plan that have projections (to 12 GWs out); without that the plan's back half rolled by construction (fixed 2026-11-02).
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
