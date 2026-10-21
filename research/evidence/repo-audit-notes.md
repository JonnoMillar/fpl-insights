# Repository audit evidence

Audit date: **21 October 2026**. Source baseline: **`5546ef79a146f00b0d7684066174760be7121abf`**, local `main`, commit time `2026-10-21T14:38:29+01:00`, subject `merge: integrate reviewed squad UI with transfer planner`.

The current-data work wrote only `research/current-data.md` and this evidence note. No source/generated artifact, cache, price-history, HANDOFF or git commit was changed by this audit. Other research files may be produced concurrently by the parent task. Initial existing untracked directories `.agents/` and `.playwright-mcp/` were preserved.

## Method and commands

Read `AGENTS.md`, the current/recent part of `docs/HANDOFF.md`, README, config, workflow and deployment rewrite first. Read the Graphify skill; `Test-Path graphify-out/graph.json` returned **False**, so no graph generation/install was attempted, following the task's explicit constraint.

Read actual ingress implementations and traced named fields into production consumers. Representative commands:

```powershell
git rev-parse HEAD
git status --short
Get-Content -LiteralPath docs/HANDOFF.md -First 220
Get-Content -LiteralPath README.md
Get-Content -LiteralPath .github/workflows/build.yml
Get-Content -LiteralPath fplapi.py
Get-Content -LiteralPath ffs.py
Get-Content -LiteralPath odds.py
Get-Content -LiteralPath pulse.py
Get-Content -LiteralPath elite.py
rg --files -g '*.py' -g '*.js' -g '*.json' -g '*.yml' -g '*.yaml'
rg -n 'https?://|fetch_json|fetch_text|urlopen|Request\(|ttl|cache' fplapi.py odds.py ffs.py pulse.py elite.py cli.py dashboard.py
rg -n 'https?://|fetch\(|XMLHttpRequest|\.json|\.csv|open\(' --glob '*.py' --glob '*.js' --glob '!tests/**' --glob '!research/**'
rg -n '^def |payload|script_json|element|history|past|_pulse|photo|meta' cards_*.py
rg -n 'btts|supremacy|home_name|away_name|market_card' --glob '*.py' --glob '*.js' --glob '!tests/**'
rg -n 'news_added|scout_news_link|scout_risks|team_join_date|price_change_hourly_rate|calibrating|locked_until|multiplier|automatic_subs' --glob '*.py' --glob '*.js' --glob '!tests/**' --glob '!research/**'
git log -18 --date=iso-strict --format='%h %cI %s' origin/main
```

Additional chunks of `analysis.py`, `dashboard.py`, `transfers.py`, `planner.py`, `scout.py`, `captaincy.py`, all four card families, `components.py`, `report.py`, `cli.py`, `playerview.js`, `scout.js`, `dashboard.js`, `ticker.py` and the fixture scripts were read. AST passes listed constant subscripts/`.get` keys grouped by base variable. This was only a search aid: dynamic duty fields, generic Opta enumeration and config-driven Scout metric access were manually traced, because string searches alone would misclassify these as unused.

Cache inspection used Python imports for URL constants/hash calculation, `Path.read_text(encoding='utf-8')`, JSON shape/count inspection and UTC filesystem modification times. No fetch/client/build function was called. The script emitted keys/counts/times, not manager records. One exploratory inspection failed because `read_text()` used Windows cp1252; rerunning with explicit UTF-8 succeeded. A guessed element-summary ID was absent; an ID from existing own public-picks cache then located an existing summary. Neither miss caused a network request.

## Observed schema and cache facts

