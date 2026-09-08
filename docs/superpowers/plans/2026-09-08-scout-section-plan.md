# Scout section plan — position comparison labs

Written 2026-09-08 against commit `714503e` (plus uncommitted work in `analysis.py`, `dashboard.py`, `fplapi.py`, `playerview.js` — **commit or stash that before starting**). Live state: GW3 current, GW2 the last finished week, 653 players in bootstrap, 214 defenders.

Source: `defenders-section-spec.md`. That spec was written against an assumed React/TypeScript repo with a charting library. This plan is the same design translated onto what is actually here, with the places I disagree with the spec called out and decided in section 2 rather than left as a difference to discover mid-build.

The section is built **position-generic from the first commit**. Defenders ships first; midfielders, forwards and keepers are then a config entry each, not a second implementation. That is the single most important decision in this plan and it is why the module is called `scout`, not `defenders`.

Conventions below match the 2026-09-02 audit plan: each item gives **where**, **what**, **why**, **fix**, **done when**. Line numbers refer to `714503e`.

---

## 1. What the codebase actually is (answering spec §0)

Verified by reading, not assumed:

| Spec §0 asks | Reality |
|---|---|
| Charting library | **None.** All SVG is hand-rolled — server-side in `components.py` (sparkline, meter, gap_chart, defcon_bars), or browser-drawn from a JSON island in `scatter.js`, `captaincy.js`, `ticker.js`, `leaguechart.js`. "Do not introduce a second charting library" resolves to *do not introduce a first one*. |
| Component conventions | Python functions returning HTML strings. `<section class="card">` → `.card-head` (h2 + `components.info_btn()` + a hidden one-line `.sub`) → `.card-body`. Chapters are `<div class="chapter">`; the rail nav (`dashboard.py:2280`) builds itself from whichever chapters the open tab has. |
| Data fetching | Python stdlib only, zero dependencies. `fplapi.py` over `urllib`, disk-cached by URL hash, `DEFAULT_TTL = 900`. Everything is baked into one self-contained `dashboard.html` (1.77 MB raw, 0.97 MB gzipped) as data URIs so it works offline. |
| Styling | Inline `<style>` from the `CSS` constant in `dashboard.py:166+`. FPL purple ramp `--p2`…`--p120`, `--ink:#37003c`, single accent `--accent:#01fc7a`. Archivo (variable width axis) + IBM Plex Mono on every figure. Light theme only. |

**Data availability** — better than the spec assumes:

- **Bootstrap, one request**, already carries ~80% of `DefenderRow` for all 214 defenders: `starts`, `minutes`, `defensive_contribution_per_90`, `expected_goal_involvements_per_90`, `expected_goals_conceded_per_90`, `bps`, `bonus`, `yellow_cards`, `now_cost`, `selected_by_percent`, `transfers_in_event`/`transfers_out_event`, `corners_and_indirect_freekicks_order`, `penalties_order`, `status`, `chance_of_playing_next_round`.
- **`matches[]` costs N requests, not 214.** `fplapi.event_live(gw)` returns per-gameweek stats for all ~626 players in one call, including `defensive_contribution`, `minutes`, `starts`, `clean_sheets`, `goals_conceded`, cards, `bonus`, `bps`, `expected_goals_conceded`, `total_points`, and the fixture id via `explain[].fixture`. Already used at `dashboard.py:3932`. **Do not use `element_summary` per player** — that is 214 requests for the same data.
- **Fixture horizon is free.** `ffs.projections()` returns `{(club_code, gw): {cs, g, opp, ven}}` for all 20 clubs × 38 weeks. `ffs.ticker(proj, club, start_gw, n)` already shapes it, blanks included.
- **`defconDifficulty` does not exist in any source.** Derivable proxy: for a club's fixture in gw, look up the *opponent's* row `proj[(opp, gw)]["g"]` — the opponent's expected goals is a proxy for defensive workload. Ships labelled as a model, not a measured stat (see §2.6).
- **`role: CB | FB | WB` does not exist in FPL data at all.** Cut (see §2.3).

Measured payload cost (real bootstrap, players with ≥1 start, per-match arrays included):

| | now (3 GWs) | season end (38 GWs) |
|---|---|---|
| Defenders only | 36 KB | 280 KB |
| All four positions | 95 KB | 730 KB |

730 KB of JSON on a 1.77 MB page is a 41% raw increase but compresses far better than the base64 images that dominate today's payload. Acceptable, with the gates in §2.10.

