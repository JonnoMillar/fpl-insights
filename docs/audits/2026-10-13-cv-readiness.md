# FPL Insights: CV readiness audit

Audited 13 October 2026. Live site: https://fpl-insights-jm.vercel.app/

## Verdict and scope

Fix the mobile document, impossible Bench Boost rebuild, contradictory advice, and failure handling before putting this link on a CV. There are also confirmed defects in the recommendation calculations and JSON embedding that should be resolved before calling the recommendations dependable.

This is a diagnosis, not an implementation. No application code was changed. Existing uncommitted changes were left intact. Consent and rights to league data and pictures are accepted as settled. Brand direction, visual consistency, onboarding and the intended walkthrough are reserved for the next phase.

The product is a static Python-generated dashboard for one FPL manager and an eight-person league, with JavaScript interactions. The expected audience is occasional visitors and recruiters, including phone users. That makes first-load readability, coherent advice and unattended reliability more important than speculative server scaling. There is no account or transactional backend to assess here.

The local checkout's latest commit is dated 27 September, while production has newer changes. I checked current public upstream source for the central findings as well as the live page; the passing tests described below apply to the local working tree, not a separately executed production checkout.

## Must fix before sharing

### 1. Phones receive a shrunken desktop page

**Evidence:** In a mobile browser context with a 390px screen, the live page reports a 980px layout viewport. It has no viewport meta tag, no document language, and runs in `BackCompat` (browser quirks mode). The screenshot at `../../.playwright-mcp/audit-mobile.png` shows the resulting tiny type and controls.

**Cause:** `dashboard.render(..., standalone=False)` produces a fragment. The CLI publishes that fragment, and `vercel.json` serves it as the actual website. Only the standalone branch gets the doctype, language, character encoding and viewport.

**Smallest fix:** Serve the full standalone HTML on Vercel; keep fragment output only if an artifact consumer still needs it. Fix the document title at the same boundary.

**Verification:** A controlled browser response with a doctype and viewport switched to a 390px viewport and standards mode, with no whole-document horizontal overflow across all four tabs. Verify the final generated and deployed document on 390px and 320px screens; check internal scrolling and dialogs too.

**If skipped:** A recruiter opening the CV link on a phone sees what looks like an unfinished desktop export.

Source: `dashboard.py:453`, `cli.py:225`, `vercel.json`.

### 2. The live Bench Boost rebuild is unaffordable and shows the wrong week's fixtures

**Evidence:** The page shows £3.1m in the bank. The proposed rebuild replaces Dubravka (£4.0m), Diop (£4.0m), and Hughes (£4.4m) with Donnarumma (£5.5m), Tarkowski (£6.2m), and Manzambi (£5.9m). That requires £5.2m extra, at least £2.1m beyond the displayed bank. These are the actual live card prices, even before adjusting sale prices for retained profits.

The heading says GW13, but the fixture pills show GW7 opponents: Donnarumma versus IPS, Tarkowski versus CHE, and Manzambi at NEW.

**Cause:** Each swap is checked against the same bank independently, then rendered as one rebuilt bench. The scorer is given only the bench, so it also lacks the starting XI's ownership and club-limit constraints. Rendering passes `next_gw` to fixture pills instead of `bb['gw']`.

**Smallest fix:** Validate the combined rebuild against the full squad, one shared budget, actual sale values, distinct incoming players and the club limit. If the intended output is independent alternatives, present them as alternatives rather than a proposed bench. Render the recommended week's fixtures.

**Verification:** Reproduce these three moves; the impossible combined bench must be rejected or explicitly separated into alternatives. Check a squad already holding three players from an incoming player's club, and an incoming player already owned in the XI.

**If skipped:** The site presents an impossible action as its recommended team, with misleading match context.

Source: `chips.py:322`, `cards_planning.py:459`, `transfers.py:1139`.

### 3. Advice contradicts itself and chip copy gets basic arithmetic wrong

**Evidence:** Palmer appears in both Buy and Avoid on the live board. Avoid justifies rejecting him with Cherki projecting only 0.9 more across five weeks, while nearby copy treats a 2.93-point gap as noise. The Triple Captain card says Haaland projects 7.7 and 15.3 with the armband, while claiming that is 7.7 more than normal captaincy. The displayed total is doubled, not tripled; the unrounded projection should be multiplied by three for Triple Captain.

The Bench Boost timing also says "clearly the best week in the window" alongside "Timing flexible". Its strip compares the maximum to the minimum; the confidence calculation compares it to the runner-up, so one poor week can generate the strong sentence even with several nearly equal good weeks.

**Smallest fix:** Give the Buy/Avoid relationship explicit precedence or qualified wording; apply a consistent meaningful-gap rule. Show normal captaincy, Triple Captain total and incremental gain correctly. Derive timing sentences and confidence labels from the same runner-up comparison.

