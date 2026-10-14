# HANDOFF — FPL Insights

Last updated: 14 October 2026, checkpoint after the CV-readiness fixes were deployed and verified.

## Status

Jonno intends to link the live dashboard on his CV. The first phase was a deep audit of glaring functional, correctness and reliability risks, followed by fixes. That phase is complete and live at [FPL Insights](https://fpl-insights-jm.vercel.app/).

The next phase is sharpening brand identity, UI/UX, consistency, product logic and the intended visitor walkthrough. No new brand direction or broad visual redesign has been implemented in this chat. Read the [audit and resolution notes](audits/2026-10-13-cv-readiness.md) for evidence; avoid repeating the completed audit without new evidence.

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

1. Inspect the current live page on desktop and mobile, plus dashboard.css, dashboard.py, cards_*.py and relevant feature scripts. Assess the experience of a recruiter arriving from a CV and an FPL user making decisions. Acceptance: a concrete map of what each visitor should understand or do first, and where the current page obstructs that.
2. Develop a coherent brand direction and information hierarchy for this existing product. Acceptance: a concise design brief covering identity, type/colour roles, terminology, density, shared components and the relationship between Squad, Planning, Mini-league and Scout. Ground recommendations in observed content, not generic dashboard trends.
3. Prioritise the UI/logic changes and define the intended walkthrough before a broad redesign. Acceptance: a focused implementation sequence with desktop/mobile interaction checks; identify which data and features can remain exactly as they are.
4. Implement the agreed direction in focused passes, using the relevant design skills and existing architecture. After meaningful changes, run the regressions and verify actual views/interactions at narrow widths and with the keyboard.

Do not introduce a framework, bundler, database, account system or paid service just for polish. Do not reopen consent for league data/pictures; Jonno explicitly settled that. Do not hide snapshot or model limits to make the page look cleaner. Preserve compatibility with projections.json and the existing deployment workflow.

## Open questions for Jonno

- **Non-blocking:** preferred brand direction and balance between familiar FPL styling and a distinct personal identity. No direction has been chosen yet; inspect the product and propose a reasoned direction first.
- **Non-blocking:** how much explanatory guidance the CV visitor needs without slowing experienced FPL users. The showcase objective is established; use a mixed-audience assumption until clarified.
- No unresolved blocker from the functional-repair phase.

## Hazards at handoff

- No session dev server, login flow or background build remains running. Both local servers were stopped. The GitHub run completed and its generated commit was synced.
- At checkpoint start, tracked work was clean. Untracked **.agents/** contains the pre-existing project-check skill; **.playwright-mcp/** contains audit snapshots and screenshots. Leave these intact; do not accidentally stage them as application changes.
- .cache/cv/ contains ignored build logs, generated verification pages and a boundary-check script. It is local evidence, not a deploy source of truth. The committed dashboard-artifact.html is the hosted artifact.
- The earlier autostash was successfully reapplied during the initial fast-forward. There is no active rebase or known unresolved stash work from this session.
- AGENTS.md and this handoff are the checkpoint documents to commit. The commit SHA is reported in the chat to avoid embedding a self-referential SHA here.

## Resume prompt

```text
Read AGENTS.md and docs/HANDOFF.md, then begin the brand, UI/UX, consistency and visitor-walkthrough phase for FPL Insights as a CV showcase. Inspect the live desktop/mobile experience and existing components, then propose a coherent design direction and prioritised implementation plan grounded in concrete findings. Acceptance: a clear recruiter/FPL-user walkthrough, consistent brand/component rules, and focused changes with verification criteria. Preserve the completed correctness fixes, visible data/model limits, projections.json compatibility and the existing lightweight architecture; do not reopen league-data consent or add unrelated features.
```