---

## 2. Where this plan overrides the spec

The spec's analysis is good — §3.1 (DEFCON is a threshold, not a rate), §3.2 (two fixture metrics), §3.4 (no composite, archetypes instead) are all correct and non-obvious. These are the places its *implementation* instructions are wrong for this repo or wrong on their own terms.

### 2.1 `defconHitRate` cannot be the headline metric yet — phase it in
Spec §3.1 puts `defconHitRate` on the hero x-axis, on tiles and on rankings. Two gameweeks are finished. Across 83 defenders with 2+ starts the metric takes exactly three values: 0, 0.5, 1.0. The hero scatter is three vertical stripes, and it looks authoritative while saying nothing.

**Decision:** the hero x-axis is driven by a sample gate. Below `SAMPLE_GATE` starts across the filtered pool's median, x is `defconPer90` with the hard reference line at 10 that §3.1 already asks for; above it, x is `defconHitRate`. Hit rate is *always* rendered with its n attached ("3 of 5"), never as a bare percentage — `components.defcon_bars` (components.py:164) already sets this precedent. Where last season exists, blend it the way the rest of the repo does (`transfers._blend`, `BLEND_MINUTES=900`); `analysis.DEFCON_MIN_MINUTES = 180` is already this codebase's own guard for exactly this problem and the section reuses it rather than inventing a second threshold.

The archetype rule ("top third of the filtered pool") gets the same gate — at n=2 it assigns near-randomly, so below the gate archetype badges are suppressed rather than shown wrong.

### 2.2 Archetype zones cannot be shaded on the scatter canvas
Spec §4.2 wants "three archetype zones shaded and labelled directly on the plot canvas". The three archetypes are driven by `defconHitRate` (x), `xgiPer90` (y) and `solidityPercentile` — and solidity is the *bubble size*, not a position. There is no region of the x/y plane that means "clean sheet archetype", so a shaded zone claiming otherwise would be a drawn lie.

**Decision:** keep the faint median crosshairs (§4.2 asks for them and they are honest), drop the shaded zones, and carry archetypes as **badges** on the heatmap row and in the hover readout, where all three metrics are actually present. Quadrant labels sit on the crosshairs as text, describing what the quadrant means in x and y only.

### 2.3 Cut `role: CB | FB | WB`
Not in FPL's API at any level. Pulselive has `info.positionInfo` on its per-player endpoint, but `pulse.py` only uses ranked-stat endpoints today, so this is 214 new requests to add one filter. It is the least load-bearing of the five filters in §4.1.

**Decision:** cut from v1. The freed filter slot goes to **minutes per start** (hook risk), which §3.3 correctly identifies as a distinct question and which nothing else on the page exposes. Revisit only if the filter is actually missed.

### 2.4 Okabe-Ito is scoped to this section, not to the dashboard
Spec §1 mandates Okabe-Ito everywhere and bans red/green for opposite meanings. Most of the page already complies for real reasons: the fixture ticker is deliberately rose → warm neutral → teal *against* red-amber-green with the rating printed in every cell (ticker.py:58-62); difficulty pills always carry opponent and number because the FPL green is 1.35:1 on white (README); the scatter separates squad from market by size, ring and label (dashboard.py:2847-2850); delta chips carry a CSS triangle so direction survives greyscale (dashboard.py:268-275).

The genuine conflict is `--good:#01fc7a` / `--bad:#e60023`, and `--accent` being the FPL green. A global palette rewrite contradicts a standing project constraint (FPL purple as ink, FPL green as the single accent).

**Decision:** Okabe-Ito, blue→orange and viridis apply **inside the scout section**. The shell keeps FPL colours. Existing red/green usages are all redundantly encoded and stay.

### 2.5 Two diverging scales, one meaning each
Spec §1 says all diverging scales are blue→orange. But fixture difficulty already has a shipped, CVD-safe rose→teal scale used in the ticker, the player dialog (`playerview.js` `csTone`/`xgTone`) and the pitch pills. Colouring the same concept two ways on one page is worse than having two scales.

**Decision:** fixture difficulty keeps **rose → teal** inside the scout section too, so a fixture reads identically wherever it appears. **Blue → orange** is reserved for the genuinely new concepts with no existing scale: the percentile heatmap (§4.3) and the z-score bars (§5.1). Two scales, each with exactly one meaning.

### 2.6 The DEFCON difficulty row is a model and must say so
The opponent-xG proxy (§1) is untestable right now — three gameweeks is not enough to correlate opponent xG against realised contribution counts.