**Verification:** A player cannot receive conflicting unconditional instructions. An 8-point single score produces 16 normal-captain points and 24 Triple Captain points, an 8-point uplift. A synthetic series such as 100, 99, 20 must not claim the winner is clearly separated from its nearest alternative.

**If skipped:** A reader can spot the contradictions without knowing the implementation, weakening trust in all the numbers.

Source: `transfers.py:572`, `cards_planning.py:526`, `cards_planning.py:569`.

### 4. A blank fixture or projection outage can stop the entire refresh

**Evidence:** Calling `cards_squad.player_payload` with missing projections raises `KeyError: 'opp'`. `ffs.ticker` emits a `{'gw': ..., 'blank': True}` record when there is no projection, but the dialog payload assumes every record has `opp`, `home`, `cs` and `xg`. A real blank in the next six weeks follows the same path.

**Smallest fix:** Carry blank and unavailable states through payloads and the player dialog. Distinguish a confirmed no-fixture week from a failed source. Optional data must not prevent rendering the core squad and league.

**Verification:** Build from controlled input with an empty projection feed and with one blank among the next six weeks. Both builds should finish, preserve the core page and visibly identify what is unavailable. The latest valid page should survive a genuinely fatal build failure.

**If skipped:** One optional source failure or scheduled blank leaves the public page stuck on an older build.

Source: `cards_squad.py:832`, `ffs.py:ticker`, `dashboard.py:build`.

### 5. Free-text names can escape the chart's JSON script element

**Evidence:** League names are inserted using `json.dumps(data)` inside an HTML `<script type="application/json">`. JSON escaping does not escape the HTML `</script>` boundary. A controlled synthetic name closed that element, made its JSON unparseable, and executed a harmless `window.__auditProbe=1` marker in an isolated test page.

**Scope:** This confirms an unsafe rendering boundary. It does not establish that FPL accepts the synthetic string through its own name validation, or that any league member has supplied malicious input. No live names or external data were changed. Consent to display names does not resolve this technical boundary.

**Smallest fix:** Use one script-safe JSON encoder for every embedded JSON payload, escaping `<` as `\u003c` at minimum. Continue ordinary HTML escaping in visible text and attributes. Do not HTML-entity-encode the entire JSON blob, which would break parsing.

**Verification:** Names containing closing-script text, quotes, ampersands and accented characters must round-trip as text, produce valid JSON and create no extra executable elements.

**If skipped:** An upstream free-text value can break the page or inject markup; script execution is possible if the dangerous value reaches this boundary.

Source: `cards_league.py:639`; the same encoding pattern also appears in squad, Scout and planning payloads.

### 6. The transfer baseline can bench the better goalkeeper because he is cheaper

**Evidence:** A controlled legal fifteen-player pool, compared against exhaustive enumeration of its legal elevens, returned 68 from `transfers._xi_value` where the actual maximum was 163. The cheap goalkeeper carried a value of 100 and was assigned to the bench before the XI search. This exaggerated test value isolates the defect; it is not a claim about a real player's projection.

**Cause:** `_xi_value` reuses `squadbuilder.best_xi`, whose cheap-bench-first strategy reserves the cheapest goalkeeper before optimizing. That is unsuitable for choosing an XI from an already owned squad with effectively unlimited selection budget. Transfer gains and Wildcard comparisons inherit the error.

**Smallest fix:** Select the best legal XI directly from the owned fifteen for these comparisons. Keep budget-oriented full-squad construction separate where it is actually required.

**Verification:** Compare with exhaustive legal selection for small controlled squads, including a cheaper but stronger keeper and strong cheap outfield players. The selected score must not depend on arbitrary price order when only team selection is being decided.

**If skipped:** Transfers can be ranked against the wrong baseline, and the model can invent gains or miss genuine improvements.

Source: `squadbuilder.py:148`, `transfers.py:526`, `chips.py:wildcard`.

### 7. Transfer-pair gains are not calculated on the resulting pair

**Evidence:** `pair_suggestions` sums the two independently calculated XI gains. In a controlled squad, the independent gains summed to 89 while applying both moves and recomputing the XI produced 88, before the separately documented bench allowance. The two moves can change formation and displace the same player, so their effects are not generally additive.

**Smallest fix:** Apply both outgoing and incoming players to a single candidate squad, calculate the resulting legal XI, then subtract the unchanged baseline once. Treat any bench allowance separately and consistently, then deduct the actual hit.

**Verification:** Assert the displayed combined gain equals the combined before/after calculation, including a pair competing for the same XI slots and a formation change. Fix finding 6 first so this comparison has a sound baseline.

