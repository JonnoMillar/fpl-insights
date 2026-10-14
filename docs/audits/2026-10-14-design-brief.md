# FPL Insights — brand, UI and visitor walkthrough proposal

Status: proposed direction, awaiting Jonno's response before UI implementation.
Reviewed: 14 October 2026. Scope: the existing CV showcase and FPL dashboard.

## Recommendation

Treat FPL Insights as a **football analysis desk**: a personal, working tool that explains the numbers behind squad decisions. Keep its purple ink, green accent, warm paper, Archivo headings and Plex Mono figures. Its distinctiveness should come from clear editorial hierarchy, precise labels and useful comparisons. The current visual identity is a sound starting point; a new palette, logo exercise or landing-page detour would not solve the main problems.

Suggested product line: **The numbers behind your FPL decisions.** Follow with a short factual context line: **Jonno Millar's squad and mini-league, analysed from public data.** This makes the personal scope clear before visitors interpret “your” as their own team. Include a readily accessible “About & methods” disclosure and a clearly named GitHub source link. Keep detailed technical explanation there, not in the primary decision flow. These are proposed additions to orientation, not claims of validated predictive performance.

Assumption: both a recruiter with little FPL knowledge and an experienced FPL player should be able to use the same page. The dashboard remains the entry point; no separate marketing site, tour overlay or onboarding gate.

## Evidence from the live experience

Inspected https://fpl-insights-jm.vercel.app/ in the Codex in-app browser at 1440×900, 390×844 and a narrower 320×740 viewport. The page displayed the 14 Oct 2026, 00:24 UTC snapshot. Browser-generated age appeared as 17–18 minutes; it depends on the browser clock and is not a statement of current freshness. Local HEAD was c4a8a11; the generated artifact came from 3306697. No deployment comparison or new freshness audit was needed for this design review.

| Observation | Consequence | Proposed response |
|---|---|---|
| Arrival leads with “Savin Kluivert Rayan”, six tiles and a retrospective verdict; purpose is not stated. The source link is in the footer. | A CV visitor must infer what the product does and whose data it shows. | Add compact product orientation and source/method access; make the team name secondary to product identity. |
| At 390px, the hero is about 445px tall and main tabs start about 623px from document top. At 320px the hero grows to about 771px and tabs start about 999px down. | Navigation and the actual tool arrive late on narrow screens. | Move main navigation above the large team summary; replace the persistent six-tile hero with a compact summary and tab-relevant context. Keep every metric accessible. |
| Scout is partly outside the mobile main-tab strip; pitch controls also share one horizontally scrolling strip with metric toggles. | Primary destinations and controls depend on discovering sideways scrolling. | Fit four main tabs at 320px; give pitch view and metric controls separate wrapping rows. |
| Planning opens with market odds, a highest-points XI and the knee-jerk card. Captaincy follows verdicts, six single transfers and pairings. | The user must pass contextual exploration before the main next-week decisions. | Lead with captaincy and affordable moves; put market context and the unconstrained XI in supporting analysis. |
| The highest-points XI explicitly says it is selected without budget and is not a squad you can build. | Its honest caveat currently competes with the prominent “best XI” framing. | Name it “Unconstrained XI benchmark” and retain the caveat beside the score, at lower prominence. |
| Buy/sell/keep/avoid repeats names and advice later presented as actionable transfer cards. | Visitors must decide which of two presentations to follow. | Make verified transfer suggestions the main surface; keep verdict categories as supporting summary, without changing their calculations. |
| At 390px, the league table initially shows rank, team and manager; gameweek and total points require horizontal scrolling. | The standings conceal the two figures that make them standings. | Put rank, team, total and gameweek points first on mobile, with manager subordinate; retain captain/chip/bench/hits/xGI in detail. |
| Scout starts with “Worth a look”, fixture runs, then a filterable pool/scatter/table. Two selected names produce a useful comparison below the long table. | Discovery is rich, but the filter → shortlist → compare path is far apart. | Place a direct “Explore & compare” entry beside curated shortlists; surface selected count and a route to the existing comparison near selection controls. |
| Scout uses 1–5 difficulty (lower kinder); Planning uses 0–10 fixture rating (higher better). All are explained, but similar pill shapes require relearning the scale. | The same visual grammar carries opposite numerical directions. | Keep both definitions; always label scale/direction locally and visually distinguish difficulty from rating. Do not silently convert either model. |
| “Needs a look: 0” refers to an XI while Availability lists a bench player's doubt. Forecast figures also vary by model/context. | Without scope labels, honest values can seem contradictory. | Label “Starting XI alerts”, retain bench notices and state model/horizon beside forecasts. Trace each forecast's source before deciding whether any discrepancy is a defect. |
| Small annotations, many uppercase headings and nested coloured panels recur across cards. The owned highlight, chart categories and decision colours are not always distinguishable by their purpose. | All cards compete for attention, and metadata can be harder to read than the underlying decision. | Use fewer emphatic headings, consistent text sizes and semantic colour roles; keep charts' local category keys explicit. |