**Decision:** ship it, label the row "modelled" in the legend and the `.sub`, and add a revisit task at ~GW10 to check the correlation against real data and either keep, recalibrate, or pull the row. Do not present it in the same visual weight as the clean-sheet row, which is a real bookmaker/model number.

### 2.7 Z-score bars need the raw value beside them
Spec §5.1: seven metrics × six players = 42 bars, all in standard deviations. A z-score alone is not a number most people read at a glance, and the pool sd over 83 players with n=2 matches each is a wide, unstable estimate.

**Decision:** keep the component — §8 is right that it beats a radar — but print the **raw value** at the end of each bar alongside the z position, clamp the axis at ±3 with outliers labelled, and suppress metrics that fail the sample gate rather than drawing noise. Inverted metrics (`xgcPer90`, `cardsPer90`) carry an explicit "(inverted — right is better)" label as §5.1 requires.

### 2.8 Keep the existing xP as a column
Spec §8 bans a composite rating. Agreed, and §3.4's reasoning is right. But this repo has exactly one expected-points model (`transfers.candidate_score`; see the shared-scorer constraint) and it is on every other card on the page. Its absence here would be conspicuous, and readers will assume it was hidden.

**Decision:** xP appears as one column in the heatmap and one line in the player card. It is never the default sort and never an axis. No second scorer is introduced.

### 2.9 Keep the one-line `.sub`
Spec §1 says "no paragraph copy in the UI". The house style is a single hidden line under each card head, revealed by `info_btn()`. That is a line, not a paragraph, and it is how every other card on the page explains itself.

**Decision:** keep it. Honour the spirit — no prose blocks in the body, status and attributes as badges and icons.

### 2.10 Not in the spec: build position-generic, and render lazily
Defenders, midfielders, forwards and keepers are four instances of one section. Everything except the metric set, the DEFCON threshold (already `analysis.DEFCON_THRESHOLD = {"DEF": 10, "MID": 12, "FWD": 12}`, analysis.py:25), the archetype definitions and the axis defaults is position-agnostic.

Two forward-looking constraints that must be designed in now, not retrofitted:

- **Keepers break the hero.** A keeper's xGI is structurally ~0 — which is exactly why `analysis.market_scatter_points` already excludes them (analysis.py:1176). A keeper lab needs different axes (saves per 90 against xGC per 90 — shot-stopping over-performance). So **hero axes are config, not hardcoded**.
- **Page weight.** Emit per-match arrays only for players passing the pool gate, round hard (2 dp on rates, 0 dp on counts), and render the charts on first tab activation rather than at load. The page already times out under screenshot tooling; do not make that worse on the initial paint.

---

## 3. Architecture

New files:

```
scout.py            data layer + section renderer, position-generic
scout.js            browser rendering: scatter, heatmap, z-bars, split ticker, match strip
tests/test_scout.py stdlib unittest — the first tests in this repo
```

Touched: `fplapi.py` (season history helper), `dashboard.py` (tab, panel, script wiring, lazy-render hook), `analysis.py` (only if a derivation genuinely belongs there).

The per-position config is the whole of the difference between the four labs:

```python
POSITIONS = {
    "DEF": PositionConfig(
        label="Defenders",
        hero=("defcon_hit_rate", "xgi90"),      # (x, y); x falls back per §2.1
        size="solidity_pct",
        metrics=[...],                          # heatmap columns, in order
        zbars=[...],                            # §5.1 band order
        archetypes={
            "volume":     "defcon_hit_rate",
            "cleanSheet": "solidity_pct",
            "attacking":  "xgi90",
        },
    ),
    ...
}
```

`scout.section(ctx, pos, ...)` renders one lab. `dashboard.render` calls it once for `DEF` now; adding `MID` later is a `POSITIONS` entry plus a line in the panel.

**Zero new dependencies.** stdlib Python, vanilla JS, hand-rolled SVG.

---

## 4. Phases

Each phase ships something usable and stops for review, as spec §7 asks. Phase 0 is new — it front-loads the reusable half so phases 3–5 are the only per-position work.

### P0 — Shared pool data layer
**Where:** new `scout.py`; `fplapi.py`.

**What:** the position-agnostic foundation. Nothing renders yet.