**If skipped:** Pair rankings and "still ahead after a hit" claims can be based on a gain the actual squad does not receive.

Source: `transfers.py:1093`.

### 8. "Affordable" transfers use current price instead of actual selling price

**Evidence:** Single moves, Buy/Sell funders and pairs use `r.price`, the player's current price. The dashboard already calculates per-player selling values, but discards that mapping after summing it for chip budgets. A player bought at £5.0m and now costing £6.0m sells for £5.5m; a proposed £9.1m purchase with £3.1m in the bank is £0.5m short, despite passing the current-price check. This is a controlled boundary example, not a claim that this exact move currently appears.

**Smallest fix:** Feed the available per-player sale values into all affordability checks and bank-after calculations. Keep an explicitly uncertain fallback when purchase history cannot be recovered. Current pre-deadline transfers and bank balances may remain unavailable from public data; identify the snapshot rather than claiming authenticated current state.

**Verification:** Rising, falling and unchanged-price examples; two sales funding one pair; and a missing-history fallback. Visible affordability wording must match the evidence available.

**If skipped:** Someone follows a recommendation and discovers the FPL site will not allow it.

Source: `analysis.py:434`, `dashboard.py:build`, `transfers.py:668`, `transfers.py:1073`, `transfers.py:1199`.

### 9. Freshness and partial failures are not communicated reliably

**Evidence:** The live snapshot is timestamped 13 October at 10:09 UTC. The latest six public scheduled runs started at 10:06 and 02:24 on 13 October, 20:55 and 10:14 on 12 October, and 00:13 and 19:20 across 12/11 October: approximately 5–11 hours apart. This verifies that the observed refresh cadence does not meet the README's three-hour wording; it does not identify why the scheduler was delayed or omitted runs.

The workflow step named "Fail if a source dropped out" only emits a warning. It does not fail or prevent publishing. Source-health information is printed to logs rather than carried into the public page. Existing tests are also not run by this build workflow.

**Smallest fix:** Label the page as a snapshot and compute its age in the browser, with a visible stale state. Include source-specific availability and prevent unsupported advice from appearing normal. Define fatal versus optional failures, retain the last valid artifact for fatal failures, and put focused regression tests in the publishing workflow. Adjust the promised cadence to what can actually be guaranteed; another scheduled service is not automatically necessary.

**Verification:** A simulated old timestamp and failed optional source must be visible to visitors. A fatal failure must not publish a replacement. A regression-test failure must block publication.

**If skipped:** The page can look current and complete while presenting old price, team-news or recommendation data.

Evidence: https://github.com/JonnoMillar/fpl-insights/actions/runs/38381073012 and the public Actions run history. Source: `.github/workflows/build.yml:51`, `.github/workflows/build.yml:58`, `fplapi.py:HEALTH`.

## Should resolve or clearly limit before long-term showcasing

### 10. Fixture and line-up data are used outside the scope they describe

**Evidence:** With no projection row, the owned-player scorer returned the same NFO fixture and 4.88 points for both GW7 and GW8 from one market record. A known blank can therefore acquire a fictitious match. Double-gameweek Scout history uses aggregated weekly stats with only the first fixture's opponent and a single defensive-contribution hit decision. `Ctx.is_predicted` checks photo membership but does not check the club name the scraper now records. The next-week calculation adds one to `current_event` even when that helper falls back to an already-next event, and caps at 38 after the season ends.

**Smallest fix:** Use authoritative FPL fixtures to establish zero, one or multiple matches for each gameweek. Join market data by fixture identity/date and venue, not only club or opponent, and validate line-up club identity. Use the actual next event when available and an explicit season-ended state. If double-gameweek modelling stays out of scope, visibly mark affected recommendations as unsupported and suppress definitive chip timing rather than silently presenting a single match as the whole week.

**Verification:** Confirmed blank with market data present, a double gameweek, a player moved between clubs, pre-season/no-current-event, and season completion. Some of these are future boundary risks, not failures of today's ordinary GW7 fixtures.

**If skipped:** Advice can remain plausible while describing the wrong match or week, especially around the very weeks when chip decisions matter most.

Source: `analysis.py:76`, `analysis.py:950`, `transfers.py:185`, `scout.py:309`, `dashboard.py:585`.

### 11. The shared link has no product description or preview

**Evidence:** The deployed document has zero meta elements and its browser title is only "Savin Kluivert Rayan". `/docs/og.png` returns 404. Local uncommitted changes already add social metadata and an image, but those are not deployed and do not repair the fragment's missing document shell.

**Smallest fix:** Complete and verify the existing metadata work alongside finding 1. Use a title identifying FPL Insights and a useful description; include only a preview image that is actually published and accessible.

