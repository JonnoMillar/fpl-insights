# HANDOFF — FPL Insights

Last updated: 29 October 2026 (logo/icon handoff; dashboard draft still awaiting review). Older checkpoint detail lives in git history (`git log -p docs/HANDOFF.md`).

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

## Logo and icon handoff for Claude (29 October 2026)

CURRENT — 1 November: `brand-handoff/transparent-suite/` supplies 40 generated icons as 3 transparent PNG atlases plus 40 CSS alpha-mask views, source rectangles, local preview and white/aubergine/green browser captures. Actual generated pixels retained; no code-drawn shapes. Alpha verified; preview checked at 1200/390px with no overflow. Saves B selected by Codex as working choice, not user approval. Clean `fpl-insights-generated-icons-2026-11-01.zip` excludes rejected vector redraws. Full visual approval and final logo exports remain open. Application unchanged.

LATEST — 30 October: Jonno rejected the code-drawn vector suite as visually poor, especially Saves. Its technical rendering checks are not design approval. `vector-suite/` and the old `-vectors.zip` must not be implemented. Resume built-in image generation using the approved Goals/Assist image reference. Three new Saves alternatives are in `brand-handoff/concept-suite/saves-image-options.png`, unreviewed. Do not substitute freehand SVG geometry. Application unchanged.

30 October vector checkpoint: `brand-handoff/vector-suite/` supplies 40 SVG masters + 40 compact exports, shared construction source, catalogue, light/dark/mobile previews and Claude usage notes. 80 XML parses; 160 rendered samples loaded; no painted border/empty exports; 1280/390px overflow checks passed. Goals/Assist compositions retained; shared ball/goal/arrow geometry, injury knockout, normal Deadline clock and single filled red card supplied. Complex football scenes remain dense at 16px: prefer 20–24px plus labels. Whole-suite vector geometry awaits Jonno review; final logo geometry/exports remain open. Application unchanged; no publication.

30 October: Jonno requested the whole suite after iterative Goals/Assist and set-piece studies. `brand-handoff/concept-suite/` holds 40 generated labelled proposals across three sheets, original approved Goals/Assist composition reference, latest set-piece study, preview and Claude notes. The new suite supersedes older bulk dashboard-icons drafts. Goals/Assist concepts approved; full suite unreviewed. Production SVG normalization and 16/20/24px recognition remain outstanding. Red-card stacking is semantically ambiguous; Deadline stopwatch should become a normal clock. No application changes or publishing.

- Delivery entry point: [`brand-handoff/README.md`](brand-handoff/README.md); ready-to-use brief: [`brand-handoff/CLAUDE_BRIEF.md`](brand-handoff/CLAUDE_BRIEF.md).
- Approved **logo direction**: open-bottom football goal frame with three ascending data bars. Exact geometry remains a draft; no production master or final exports have been approved.
- Navigation starting point: bold outline shirt (internal sleeve seam lines removed), route, trophy and magnifier. Jonno considers the icons potentially suitable; this is not blanket approval of the sidebar treatment.
- Claude should design the sidebar shape/layout and more distinctive selected states as part of the full dashboard redesign. Earlier sample rail dimensions, white selection tiles and green logo containers are not locked requirements.
- The delivery folder includes only the goal/chart direction, four navigation SVGs, their MIT licence and Jonno's supplied new-dashboard screenshot. All eye concepts and generated whole-page logo mockups are excluded.
- Package verification: 12 files, five parsed SVGs, desktop/390px preview without horizontal overflow; archive integrity and per-file SHA-256 hashes verified. No application regression suite run because application code is unchanged.
- Subsequent checkpoint: the handoff is explicitly **partial**, not finished. `brand-handoff/drafts/` now holds 30 additional dashboard icon proposals: 24 Phosphor bold assets and six custom football symbols. Two sheets show 36px artwork plus 18px samples; parsed SVGs and desktop/390px rendering verified. Jonno has not reviewed these new icons yet. The earlier 12-file ZIP remains an older partial snapshot.
- Latest feedback supersedes the batch approach: Jonno found the additional set insufficiently distinctive and rejected the assists/penalties/free-kick semantics. These are historical drafts, not implementation choices. Research is recorded in `brand-handoff/drafts/ICON_RESEARCH.md`; proceed with one carefully developed custom image-generated football icon at a time, starting with assists. The new custom assists studies are not yet user-reviewed or verified at small size.
- No application code or production assets were changed by this design exercise. Final logo geometry and integrated sidebar previews need Jonno's review before production exports or implementation. No publishing approval.

## Now: brand refresh (final dashboard draft awaiting Jonno's review)

Canvas: [FPL Insights brand directions](https://claude.ai/artifact/9paQtGhWZJ4K6NS4gmYzAn), version 17. Rows top to bottom: first four directions, C round 2 (y 8500), Round 3 (y 11800), **Final draft (y 14900)**.

Round 3 verdict (28 Oct comments): C best overall (layout, colour balance, click-to-reveal instead of scrolling). Keep from C: transfer card with the old player greyed out, the night-coloured fourth band. Keep from A: big glass crest tiles for fixture runs. Keep from B: the swipe deck for transfer options. B faults: floor rings drawn across the players' legs ("awful"), and Hall's ring should sit behind him.

Final draft, one option:
- **F-Kit** (1280×3700): colour roles and target balance, Archivo at four settings, rules and never-list, components (week tile states, chip coins, transfer card, captain card with ring behind, glass crest tile, swipe deck), player-image do/don't, motion and shape specs.
- **F-Desktop** (1280×1794) and **F-Phone** (390×3005), both interactive: C's rail and week stage; captain card with the green ring behind Hall; green panel holding B's deck rebuilt on C's transfer card (purple foil cards, glass opponent plate, ranked list on desktop, face dots on phone); night band with A's glass crest tiles plus worst runs (Hull crest uploaded) and a white last-week card.
- Verified locally in headless Chromium: deck at positions 1, 3 and 4, weeks GW9/GW12/GW13/GW14; no overflow, clipped text or broken images. Live canvas runtime and real dragging not tested.
- Generator for F-Desktop/F-Phone was `scratchpad/final/gen.py` (lost on `/clear`); edit the published `.dc.html` files directly after re-reading them.

**Next:** Jonno reviews the final draft. Then write `docs/design.md` from F-Kit and restyle Planning > Your moves against `.cache/ui/moves-before-{1440,375}.png`.

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

1. Review the final brand draft (above).
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
Read AGENTS.md and docs/HANDOFF.md. Work on main in C:/Users/jonno/code/fpl-insights. Brand refresh: the final draft (brand kit plus desktop and phone samples) is on the canvas https://claude.ai/artifact/9paQtGhWZJ4K6NS4gmYzAn awaiting Jonno's review; read new comments first. Once approved: write docs/design.md from the F-Kit board following "Jonno's design rules", then restyle Planning > Your moves and compare with .cache/ui/moves-before-*.png. Commit by explicit path only (Codex has files staged; never git add -A, stash, reset or checkout). Do not push or publish until Jonno says so.
```