**Fix:**
1. `fplapi.season_live(upto_gw, ttl=...)` → `{player_id: [per-gw stat dicts]}`, one `event_live` call per finished gameweek, each disk-cached as today. Finished weeks never change, so they take a long TTL; only the current week takes `DEFAULT_TTL`. Attach the opponent and venue by joining `explain[].fixture` against `ctx.fixtures`.
2. `scout.pool_rows(ctx, pos, live, proj, filters)` → the Python equivalent of `DefenderRow`, one dict per player passing the gate. Everything in §1's bootstrap list comes straight off the element; `matches[]` comes from `live`.
3. Derivations, per spec §2.1, **computed against the currently filtered pool and recomputed on filter change** (so they live in JS as well as Python — Python computes the initial render, `scout.js` recomputes on filter):
   - `start_rate = starts / team_matches_since_first_start`
   - `solidity_pct` = percentile rank of `xgc90`, **inverted** (100 = concedes least)
   - percentile rank per metric; `z` per metric against the filtered pool's positional mean
   - `archetypes: list[str]` — top third on each archetype's driving metric, **suppressed below the sample gate** (§2.1)
   - `defcon_hit_rate` = share of *starts* (not appearances) with `defensive_contribution >= DEFCON_THRESHOLD[pos]`
4. Fixture rows: `cs_difficulty` from `ffs.ticker`'s `cs` (inverted to 1..5), `defcon_difficulty` from the opponent's `g` in the same gw (§2.6), both carrying the numeral for the cell.
5. `tests/test_scout.py` — stdlib `unittest`, run with `python -m unittest discover -s tests`. **No pytest**: zero-dependency is a project value. Cover `defcon_hit_rate` (denominator is starts, not appearances; zero-start player does not divide by zero), the inverted `solidity_pct` (a low-xGC player scores *high*), percentile ranks against a filtered subset vs the full pool, z-scores at zero variance, the sample gate, blank gameweeks in the fixture horizon, and a player whose first start is mid-season (`team_matches_since_first_start`).

**Done when:** `python -m unittest discover -s tests` passes, and a scratch script prints a defender pool with plausible hit rates, solidity percentiles and a 6-GW two-row fixture horizon.

### P1 — Colour and accessibility primitives
**Where:** `scout.py` constants; a scoped CSS block in `dashboard.py`'s `CSS`.

**What:** everything downstream imports these. Scoped under `.scoutsec` so nothing leaks into the FPL-coloured shell (§2.4).

**Fix:**
1. Okabe-Ito constants: `#0072B2` blue, `#E69F00` orange, `#56B4E9` sky, `#F0E442` yellow, `#009E73` bluish green, `#D55E00` vermillion, `#CC79A7` reddish purple.
2. Blue→orange diverging ramp for the heatmap and z-bars (§2.5). White→blue for good, white→orange for bad, per §4.3.
3. Rose→teal reused from `ticker.py` for both fixture rows (§2.5) — import the existing steps, do not re-declare them.
4. Percentile→radius mapper, 5px to 22px, **by percentile not raw value** (§4.2 is right that raw xGC spans 0.8–1.6 and is invisible as area). Must resolve into at least four visually distinct tiers.
5. Greyscale check helper — a build-time assertion that any two adjacent scale steps differ in relative luminance by a stated minimum. This is what makes §1's acceptance test ("render in greyscale, still readable") mechanical rather than a promise.

**Done when:** a scratch page renders every scale, and the greyscale helper passes on all of them.

### P2 — Section shell and lazy render
**Where:** `dashboard.py` render/build; `scout.js`.

**Fix:**
1. Fourth tab `Scout` → `<div class="panel" id="p-scout" hidden>`. The rail (dashboard.py:2280) picks up its chapters automatically.
2. Emit one shared data island per position, `<script type="application/json" class="scout-data" data-pos="DEF">`.
3. Fire a `panel:shown` event from the tab handler (dashboard.py:2259-2274) and have `scout.js` do its first draw on that event, not on `DOMContentLoaded` (§2.10).
4. Wire `SCOUT_JS` into both the standalone and `--artifact` script lists (dashboard.py:5184 and 5196 — **both**, they are separate literals and it is easy to update one).

**Done when:** the tab exists, is empty, and `python cli.py dashboard --artifact` still builds with no console errors.

### P3 — Level 1: pool view
**Where:** `scout.js`, extending `scatter.js` rather than duplicating it.

`scatter.js` already has: switchable axes, `niceStep`/`niceTicks` round-number ticks, position filtering, hover/click readout, and CVD-separated marks. Extract the shared layout core; do not write a second scatter.