| Input | Cache write time (UTC) | Observed shape/count |
|---|---|---|
| FPL bootstrap | `2026-10-21T02:25:43.217490Z` | 1,785,076 bytes; ten top-level keys; 668 elements, 20 teams, 38 events, eight chip definitions, 11 phases, 26 element-stat definitions, four element types. GW7 current+finished, GW8 next. |
| FPL fixtures | `2026-10-21T02:25:43.363686Z` | 380 fixtures; raw scores/stats and scheduling metadata present in addition to consumed routing/status/FDR fields. |
| Own manager metadata | `2026-10-21T02:25:43.882327Z` | 25 top-level keys; only name/manager names/overall rank read for page. |
| Own public GW7 picks | `2026-10-21T13:32:09.151631Z` | `active_chip`, `automatic_subs`, `entry_history`, `picks`. Each pick has element/type/captain/vice/multiplier/position. |
| Sample owned element summary | `2026-10-21T02:25:44.034590Z` | `fixtures` (31 future rows), `history` (seven current rows), `history_past` (five season rows). Full fixtures branch unused. |
| Own manager history | `2026-10-21T02:26:03.134754Z` | `current`, `past`, `chips`; extra rank-percentile/bank/scoring fields fetched beyond consumers. |
| Own transfers | `2026-10-21T02:26:47.476741Z` | Six rows; fields element_in/cost, element_out/cost, entry, event, time. Only purchase-side ID/cost/event/time read. |
| Personal league standings page 1 | `2026-10-21T02:26:02.341503Z` | Eight managers, `has_next=false`; `last_updated_data` present but ignored. |
| Event GW7 live | `2026-10-21T02:26:50.664217Z` | 668 elements; `id`, `stats`, `explain`, `modified`. `modified` and individual explain-stat detail ignored. |
| FFS line-ups | `2026-10-21T02:25:43.550639Z` | 220 extracted photo-ID→club entries. HTML/prose/time evidence is not retained. |
| FFS projections | `2026-10-21T02:26:05.222335Z` | 760 club-GW rows, value keys exactly `cs`, `g`, `opp`, `ven`. |
| Pinnacle matchups | `2026-10-21T02:26:05.815143Z` | 507 catalogue rows, 990,781 bytes. |
| Pinnacle markets | `2026-10-21T02:26:06.274220Z` | 1,344 rows, 499,413 bytes. |
| Pulselive resolver | `2026-10-21T02:25:47.019989Z` | First completed fixture yields season `841.0`, cast to `841`. |
| Committed projections output | Embedded generated time `2026-10-21T13:32:20Z` | GW8, 668 xP IDs. This is render/export time, not fresh-network proof. |
| Committed price memory | Dates `2026-10-14` through `2026-10-21` | 668 players, eight date entries. |

Raw schemas inspected: bootstrap element/team/event keys; player-summary fixtures/current/past row keys; public-pick and entry-history keys; event-live stats/explain keys; transfer row keys; classic-standing result keys. Used-field inventory distinguishes these actual source schemas from derived Python/JavaScript payload names.

### Pulselive page-cap evidence

All inspected stat URLs used `compSeasons=841&comps=1&pageSize=100&page={0..3}&altIds=true`.

| Stat | Cached pages | Row counts | Provider-reported numPages |
|---|---|---|---|
| `big_chance_created` | 0, 1 | 100, 53 | 2 |
| `total_att_assist` | 0, 1, 2, 3 | 100, 100, 100, 17 | 4 |
| `total_scoring_att` | 0, 1, 2, 3 | 100, 100, 100, 32 | 4 |
| `ontarget_scoring_att` | 0, 1, 2 | 100, 100, 36 | 3 |
| `big_chance_missed` | 0, 1 | 100, 30 | 2 |
| `won_contest` | 0, 1, 2 | 100, 100, 97 | 3 |
| `touches` | 0, 1, 2, 3 | 100, 100, 100, 100 | **5** |

`pulse.ranked(..., pages=4)` uses `range(pages)`; no caller increases this. The fifth touches page is therefore omitted. `attach()` marks the source healthy if any FPL player matches any merged stat; it does not assert all pages/stats/players arrived. This finding is verified against local provider response metadata, not inferred solely from an arbitrary code cap.

### Requested cadence versus observed commits

Workflow cron is `0 */3 * * *`. Eighteen generated commits in the available local `origin/main` log cover 17 intervals: min **2.31h**, median **4.74h**, max **8.86h**. Latest inspected generated commits are `0538c72` at `2026-10-21T11:12:41Z` and `7a8649d` at `03:23:28Z`, gap **7.82h**. This is publication-history evidence, not an exhaustive scheduled-run result or a fresh origin query.

## Verification boundary

No fresh HTTP request, dashboard build, browser session or regression suite was run by this source-audit subtask. That avoids turning old-cache observations into a false claim of live provider availability and avoids the build's `price_history.json` side effect. Existing HANDOFF test/browser/build statements are historical evidence only. The parent research task owns live endpoint research and final stage checks.

Validation completed: `git diff --check` returned exit 0. Local assertions passed for 900-second default TTL, 30-day finished-live TTL, FFS URL, seven Pulselive statistics, 668/20/38 bootstrap counts, touches page 3's 100 rows/5-page metadata, and committed GW8/668-player/13:32:20Z feed shape. Both new reports passed relative-link existence, trailing-whitespace and balanced-code-fence checks. No complete test/build/browser result is implied by these document/invariant checks.