**Verification:** Read the deployed HTML and confirm title, description and preview tags are in the document head; the declared image returns 200 with an image content type. Avoid treating source edits as proof of deployment.

**If skipped:** Browser tabs, saved links and previews fail to identify the showcase properly.

Source: `dashboard.py:render`, existing `dashboard.py` diff, `docs/og.png`.

### 12. Main tabs declare accessibility semantics but lack the corresponding keyboard behaviour

**Evidence:** Focusing Squad and pressing Right Arrow leaves focus and selection on Squad. Main tabs have `role="tab"`, but lack the tab/panel associations and roving focus implemented for the Scout position selector. The deployed document also lacks `lang`; fixing finding 1 supplies it.

**Smallest fix:** Reuse the established Scout keyboard pattern for the main and pitch tabs: Arrow keys, Home/End, a deliberate activation policy, roving focus and explicit tab/panel labels and controls. Preserve normal Tab/Enter access to controls and dialogs.

**Verification:** Navigate each view by keyboard, confirm visible focus and matching selected/panel state, and test dialog close/focus return. This is a specific functional accessibility check, not a claim of a complete accessibility certification.

**If skipped:** A keyboard or assistive-technology user gets controls that do not behave as their declared roles imply.

Source: `dashboard.js:92`, `dashboard.py:render`, `scout.js` position navigation.

## What passed and what was not checked

- Local Python suite: **49 passed, 9 subtests passed** in 0.15 seconds. Current coverage is concentrated on Scout and transfer-board calculations; these passes do not cover the defects reproduced above.
- Live Chrome/Chromium checks: all four main tabs switch; all three Scout position views populate; price filtering reaches zero and restores results after committing the field; shortlist comparison works; squad and Scout dialogs open and Escape closes them; the league chart toggles between positions and points; Pick Team and predicted-points toggles respond.
- No browser console errors during those normal desktop interactions; no broken embedded images observed. The first observed document transfer was about **715 KB**, expanding to about **3.21 MB**. That is measurable weight, but this run does not establish a performance blocker. Optimize it after correctness unless slower-device testing shows otherwise.
- No obvious private-key or common token patterns found in the searched project files. Public team/league IDs and static source files are not treated as secrets. This is a focused scan, not a full Git-history secret audit.
- GitHub CLI access failed from this environment; public read-only GitHub API and source requests succeeded through the browser runtime. No credentials, workflow settings or deployments were changed.
- Not checked: a full fresh-data rebuild, authenticated FPL state, real upstream acceptance of the synthetic injection string, model predictive accuracy/backtesting, production test execution, Safari/Firefox, physical phones, screen-reader output, slow-network/low-end-device performance, or every combination of chips and transfer history.

## Recommended repair order

1. Fix the served HTML shell and complete existing link metadata.
2. Make missing/blank data safe and escape embedded JSON.
3. Repair the owned-XI baseline, actual selling values and combined transfer/rebuild validation.
4. Remove visible recommendation contradictions and correct chip arithmetic and target-week fixtures.
5. Add focused regression gates and visible freshness/source status; cover or suppress unsupported fixture boundaries.
6. Verify the deployed result on desktop, phone-sized contexts and keyboard navigation.

Only then move to brand identity, hierarchy, consistency and the visitor walkthrough. There is no reason to introduce a framework, database, account system or paid service to address the confirmed issues.

## Resolution work — 14 October 2026

Implemented the corrections above without introducing a framework or dependency.
Bench Boost now proposes one affordable upgrade, checked against the entire squad;
it does not claim a coordinated three-move rebuild. Pair gains are recomputed on
the resulting squad, and per-leg standalone gains were removed from the display
because they are not additive. Existing Scout and social-preview edits were
preserved and checked alongside the fixes.

Double-gameweek projections remain unsupported: recommendations are withheld for
affected planning windows, and historical Scout aggregates are labelled as multiple
fixtures rather than attributed to one opponent. The page reports snapshot age and
unavailable sources; after six hours it displays an overdue-update warning. A
three-hour scheduler remains best-effort. These are explicit limits, not claims
that the model or scheduler now supports everything.

Verification: 64 offline regression tests pass; JavaScript syntax checks and the
diff whitespace check pass. A complete fresh build loaded all nine recorded sources
and produced a 667-player projections feed. Browser checks covered all tabs at
320px and 390px without document overflow, keyboard tab navigation, Scout filters
and comparisons, dialogs, and corrected chip/rebuild content. Full builds with
missing projections/Opta data and with no upcoming gameweek also completed, retaining
the squad and league while withholding advice. Some portrait URLs return HTTP 403;
existing shirt fallbacks are used, with no pointless retry delay.

Still unverified: physical phones, Safari/Firefox, screen-reader output, and predictive
accuracy/backtesting. Deployment verification is recorded in the accompanying chat.