Positive evidence to preserve: restrained palette; tabular figures; recognisable pitch; visible source and squad-publication limits; small-sample cautions; honest benchmark caveat; section rail; sortable tables; working player details and Scout comparison. No document overflow was observed in the sampled 1440/390/320 states. Internal table scrolling is intentional and should remain confined to table wrappers.

Interactions sampled: all four desktop tabs; mobile Pick team; Haaland player dialog and Escape close; Planning section jump; Mini-league arrival; Scout pool jump; Gabriel/Calafiori shortlist comparison; main-tab ArrowRight activation at 320px. The keyboard action selected Planning, the comparison displayed both players, and the checked browser logs contained no errors. Screenshots and DOM observations were used together. A visible scrollbar in player detail was not treated as a page-overflow bug: the open dialog's client width equalled its scroll width, and the wide match-log table was internally scrollable.

Not verified in this pass: physical touch devices, Safari/Firefox, screen-reader output, network/device performance, predictive accuracy, every position/filter combination, or complete accessibility compliance. The existing 64-test correctness result belongs to the previous phase; it was not rerun for this documentation-only proposal.

## Intended walkthroughs

### CV visitor: understand, try, inspect

1. **Arrival:** read product purpose, author/personal squad context and snapshot state. See navigation and a real squad preview in the first mobile viewport. Success: explain what the tool is and whose data it uses without opening README.
2. **Squad:** see the latest published XI, next-gameweek forecast and availability scope. Open one player to see observed performance separately from modelled next-match points. Define xGI as expected goal involvement at first use; explain other acronyms locally.
3. **Planning:** inspect one captain option or affordable transfer, with gameweek/horizon, projected XI benefit, spending/hit consequence and adjacent limits. Success: understand the evidence behind a suggestion without mistaking it for a guaranteed outcome or an executed change.
4. **Scout:** select a position, filter the pool and compare two players. Success: discover the interactive work rather than merely scroll a long report.
5. **Mini-league / methods:** inspect standings and the context behind results; open source/method notes to understand the public-data joins, static Python pipeline and modelling limits. Technical detail supports the artifact after visitors have used it.

This is a suggested reading sequence, not forced navigation. All four tabs remain peers. No sample recommendation should be hardcoded: showcase copy must survive outages and changing data.

### Returning FPL user: review, decide, investigate

1. Check snapshot/source state and the last-published squad context.
2. Review next-week starting XI and availability; open a player when needed. “Pick team” must say it is an analysis view, not a control that changes the FPL account.
3. Open Planning: captain options → affordable transfer suggestions → paired transfers/hit cost → chips and fixture window.
4. Use Scout to inspect alternatives and Mini-league to understand rivals. Supporting market/benchmark analysis remains one section jump away.

Keep Squad as the default main tab. Within it, trial clearer labels (“Season overview”, “Next gameweek”, “Last gameweek”) and a next-gameweek-first composition; choose the default pitch view in the first layout pass only after checking its unavailable-data state. Do not accidentally imply the displayed XI includes private pre-deadline changes.

## Shared brand and component rules

| Area | Proposed rule |
|---|---|
| Identity | Keep FPL Insights and the current palette/type families. Purple supplies ink and structure; warm paper supplies ground; white supplies data surfaces. Use green for selection and a small number of focal actions. No oversized decorative hero. |
| Colour semantics | Green/red describe favourable/unfavourable outcomes with text or arrows; amber means caution/unavailable/needs review; teal identifies market provenance; pink means owned/Jonno; blue identifies rivals. Chart category colours remain local to a visible legend. Keep existing contrast-safe ink tokens; bright green is fill, not body text. |
| Type | Archivo for words, Plex Mono for figures. Sentence case for ordinary card titles; expanded display type limited to product/chapter hierarchy. Aim for 14–16px explanatory copy and 12–13px metadata; avoid essential 9–11px text. Dense tables may need internal scrolling rather than smaller type. Check actual rendered sizes and contrast. |
| Density | One question and one dominant answer per card. Desktop may place related decisions side by side; mobile uses a single reading column and short summaries before detail. Do not add blank space that pushes useful content farther away. |
| Card anatomy | Title/question → scoped answer → reason/evidence → consequence → caveat/source → optional detail. Use existing card and info-button patterns; critical validity limits stay visible, explanatory derivations may expand. |
| Numbers | Standardise display precision by meaning: forecast points/gains normally one decimal, money £x.xm, probabilities whole %, ranks with separators. Preserve raw calculation precision and feed values. Put unit, gameweek/horizon and individual-versus-XI scope beside the number. |
| Vocabulary | “Expected points” for the model output; “Predicted line-up” for FFS; “Projected XI gain” for squad effects; “Market odds” for quoted prices; “Derived” for quantities inferred from them. Keep different model estimates distinct until their source has been traced. Avoid “certainty”, “nailed on” or “will not repeat” when the evidence supports only a historical rate or likelihood. |
| Fixtures | Opponent plus explicit (H)/(A), scale and direction. Retain uppercase/lowercase as redundant familiar cues. Difficulty 1–5 and rating /10 remain separate concepts. Preserve confirmed blanks, missing data and double-gameweek withholding. |
| Interaction | Visible text names for navigation and disclosure controls; consistent selected/focus states; touch targets around 44px for primary mobile controls; reduced-motion support. Keep keyboard tab behaviour and Escape close. Give hover-only chart values a touch/keyboard-readable equivalent. |
| Mobile tables | Keep identity and key outcome visible together; put secondary columns in a confined scroll region or existing disclosure. Retain access to every column, sort action and sample warning. Selection/compare actions must stay discoverable. |
| Trust states | Always show snapshot age and publication context. Preserve overdue warning, optional-source failures, unavailable predictions and DGW limits. Alerts precede affected advice, not the footer. “No alerts” and “data unavailable” must never share reassuring treatment. |