**Fix:**
1. **Filter bar** (§4.1): sticky, one row, five controls — price range, minimum start rate (default 0.6), minutes per start (replacing role, §2.3), team, fixture horizon (default 6). Every change recomputes percentiles and z-scores against the new pool.
2. **Hero scatter** (§4.2): x per §2.1's gate, y `xgi90`, bubble size `solidity_pct` via the P1 mapper with the legend "Defensive solidity (bigger = concedes less)". Solid fill above the minutes threshold, hollow outline below. Neutral fill by default with an optional Okabe-Ito categorical toggle. Faint median crosshairs with text quadrant labels; **no shaded archetype zones** (§2.2). Labels on top-quadrant players with collision avoidance, others on hover.
3. **Percentile heatmap** (§4.3): one row per player, one column per metric, cells shaded white→blue (good) / white→orange (bad), sortable on every column, archetype badges on the row (§2.2), numbers right-aligned with `font-variant-numeric: tabular-nums`.
4. **Bi-directional sync**: hovering a row highlights the bubble and vice versa; brushing a scatter region filters the table.

**Done when:** greyscale screenshot of the scatter is readable and size resolves into ≥4 tiers; sort, filter and brush all recompute percentiles; nothing else is on the view (§4.3 "nothing else on this view").

### P4 — Level 2: shortlist compare
**Fix:**
1. Selection from Level 1, max six.
2. **Z-score bars** (§5.1) in the specified band order, centre line at the filtered pool's positional mean, shared sd scale, every metric oriented so right is good, inverted ones labelled — plus the raw value, the ±3 clamp and the sample gate from §2.7. Identity carried by consistent vertical position and a text label, never colour alone.
3. **Split fixture ticker** (§5.2) directly below in the same player order: two thin rows per player, rose→teal ramp *and* the numeral in each cell, the DEFCON row marked modelled (§2.6).

**Done when:** two players with the same mean but different spread are visibly different; greyscale check passes on both components.

### P5 — Level 3: player card
The existing player dialog (`playerview.js`, payload at dashboard.py:4133) is already ~70% of this: identity, stat rows, a match log carrying `dc` per gameweek, and a 6-GW fixture strip. **Extend it; do not build a second dialog.**

**Fix:**
1. **Identity strip** (§6.1): name, team, price, badges. Set-piece icons already exist (`components.ICONS`), as do `duty_badges` (components.py:338). Add ownership and price-change momentum as icons with tooltips. No prose.
2. **Metric tiles** (§6.2): five tiles, each a large number over a thin **bullet bar** showing percentile position with a tick at the positional median. `components.meter` (dashboard.py:137) is the starting point.
3. **Per-match strip** (§6.3) — build this before the sparklines; it is the best idea in the spec and the main justification for the whole section. One narrow column per gameweek, height = points, markers for started/subbed/benched/unavailable, DEFCON hit or miss, clean sheet, card. **Markers distinguish by shape and position; colour is supplementary only.** Hover reveals opponent, minutes, contribution count. Acceptance: two players with identical `defconPer90` and different consistency must look visibly different.
4. **Rolling sparklines** (§6.4): three small lines, last ten gameweeks — DEFCON count, xGI, xGC. Trend only, no axes or legend. `components.sparkline` (components.py:656) exists.

**Done when:** the acceptance test in step 3 is demonstrated with two real players from the current pool.

---

## 5. After defenders

Adding midfielders is intended to be: a `POSITIONS` entry (threshold 12, archetypes volume/creator/finisher, hero `defcon_hit_rate` × `xgi90`), a line in the panel, and nothing else. Forwards likewise. If it turns out to need more than that, P0–P2 did not generalise and that is the bug to fix, rather than forking the section.

Keepers are the one that will not fit the mould and should be planned separately when reached — different hero axes (saves/90 × xGC/90), no DEFCON threshold at all, and a much smaller pool.

## 6. Open items

- **GW10 revisit:** validate the opponent-xG proxy for `defcon_difficulty` against realised contribution counts; keep, recalibrate or pull the row (§2.6).
- **Sample gate crossover:** the hero x-axis swaps from `defconPer90` to `defconHitRate` once the gate passes (§2.1). Note the crossover in the `.sub` so the chart does not silently change meaning between builds.
- **Ticker migration:** whether the rest of the page's rose→teal should become blue→orange is a separate decision, deliberately not taken here (§2.5).
- `role: CB|FB|WB` stays cut unless the filter is actually missed (§2.3).
