# HANDOFF — FPL Insights

Last updated: 20 October 2026, apple-design CV showcase assessment complete. No application edits or publication in this review; the latest UI source still differs from the live artifact.

## Status

Jonno intends to link the live dashboard on his CV. The first phase was a deep audit of glaring functional, correctness and reliability risks, followed by fixes. That phase is complete and live at [FPL Insights](https://fpl-insights-jm.vercel.app/).

The brand/UI/visitor review is documented in the [design brief and prioritised plan](audits/2026-10-14-design-brief.md). Jonno reviewed the comparison and explicitly requested the implementation below. His feedback supersedes the proposed removal of the review hero: keep it on both desktop and mobile, add linked next actions, stabilise the pitch and improve narrow layouts. The purple/green/warm-paper identity, existing forecast calculations, correctness guards and dependency-free architecture remain. Read the [audit and resolution notes](audits/2026-10-13-cv-readiness.md) for correctness evidence; avoid repeating the completed audit without new evidence.

## CV showcase review checkpoint — 20 October 2026

- Jonno requested an apple-design assessment for a recruiter/engineering hiring manager: five presentation improvements and a concrete direction before editing. Read [the assessment](audits/2026-10-20-apple-design-showcase.md) for measured evidence, source locations, guideline references, a token/type proposal and desktop/mobile structure. This is a proposal, not an approved implementation.
- Inspected live arrival (20 October, 08:12 UTC snapshot) and the historical local `revised.html` build. Live still has older pitch controls and no linked hero actions; local CSS and embedded dashboard.js/scout.js/playerview.js/ticker.js match current source exactly. The local 14 October snapshot displays an expected overdue warning; do not describe it as a live-feed outage or current transfer advice.
- Five priorities: explain purpose/author/source on arrival; compose the retained weekly review beside the pitch and compact it on mobile; surface Planning decisions and Scout comparison; tighten typography/card hierarchy; finish navigation, control targets and feedback. Preserve the purple/green/paper identity, both type families, hero on both sizes, stable pitch and all existing functionality.
- Browser evidence: local hero 718px high at 390px, tabs at y≈906px, pitch at y≈1,208px; at 320px these are 871px / 1,059px / 1,380px. With the unfiltered defender pool at 390px, comparison starts roughly 3,362px below the first selection. Information-button hit boxes are 16×16px. The report distinguishes design comfort targets from web accessibility requirements.
- Sampled all four tabs at 1440/390/320, Scout's three positions, team filter/two-player compare, pitch periods/metric visibility, hero captain destination/focus, keyboard tabs, player dialog/Escape/focus restoration, Total sorting and reduced-motion styles. No sampled document overflow or recorded console errors. No fresh build, regression run, physical-device, cross-browser, enlarged-text or performance claim. Application and generated files unchanged.
- Local evidence remains in untracked `.playwright-mcp/`. The temporary review server for this audit on port 8767 is stopped after use; the older comparison server recorded below was not changed. Documentation-only `git diff --check` is the checkpoint verification. Commit only this assessment and HANDOFF; preserve pre-existing `.agents/` and `.playwright-mcp/`.

Next gate: Jonno's response to the proposed direction. The highest-impact implementation is compact purpose/navigation plus a desktop review/pitch composition, keeping the requested hero and all six summary facts. If implementation is requested, verify a current-data source build before publication; do not simply publish the historical review HTML.

## Current implementation checkpoint — 14 October 2026

- Main review hero remains on every screen, with two-column mobile summary tiles and linked captain/action summaries. The actual saved squad suggests Hall → Schuster plus Hughes → Cherki (+23.0 five-GW XI gain after the four-point hit) and Haaland (7.7 expected points). These are snapshot results, not promises of current advice.
- `next_action.py` selects from existing legal, affordable recommendation outputs. Single moves must clear two net points; pairs must clear two and beat the best single by another two. Otherwise roll the available free transfers; the five-transfer cap is explained. This is a visible conservative heuristic, not a calibrated model of transfer value. Tagged kneejerk pairs use another horizon and are excluded. Missing projections, selling prices or free-transfer count withhold the action.
- A known-unused chip is promoted only when exactly one existing planner has a strong recommendation for the next gameweek. Chip scores are not ranked against unlike transfer horizons. Wildcard remains a separate longer-window case in the chip planner; it is not automatically promoted by this selector. Unknown chip history never triggers a hero chip recommendation. Model limits and publication caveats remain visible.
- Hero links switch to Planning, scroll below the sticky header and move keyboard focus to the exact transfer/pair, captaincy matrix or chip card. Method links open their disclosure; unavailable chip advice has a real explanatory destination.
- Pitch periods read Season / Next gameweek / Last gameweek. The review line stays fixed. Shared grid geometry preserves card position/height; controls occupy their own stable row. Only the chosen points/per-game/xGI number is displayed on each season pitch card. Season-based metrics stay explicitly labelled even in the last-gameweek view. Small pitches retain their formation instead of wrapping a four-player row into two rows.
- Fixed the responsive cascade where later desktop grids overrode mobile leaders/pairings. Leaders use three desktop/two tablet/one phone columns; pairings stack below 900px, with wrapping names and totals. Pair gains now use dark green for contrast. Standings show Rank / Team (+manager) / Total / GW first; sorting uses the rendered columns.
- Removed the duplicate Busiest fixture odds card. Existing bookmaker data is team-level: it cannot support a genuine individual goalscorer odds claim.
- Verified FPL's own current ElementPhoto implementation in its official client. Portraits now use `premierleague25/photos/players/110x140/{element.code}.png`, weekly refreshes and club-specific cache keys. No legacy old-club photo fallback. Temporary/missing portraits use the official neutral placeholder; 403/404 responses are not retried and get a one-day cooldown. An authoritative missing response retires any expired cached image. One requested portrait (code 199798) was unavailable during the first build; the official placeholder loaded. Provider portraits can still lag a transfer; do not claim every picture is current.
- Verification: `python -m unittest discover -s tests -t .` **72 passed** (64 existing plus 8 focused action/image cases); `node --check dashboard.js` and `git diff --check` passed. Complete cached-data builds succeeded with all nine source-health entries OK, at ~2,982 KB. Existing generated files and projections.json were not replaced or published.
- Browser proof: 1280px desktop, 390px and 320px phone widths. Pitch top and height identical across the three periods at each width. Verified one selected metric, action/captain/method/chip destinations, expanded predicted-points view, all four tabs at 320px, single-column leaders/pairings with no sampled card/document overflow, standings Total sorting and empty error logs in the checked flows. No physical-phone, Safari/Firefox, screen-reader, fresh-network full rebuild or prediction-backtesting claim.
- Review files: [before/after comparison](http://127.0.0.1:8766/comparison.html) and [full working dashboard](http://127.0.0.1:8766/revised.html?review=final). Files live in `C:/Users/jonno/.codex/visualizations/2026/10/14/01a137d8-6cda-70e2-b6ad-0c76be0c871f/`; ignored `.cache/update_review.py` assembles the comparison from the committed before artifact and verified revised source build. This comparison supersedes the first hero-removal mockup.

Next gate: Jonno reviews this working comparison. If publishing is requested, fetch/integrate any scheduled bot commits, run a fresh complete artifact build and regressions, check source health and projections compatibility, then publish through the existing Git integration. Continue remaining recruiter orientation/Scout discovery polish only from his review; do not reinstate the rejected hero removal.

The fixes are in commit f3578be, followed by the successful automated refresh 3306697. The checkout was fast-forwarded to that refresh. Existing Scout and social-preview edits present at the start were preserved, verified and included in the release.

## Verified state — 14 October 2026

- Local command: `python -m unittest discover -s tests -t .` — **64 tests passed**. pytest also passed during implementation; the final authoritative count is the unittest run.
- Syntax checks passed for dashboard.js, scout.js and playerview.js. `git diff --check` passed before release.
- [GitHub Actions run 38489876686](https://github.com/JonnoMillar/fpl-insights/actions/runs/38489876686) completed successfully: regression tests, fresh-data build and generated commit. CI ran the same 64 tests on Python 3.12.
- A local fresh build and the CI build loaded all nine recorded sources. The public projections feed returned HTTP 200, GW7 and **667 players**. The preview image at /docs/og.png returned HTTP 200 with image/png.
- The CI-generated live page showed **14 Oct 2026, 00:24 UTC** at final verification, with standards mode, English document language, viewport metadata and valid embedded JSON. Its decoded HTML was **2,821,397 bytes**. These are measurements at verification, not promises of current freshness.
- All four live tabs fit **320px and 390px** browser contexts without document overflow or broken embedded images. Keyboard main-tab selection, Scout's three positions, comparison shortlist, squad/Scout dialogs and Escape closing were checked. No console errors were observed during the checked flows.
- Controlled full builds with missing projections/Opta data and with no upcoming gameweek completed: squad/league retained, recommendations withheld, explanation visible. A simulated seven-hour-old snapshot displayed the overdue-update warning.
- Remaining unverified: physical phones, Safari/Firefox, screen-reader output, slow-device/network performance and predictive accuracy/backtesting. Do not claim these passed.

## Decisions made — and why

- Serve a full HTML document rather than a fragment: the fragment caused phones to scale a 980px desktop layout down to their screen.
- Bench Boost rebuilds show **one affordable upgrade at a time**, checked against the entire squad. The previous three-move rebuild reused the same bank independently and was £2.1m short. No new multi-transfer optimizer was added.
- Recover actual per-player selling values before affordability advice. If recovery fails, withhold the advice rather than overstate spending power.
- Use exact owned-XI selection and calculate a pair's combined effect on the resulting squad. Remove per-leg standalone gains from pair cards because their effects are not additive.
- Use one meaningful-gap threshold for Avoid versus the other transfer copy, exclude conflicting Buy/Avoid instructions, and derive timing text from the runner-up comparison. Triple Captain totals now use three times the individual score.
- Do not attempt a full double-gameweek model in this repair phase. Withhold recommendations when the eight-week planning window has doubles or incomplete/mismatched fixture coverage. Historical Scout doubles are labelled as multiple fixtures, with unmeasurable defensive hit rates excluded.
- Preserve the existing phone-alert feed interface. An unavailable/wrong-week feed lets the separate bot use its existing fallback; do not modify that private project as part of this dashboard task.
- Show snapshot age and source failures, with an overdue warning after **six hours**. Keep the existing three-hour best-effort schedule; no paid scheduler or extra service was introduced.
- Run offline regressions before publishing and on source changes. Workflow push-path filters exclude generated-only commits, avoiding rebuild loops. Explicit bash preserves pipeline failure status.

## Gotchas discovered this session

- The initial local checkout was behind production. Fetch and inspect divergence before editing; scheduled bot commits can arrive while work is in flight. The release push initially collided with a generated-only bot commit; it was rebased and the two generated-file conflicts were resolved using verified output. No force push was used.
- A projection outage broke not only player-dialog payloads but also Pick Team and fixture-rating pills. Those shared rendering boundaries are now safe; retain their regressions.
- Some Premier League portrait requests return 403. Existing shirt fallbacks work; these permanent failures now stop retrying immediately.
- GitHub authentication works when tools have the required host/network access. A sandboxed auth error initially looked like an invalid token; the approved host check succeeded. Do not ask Jonno to re-authenticate on that evidence alone.
- Vercel CLI credentials were unavailable. An automatic login prompt was cancelled; no account settings changed. Publication succeeded through the existing Git integration, so CLI login is not a prerequisite for this route.
- The stopped local server that worked used port 8766 outside the network sandbox. The first sandboxed server on 8765 was unreachable. Use approved tool access if the same socket restriction recurs.

## Next: brand, UI consistency and visitor walkthrough

### Review completed — 14 October 2026

- Read AGENTS.md, this handoff, README and the current render/CSS/interaction patterns. Used Impeccable design guidance; its context launcher could not install its engine in the sandbox, so existing project context was read directly. No PRODUCT.md, DESIGN.md or existing graphify graph was present. No design tools/dependencies were installed.
- Inspected the live page with the in-app browser at 1440×900, 390×844 and 320×740. The dedicated Playwright connector was unavailable because its browser profile was in use; the in-app browser provided screenshots, DOM evidence and interactions instead.
- Findings: purpose/author context is missing at arrival; six summary tiles push mobile navigation down (main tabs around 623px at 390px, 999px at 320px); Scout is partly outside the main-tab strip; Planning puts context/benchmark before decisions; initial mobile standings conceal scores; Scout comparison appears after a long table; similar fixture pills carry opposing rating scales.
- Verified sampled desktop tabs, mobile next-week pitch, player dialog/Escape, Planning section jump, league arrival, two-player Scout shortlist comparison and 320px keyboard ArrowRight tab activation. No document overflow in sampled states or errors in checked browser logs. These are browser viewport checks, not physical-phone, screen-reader or cross-browser certification.
- Saved recruiter and returning-player walkthroughs, shared component/terminology rules, five prioritised delivery passes and per-pass acceptance criteria. The brief preserves model/source/squad-publication limits, all prior correctness fixes and the lightweight architecture. No new numerical correctness conclusion was drawn from differently scoped forecast values.
- Documentation-only verification: `git diff --check` passed. Regression tests were not rerun; the previous 64-test result above remains historical evidence, not a new run. Application/deployment files remain unchanged.

### Original proposal preview — historical

Visual comparison prepared at Jonno's request: [local before/after preview](http://127.0.0.1:8766/comparison.html), with mobile/desktop switches and Arrival, Planning, Mini-league and Scout comparisons plus reasons. Durable files and screenshot captures are in `C:/Users/jonno/.codex/visualizations/2026/10/14/01a137d8-6cda-70e2-b6ad-0c76be0c871f/` (`comparison.html`, `before.html`, `after.html`, `comparison.png` and per-topic captures). The working copies reuse the committed snapshot; preview changes are applied only to the after copy. `.cache/build_design_preview.py` regenerates them locally and is ignored.

The preview was checked at 390px and 320px, with desktop comparison frames at 1280px. Corrected a preview column-count assumption and the sticky-navigation offset before completion. Confirmed captaincy/transfers lead, mobile standings show Team/Total/GW together, Scout selection and comparison jump work, and sampled states have no document overflow or logged errors. Preview JavaScript syntax was checked; production regressions/failure states were not rerun because application code and the hosted artifact remain unchanged. League sorting needs its event wiring updated before production column rearrangement; the preview states this limitation. No approval of the proposed direction is implied by requesting a visual comparison.

A localhost-only review server on port 8766 was left running for review. The original session ended; the current server and restart command are recorded under Hazards below. These local review assets are not a deployment and should not be staged as generated application output.

The first preview was a proposal, not approval. The current implementation checkpoint above records Jonno's subsequent requested changes. Keep Squad as the default main tab; do not silently choose a new forecasting model or replace the design world.

The original phase acceptance criteria remain:

1. Inspect the current live page on desktop and mobile, plus dashboard.css, dashboard.py, cards_*.py and relevant feature scripts. Assess the experience of a recruiter arriving from a CV and an FPL user making decisions. Acceptance: a concrete map of what each visitor should understand or do first, and where the current page obstructs that.
2. Develop a coherent brand direction and information hierarchy for this existing product. Acceptance: a concise design brief covering identity, type/colour roles, terminology, density, shared components and the relationship between Squad, Planning, Mini-league and Scout. Ground recommendations in observed content, not generic dashboard trends.
3. Prioritise the UI/logic changes and define the intended walkthrough before a broad redesign. Acceptance: a focused implementation sequence with desktop/mobile interaction checks; identify which data and features can remain exactly as they are.
4. Implement the agreed direction in focused passes, using the relevant design skills and existing architecture. After meaningful changes, run the regressions and verify actual views/interactions at narrow widths and with the keyboard.

Do not introduce a framework, bundler, database, account system or paid service just for polish. Do not reopen consent for league data/pictures; Jonno explicitly settled that. Do not hide snapshot or model limits to make the page look cleaner. Preserve compatibility with projections.json and the existing deployment workflow.

## Open questions for Jonno

- **Non-blocking:** response to the revised working comparison; further recruiter-oriented product/author context remains a separate design choice.
- **Non-blocking:** how much explanatory guidance the CV visitor needs without slowing experienced FPL users. The showcase objective is established; use a mixed-audience assumption until clarified.
- No unresolved blocker from the functional-repair phase.

## Hazards at handoff

- Local-only comparison server is intentionally running on port 8766 as a hidden background Python process (PID 48336), with logs in `.cache/review-server*.log`; stop after review. Restart with `python -m http.server 8766 --bind 127.0.0.1 --directory C:/Users/jonno/.codex/visualizations/2026/10/14/01a137d8-6cda-70e2-b6ad-0c76be0c871f`. Sandbox network access required approval on this host. The old exec server ended on session reset, so this process keeps the comparison available. No login flow or background build remains running. Browser cache briefly returned a blank local page after restart; an uncached review query loaded the complete document.
- At checkpoint start, tracked work was clean. Untracked **.agents/** contains the pre-existing project-check skill; **.playwright-mcp/** contains audit snapshots and screenshots. Leave these intact; do not accidentally stage them as application changes.
- .cache/cv/ contains ignored build logs, generated verification pages and a boundary-check script. It is local evidence, not a deploy source of truth. The committed dashboard-artifact.html is the hosted artifact.
- The earlier autostash was successfully reapplied during the initial fast-forward. There is no active rebase or known unresolved stash work from this session.
- Finished source changes, next_action.py, its tests and this handoff are checkpointed together. The commit SHA is reported in the chat; the live hosted artifact is unchanged.

## Resume prompt

```text
Read AGENTS.md, docs/HANDOFF.md and docs/audits/2026-10-20-apple-design-showcase.md. The apple-design CV review is complete; its direction is proposed, with no application edits. Incorporate Jonno's feedback before implementing. Preserve the weekly review hero on desktop and mobile, stable pitch, existing functionality, correctness guards, visible model limits, phone-feed compatibility and Python/vanilla JavaScript architecture. Current source differs from the live UI; the local review HTML contains historical data. If publication is requested, fetch/integrate scheduled commits, run a fresh complete artifact build and regressions, verify source health/projections and browser flows, then use the existing Git deployment.
```