## Prioritised delivery plan

Each pass ends with a final diff review, appropriate checks, a HANDOFF update and a focused commit. Implementation is not part of this proposal.

| Order | Focus and likely owners | Acceptance |
|---|---|---|
| **P1 — arrival and navigation** | `dashboard.py`, `dashboard.css`, `dashboard.js`: product/context line, compact global summary, main tabs above team detail, accessible source/method entry, separate pitch controls. | At 320×740 and 390×844, all four tabs are visible without sideways scrolling and real squad content begins within the first viewport in a normal healthy state. Warnings may legitimately push content down. Desktop remains useful at 1440×900. Primary tabs remain reachable after section jumps; sticky rails do not obscure targets/focus. |
| **P1 — decision hierarchy and scope** | `dashboard.py`, `cards_planning.py`, `cards_squad.py`: captaincy and transfers first; supporting market/benchmark analysis later; explicit XI alert and forecast scopes; distinguish personal sample from visitor account. | Visitor can find one captain and one affordable move before benchmark/market exploration. Every suggestion retains budget/hit/horizon context. Paired effects stay combined; no per-leg additive claims. DGW/outage guards still withhold advice. Copy identifies unvalidated estimates as estimates. |
| **P2 — shared visual language** | `dashboard.css`, `cards_common.py`, `components.py` and affected card renderers: type/spacing, card anatomy, labels, precision and semantic colours. | Representative squad, transfer, chip, league and Scout cards share rules; no essential text depends on colour/hover alone. Critical limits remain visible. Forecast source differences are labelled after tracing, not flattened by cosmetic renaming. No new rendering framework or blanket renderer rewrite. |
| **P2 — mobile league and Scout path** | `cards_league.py`, `cards_scout.py`, `scout.js`, `dashboard.css`: standings priority, filter/selection/comparison proximity, direct pool entry. | Mobile shows team + total/GW score together; secondary data remains accessible. Select two names, reach comparison, change filters/position and clear selection without losing understandable state. Preserve six-player cap and sample cautions; no new scouting engine. |
| **P3 — showcase explanation and final walkthrough** | Existing disclosure/footer patterns, README and screenshots after UI is agreed. | Short factual project story, accessible glossary/method notes and direct source link. CV walkthrough works with keyboard and at narrow widths; README/screenshots describe the shipped UI. No predictive-accuracy or guaranteed freshness claims. |

Verification during UI implementation: run the dependency-free regression suite; syntax-check edited JS; `git diff --check`; build a complete hosted document using a temporary output and review the real generated page. Test healthy, missing-projection/optional-source, no-upcoming-GW, double-GW and overdue states where affected. Check all four tabs at desktop/390/320, a player dialog, Scout filter/compare, internal table scrolling, keyboard arrows/focus/Escape, reduced motion and settled sticky/tab geometry. Preserve the last valid generated artifact; do not publish a design pass until verified. Fetch and integrate scheduled bot commits before any release without force-pushing.

Unchanged foundations: Python standard library + optional Pillow; vanilla JS; static/self-contained output; actual modelling, fixture bindings, recovered selling prices, owned-XI selection, transfer-pair constraints, public projections feed interface, source-failure handling, CI and Vercel route. No paid service, dependency, account system, data-consent review or unrelated feature is required.

## Next decision

Jonno can accept this direction or adjust the emphasis between personal football identity and analyst presentation. The recommended first implementation is the compact arrival/navigation pass, then decision ordering. This brief is a proposal, not an approved redesign contract.
