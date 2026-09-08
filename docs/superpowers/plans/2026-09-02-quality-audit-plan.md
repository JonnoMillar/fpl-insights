# Quality audit plan — fpl-insights dashboard

Audited 2026-09-02 against the live page (https://fpl-insights-jm.vercel.app, build "01 Sep 2026, 23:19 UTC", GW2 done, GW3 next) and the code at commit `3fca503`. Every finding below was verified either by reading the computation or by measuring the live DOM/page. Line numbers refer to that commit.

This is a plan for an executing model. Each item gives: **where**, **what is wrong**, **why it matters**, **fix**. Work each group top-down; severity falls as you go. Do not silently "improve" anything not listed. After any Python change, rebuild with `python cli.py dashboard --artifact` and confirm the numbers quoted in the "evidence" lines change in the expected direction.

Conventions used below: `expected_points` = the history-backed model in `analysis.py`; `candidate_score`/`case_score` = the bootstrap-only model in `transfers.py`; "5-GW total" = `case_score` output (points summed over `TRANSFER_HORIZON_WEEKS`, plus the form/xGI nudge).

---

## 1. Logic flaws

### L1. The chip planner cannot see double or blank gameweeks, which is the whole point of chips
- **Where:** `ffs.projections` (ffs.py:37) keys the schedule as one entry per `(club, gw)`; `analysis.expected_points` (analysis.py:886, line 913 `proj.get((club, gw))`), `transfers.candidate_score` (transfers.py:187), `ffs.ticker` (ffs.py:86), `ticker._rows_for` (ticker.py:112) all assume exactly one fixture per club per gameweek.
- **What is wrong:** A double gameweek (two fixtures) is scored as one; a blank is silently skipped rather than scored as zero in the ticker. Triple Captain, Bench Boost and Free Hit are, in practice, DGW/BGW chips. The planner therefore picks "GW3, Isak, Strong" for Triple Captain — a single-fixture week no experienced manager would use it in — and will keep doing so all season because it cannot represent the weeks that matter.
- **Why it matters:** Every chip recommendation on the page is structurally unable to find the right answer once DGWs appear (typically GW24–37, after cup rounds).
- **Fix:**
  1. Build the schedule from FPL's own `ctx.fixtures` (already loaded in `analysis.Ctx.load`, analysis.py:62). For each `(club, gw)` collect a *list* of fixtures (`team_h`/`team_a`, `event`). Blank = empty list, double = two.
  2. Keep FFS `proj` only as a source of per-fixture rates. Match each FPL fixture to the FFS entry by `(club, gw, opp)`; where a second fixture in the same gw has no FFS row, derive its `g`/`cs` from `team_attack_baselines` (attack) and the opponent's conceded baseline (see L6 for the opponent xG).
  3. Change `expected_points` and `candidate_score` to loop over that list and sum per-fixture totals (appearance points once per fixture, clean sheet once per fixture — FPL scores each fixture separately). Return `fixtures: [...]` so the UI can print "2 fixtures".
  4. In `ffs.ticker`/`ticker.fixture_ticker` emit an explicit blank cell for a missing gw so columns stay aligned (see B8).
  5. In `chips.triple_captain`/`bench_boost`/`free_hit` no change is needed once the scorers sum fixtures; add "(DGW)" to the card text when `len(fixtures) > 1`.

### L2. The transfer engine values a bench slot exactly like an XI slot, so its top suggestions are bench-fodder swaps
- **Where:** `transfers.suggest` (transfers.py:985–987, `gain = s["total"] - here["total"]`), `pair_suggestions` (851), `verdict_board` Sell (533).
- **Evidence (live page):** Suggested transfers, ranked by gain: Hughes→Slater +17.49, Konsa→Egan +16.64, Van Hecke→De Cuyper +11.43, Diop→Mendy +8.87; top pairing Van Hecke→Egan + Hughes→Lewis-Potter "+32.97"; Sell column is Konsa, Van Hecke, Diop, Maguire. Hughes and Dubravka are not predicted to start (`candidate_score` gives them 15 minutes), so *anyone* who starts projects ~15–25 points more over five weeks. Those points are never scored because a bench player only plays via auto-sub.
- **Why it matters:** The page's headline transfer advice is "upgrade your 4.5m bench midfielder", which is worth roughly nothing, while the genuine XI decisions are pushed off the list.
- **Fix:** Score a transfer by the change in the squad's best-XI projection, not the change in the individual. Concretely, in `suggest`, `pair_suggestions` and `verdict_board`:
  1. Build `own_pool` = the 15 owned players as squadbuilder rows `{id,pos,club,price,value}` using the same scorer as the candidates.
  2. `base_xi = squadbuilder.best_xi(own_pool, budget=1e9)["value"]`.
  3. For each candidate swap, replace the outgoing row with the incoming row and recompute `best_xi`; `gain = new_xi_value - base_xi`.
  4. Add a small bench allowance so a bench upgrade is not exactly zero: `gain += 0.15 * (s_in - s_out)` (0.15 ≈ auto-sub probability). Make the 0.15 a named constant with a comment.
  5. Fifteen `best_xi` calls per outgoing player × ~100 candidates is cheap (it is a 15-row pool); if it is slow, pre-filter candidates to the top 30 per position by raw score before step 3.
  6. `chips.bench_boost` should keep using raw individual gain (the bench does play that week) — pass a flag rather than sharing the new path.

### L3. Free Hit is optimised with the wrong budget (about 17m short)
- **Where:** `chips.points_team` (chips.py:126) `budget = sum(r.price for r in xi_reports)`, then `squadbuilder.best_xi` (squadbuilder.py:148–182) subtracts a cheapest legal bench from that budget before filling the XI.
- **What is wrong:** A Free Hit spends the *whole squad's sell value* (15 players), of which a cheapest bench is dead weight. Passing the XI's price (~83m here) and then subtracting ~17m of bench leaves ~66m for the ideal XI — less than the manager's own XI costs. The "ideal" is thus artificially weak, the FH gap is understated, and the chosen week is distorted.
- **Evidence:** Free Hit card says "Best possible XI projects 66.7 pts against your 57.1" for GW9, while the unbudgeted best XI for GW3 is 80.1.
- **Fix:** `dashboard.build` already computes `total_sell` (dashboard.py:4901) and `bank_m`. Thread `budget=total_sell + bank_m` into `chips.free_hit` → `points_team`, and delete line 126. Also label the card: "against your XI's 57.1 that week" (the 57.1 is the manager's GW9 projection, not the hero's 63.4 for GW3, and the card does not say so).

### L4. "What the best managers own" measures last week's luck, not elite judgement
- **Where:** `elite.compare` (elite.py:100–165) with `depth=100` (cli.py:288 default), reading the global standings after GW2.
- **Evidence:** B.Fernandes 100.0% elite / 48.4% overall (he scored 23 in GW2; the top 100 after two weeks are precisely the people who captained him). Haaland 19.0% elite vs 70.4% overall, printed as a −51.4 "edge" in the "you own these; the elite largely do not" table. After two gameweeks the top 100 is a survivorship sample of lucky captaincy, and the card is actively advising against the most-owned premium in the game.
- **Why it matters:** This is the one card that claims to be a signal against the crowd, and until roughly GW10 it is noise dressed as insight; with n=100 even the exact mode carries ±10 percentage points of binomial noise, yet it prints one decimal place.
- **Fix:**
  1. Change the reference set: read pages 1–5 of the overall league (250 managers), fetch `fplapi.entry_history` for each (250 cached calls), keep managers whose most recent `past` season `rank` ≤ 100,000. If fewer than 50 qualify, return `None` and render nothing but a one-line note ("Elite ownership needs ~10 gameweeks before the top of the table means anything").
  2. Rename the label to "proven managers (top-100k finish last season, top-250 now)" and pass `n` so `elite_card` prints ±MOE in both modes (`margin_of_error(ok)` is already there — apply it always, not only when `mode == "sampled"`, elite.py:120).
  3. Round elite/edge to whole percentage points; drop rows where `|edge| < 2 × moe`.
  4. Keep the "against" table only when the filter in (1) produced ≥ 50 managers.

### L5. Appearance and clean-sheet points are computed from expected minutes with a hard 60-minute cliff, which mis-prices anyone with a doubt or rotation risk
- **Where:** `analysis.expected_points` lines 921–925 (`minutes = start_prob*avg + (1-start_prob)*8`), 972 (`defence = cs_prob * CS_POINTS * (1.0 if share > 0.65 else 0.0)`), 973 (`appearance = 2.0*share if minutes >= 60 else 1.0*share`); same shape in `transfers.candidate_score` 258–259; `expected_bonus` 820/823 also branch on `minutes >= 60`.
- **What is wrong:** These are expectations of a *mixture* (starts vs. cameo), and the code applies the 60-minute rule to the mixture's mean instead of to each branch. Worked example: `chance_of_playing_next_round = 75` and FFS predicted → `start_prob = 0.92 × 0.75 = 0.69`, `minutes = 0.69×90 + 0.31×8 = 64.6` → full CS and 2×0.72 appearance. At 65% chance: `start_prob = 0.60`, `minutes = 56.4`, `share = 0.63` → **zero** clean-sheet points and 0.63 appearance points. A 10-point fitness flag moves a 3.9-point defender by ~1.8 points. The true expectation is smooth: `0.60 × (2 + cs×4)`.
- **Fix:** Replace with branch-wise expectations in both scorers:
  ```
  p_start = start_prob
  p_cameo = (1 - start_prob) * CAMEO_PROB   # CAMEO_PROB = 0.5 for pred False / None, 0.2 otherwise
  p60 = p_start * (1.0 if avg_start_minutes >= 60 else avg_start_minutes / 60)
  appearance = p_start * 2 + p_cameo * 1
  defence = p60 * cs_prob * CS_POINTS[pos]
  share (for goals/assists) = (p_start * avg_start_minutes + p_cameo * 8) / 90   # unchanged in spirit
  ```
  and pass `p60` into `expected_bonus` instead of `minutes`, using it to weight the 6-vs-3 appearance BPS and the CS BPS. Delete the `share > 0.65` and `minutes >= 60` tests.

### L6. The points model omits four scoring events, and the omissions are biased, not random
- **Where:** `analysis.expected_points` 965–979; `transfers.candidate_score` 256–274; `components.EP_PARTS` (components.py:30).
- **Missing:** goals-conceded penalty (−1 per 2 conceded, GKP/DEF), saves (+1 per 3, GKP), yellow cards (−1), penalty saves (+5). 2026/27 scoring keeps all four.
- **Why it matters:** (a) Defenders on sides expected to concede are over-projected; the CS term already rewards good fixtures, so omitting GC makes the model *less* fixture-sensitive than reality for defenders. (b) Every keeper is under-projected, budget keepers most: a 4.0–4.5m keeper facing ~5 shots on target a game earns ~1 point a match in saves. Evidence: Raya projects 4.0 with a 37% clean sheet and no saves term at all; the Buy/Best-XI logic can never surface the classic budget-keeper value because the component that creates it is not modelled.
- **Fix (both scorers, then add segments to `EP_PARTS` and to `playerview.js` `parts`):**
  - Opponent expected goals `opp_xg`: from the market (`market_total - team_xg`) when priced, else the opponent's FFS `g` for that fixture (`proj[(opp, gw)]["g"]`), else `league_avg_xg`.
  - `E[GC penalty] = -Σ_k Poisson(k; opp_xg) * floor(k/2)` for GKP/DEF, times `p60`.
  - `saves90` = `el["saves"] / minutes * 90` from bootstrap (field exists), shrunk toward the positional prior in `candidate_score`; `E[save pts] = (saves90 * share * (opp_xg / baseline_opp_xg)) / 3` (rate scales with how much the opponent attacks; clamp multiplier 0.6–1.6).
  - `yellow90` from `el["yellow_cards"]`; `E[yc] = -yellow90 * share`.
  - Penalty saves: `0.05 * p60 * 5` for keepers only if you want it; it is small — acceptable to skip if noted.

### L7. The `case_score` "nudge" is unshrunk, penalises defenders, and skews the wildcard's formation
- **Where:** `transfers.player_case_factors` (transfers.py:329–349), `case_score` (373–375), `EXPECTED_CASE_WEIGHT = 3.0` (320); the same nudge is added to the wildcard pool in `chips.build_pool` (chips.py:60–104, `case_weighted=True`) and `chips.wildcard` (361+).
- **What is wrong:**
  1. `expected_goal_involvements_per_90` is the raw bootstrap per-90. A 63-minute cameo with one big chance (Hinshelwood, 2.04 xGI/90 on the live page) earns `3.0 × 2.04 = +6.1` points of nudge — far more than `MIN_CASE_GAIN = 0.75` — bypassing all the shrinkage `candidate_score` applies.
  2. For DEF/GKP the term is `xGI/90 − xGC/90`. xGC/90 is 1.0–1.8 for every defender, so every defender carries a −3 to −5 point penalty that midfielders and forwards do not. Within-position comparisons partly cancel this, but `squadbuilder.best_squad` compares across positions to choose a formation, so the Wildcard systematically under-buys defenders. Evidence: the proposed rebuild sells Isak and Mbeumo (1st and 3rd in the league for xG) for Foden/Palmer/Wissa, while "xGI 12.3 → 12.3 +0.0".
  3. Clean-sheet probability is already inside the points total; subtracting xGC double-counts defence.
- **Fix:** In `player_case_factors` compute `expected` as `_shrink(xgi90, minutes, prior_xgi90)` using the same `PRIOR_MINUTES` and a price-fitted prior (add `xgi90` to `RATE_KEYS`), drop the xGC term entirely, and cap the nudge at ±2.0 points. In `chips.build_pool` set `case_weighted=False` for the wildcard as well (the windowed points total already carries fixtures and rates; a cross-position nudge has no place in a formation choice).

### L8. The captaincy verdict is decided by radar polygon area, and the axes double-count
- **Where:** `captaincy._polygon_area` (captaincy.py:151–166), `matrix` line 247 `top = max(out, key=lambda c: c["area"])`, and the card text at dashboard.py:4178 ("The largest shaded shape … is the safest or highest-ceiling pick").
- **What is wrong:**
  1. Radar area depends on the order of axes and on the axis scales, not on expected points. On the live page Isak has the highest projection (8.1) but Haaland is declared "top" (area 11,834 vs 6,224) because Haaland's fixture multiplier is 1.61 vs 1.21 and he is on penalties. The chart contradicts the projection the whole page is built on.
  2. `goal_threat` (= `exp_goals`) already contains `fixture_mult` and `share`; the Fixture and Start-certainty axes count those inputs a second time.
  3. Responsibilities is a fixed 65/20/15. A penalty taker's real edge is ~0.08 xG per match (about 0.1 pens/match × 0.78 conversion); on this chart it is worth as much as the whole goal-threat axis. Szoboszlai reaches 100 on it with 0.43 expected goals.
  4. "Form (last 4)" is the one input the expert framework tells you to ignore in favour of forward-looking numbers.
- **Fix:**
  - Make `top` the highest `ep_total` (they are already sorted that way); remove `_polygon_area`, `is_top_area`, and the sentence at 4178. Say instead "Ranked by projected points; the shape shows *why*."
  - Replace the Form axis with **Effective ownership in your league**: `(owners + captains) / n` from `analysis.league_ownership` (the data is already on the page), scale 0–200%. Note in the "i" text that global EO is not public.
  - Replace Goal threat with the player's own **xGI per 90** (blended, no fixture) so Fixture stays a separate axis and nothing is counted twice.
  - Responsibilities: keep the duty labels for the callout but score the axis as `pens 50 / corners 25 / free kicks 25` and cap at 100; it stops dominating.

### L9. Triple Captain confidence is always "Strong" by construction
- **Where:** `chips.triple_captain` (chips.py:275–297) passes every other `(player, gw)` value (≈ 11 × 8 = 88) to `confidence` (27–44), which compares the best against their *mean*.
- **What is wrong:** The maximum of 88 values is always ≥ 20% above their mean. The pill carries no information. Same pattern, milder, for Free Hit and Bench Boost (best week vs. mean of the others).
- **Fix:** Compare best against the *second-best* candidate: for TC, the best other `(player, gw)`; for FH/BB, the best other week. Re-tune thresholds to that comparison (`STRONG = 0.15`, `WATCH = 0.05`) and rename `confidence()`'s second argument to `runner_up`.

### L10. Buy/Sell/Keep/Avoid: "Avoid" fires on any fractional gap, and "Buy" is not actually reachable
- **Where:** `transfers.verdict_board` — Avoid at line 594 (`os_["total"] <= s["total"]`), Buy ceiling at 463–465 and 549–561.
- **Evidence:** "Avoid Ajayi — Egan is 4.0m and projects +0.2"; "Avoid Elanga — Stach projects +0.8". A 0.2-point gap over five weeks is nothing, and the crowd buying a player is itself a signal (price rises). The Buy ceiling is "most expensive man you own in that position + bank", so Buy is "any forward under Haaland's price", reachable only by selling Haaland.
- **Fix:** Avoid: require `os_["total"] - s["total"] >= MIN_CASE_GAIN` and sort by that margin, not by `net`. Buy: a candidate is reachable only if some owned player in that position with `price + bank >= candidate price` projects at least `SELL_MARGIN` less than the candidate; put that player's name in the note ("sell Van Hecke"). After L2 the Sell column will stop being the bench.

### L11. Thin-sample handling is too short and the two projection models disagree with each other
- **Where:** `THIN_SAMPLE_MINUTES = 270` (analysis.py:490, used at 960–963); `PRIOR_MINUTES = 400` (transfers.py:40). The pitch, hero tile, Best XI and captaincy use `expected_points`; every transfer card, verdict board, knee-jerk, watchlist and the wildcard use `candidate_score`/`case_score`.
- **What is wrong:** After three matches the history model ignores last season entirely; xG per 90 does not stabilise in 270 minutes (season-to-season correlation is moderate; ~10–15 matches is the usual stabilisation horizon). Isak's 8.1 projection rests on 1.16 expected goals in one match, from 180 minutes plus a third of a season's prior. Separately, the same player is scored by two different models on the same page, and the transfer cards print the *bootstrap* model's number for a player the pitch just scored with the *history* model.
- **Fix:** (1) Use a permanent blend `w = minutes / (minutes + 900)` between this season's rate and the prior (last season's per-90 where ≥ 900 minutes, else the price-fitted positional prior from `transfers.positional_priors`), in both scorers, and delete the 270 cliff. (2) Make `candidate_score` the single scorer: give it an optional `history` argument; when `dashboard.build` scores the owned 15 it passes the history it already fetched. Then the number on the pitch, in the transfer card and in the verdict board is the same number.

### L12. The fixture rating ranks teams, not fixtures
- **Where:** `ticker.rating` (ticker.py:98–102) scores `xg` and `cs` on absolute anchors (`XG_LOW/HIGH`, `CS_LOW/HIGH`).
- **Evidence:** "Worst fixture runs" = HUL 1.5, SUN 2.2, COV 2.2 — the three weakest sides, whoever they play. The docstring admits it. But the card is headed "how good the fixture is to own a player *for*", and for a Hull defender the question is whether Hull's next six are good *for Hull*.
- **Fix:** Rate relative to the club's own baseline, the same isolation `expected_points` already does: `attack = clamp01((xg / baseline_xg[club] - 0.6) / 0.8)`, `defence = clamp01((cs / club_mean_cs - 0.6) / 0.8)` where `club_mean_cs` is the club's mean FFS `cs` across the season. Keep the absolute version as the "Our model" column in `fixture_run_summary` and call it "expected output", and use the relative one for the ticker cells and the pills.

### L13. Market expected goals are quantised to the nearest 0.25 line
- **Where:** `odds._fair_line` (odds.py) picks the single total/handicap/team-goals line closest to even money.
- **Why it matters:** Pinnacle lines step by 0.25, so the "market xG" can be off by up to ±0.125 per side before the handicap error is added, and it feeds `fixture_mult` directly.
- **Fix:** Interpolate: take the two lines bracketing even money and solve linearly for the line at which P(over) = 0.5 after `devig`. For team goals, do the same on the team ladder. Ten lines of code; leave the docstring's Poisson caveat as is.

### L14. "XI xGI" in the league table is a season sum, so it measures minutes
- **Where:** `analysis.squad_underlying` (analysis.py:1113), rendered in `dashboard.league_table` (4275) as a meter.
- **Evidence:** every rival sits between 11.1 and 12.6; the meter bars are visually identical.
- **Fix:** Show `Σ xGI per 90 × min(1, minutes/180)` per XI, or better, "projected next-GW points of their XI" using the shared scorer (L11), which is the number that actually says whether a rival's score will repeat.

---

## 2. Bugs

### B1. Free-transfer count is wrong after a hit and after a Wildcard/Free Hit
- **Where:** `analysis.free_transfers` (analysis.py:533–539).
- **Trace:** `banked = 1`; GW2 with 2 transfers (one hit): `min(5, 1 − 2 + 1) = 0`, then `max(0, 0) = 0` → GW3 reports **0** free transfers; the real answer is 1 (a hit never reduces next week's allowance). A Wildcard week with 11 transfers → `1 − 11 + 1` → 0; the 2026/27 rule is that banked transfers are *retained* through Wildcard and Free Hit and the weekly +1 still accrues.
- **Consequence:** `pair_hit` (dashboard.py:4822) and every "Both transfers are free" / "Not worth −4" verdict on the pairing cards is wrong for any manager who has taken a hit or played a chip.
- **Fix:**
  ```python
  chips_by_gw = {c["event"]: c["name"] for c in history.get("chips", [])}
  for gw in range(2, next_gw):
      used_n = used.get(gw, 0)
      if chips_by_gw.get(gw) in ("wildcard", "freehit"):
          used_n = 0
      banked = min(FREE_TRANSFER_CAP, max(0, banked - used_n) + 1)
  ```

### B2. Pairing cards print "+-13.73" and call a net-loss pair "free"
- **Where:** `components.pairing_cards` (components.py:462 `'+{gain:.2f}'` on each leg, 490 on the total; verdict at 470–480).
- **Evidence:** Live card "Reaches the knee-jerk pick": Isak → Akpom shows `+-13.73`; the pair totals +1.40 and is captioned in green "Both transfers are free".
- **Fix:** Use `{gain:+.2f}` in both places. Verdict order: if `p["gain"] <= 0` → `pr-no` "Not worth it, even free"; else existing logic.

### B3. Knee-jerk card labels a 5-GW total as "Next GW"
- **Where:** `transfers.kneejerk` returns `"ep": score["total"]` (transfers.py:779) — the `case_score` 5-GW total; `dashboard.kneejerk_card` prints it under "Next GW" (dashboard.py:4085). Live: "B.Fernandes … Next GW 56.3".
- **Fix:** Return both `score["next_gw_total"]` (already in the dict) and `score["total"]`; print "Next GW 9.2 · next 5 GW 56.3". The `rival` comparison at 4044 can stay on the 5-GW figure but must say so.

### B4. Suggested-transfer copy contradicts the numbers on the cards
- **Where:** `dashboard.build` note at 5026–5029: "ranked by projected gain for gameweek {next_gw} … One gameweek of data underneath"; `components.transfer_cards` 402 prints `+17.49 projected points` with no horizon.
- **Fix:** "Ranked by projected gain over the next 5 gameweeks (plus a small form/xGI nudge). Selling price is current price." Change the small label to "over 5 GW". Delete the "One gameweek of data" sentence (it is GW3).

### B5. The match-log sparkline in the player dialog is invisible
- **Where:** `playerview.js:197` `sparkline(pts, 'var(--lilac)')`; `--lilac` is defined nowhere in `dashboard.py` CSS. Verified live: computed `stroke: none` on the path.
- **Fix:** Use `var(--p60)` (or add `--lilac:#953bff` to `:root`).

### B6. Accent green is used as text on white, against the stylesheet's own rule
- **Where:** dashboard.py CSS — `.tf-gain` (1646), `.pr-gain` (1457), `.pr-yes` (1460), `.tf-elite` (1654), `.oyou` (840), `.mkt-cs,.mkt-xg` (931). The `:root` comment at line 164 says "#01fc7a on white is 1.35:1 … anything that lands on text uses the darker cut." Verified live: all six compute to `rgb(1,252,122)`.
- **Fix:** `color: var(--good-ink)` on all six. `.kj-score .num` (1272) is green on the ink card and is fine.

### B7. Thirteen clickable player cards do nothing
- **Where:** `template_pitch` (dashboard.py:3236) and `_mini_shirt_card` (3685, used by the Wildcard and Bench Boost pitches) emit `data-player`, `role="button"`, `tabindex="0"`, but `player_dialog` only carries payloads for the owned 15. Verified live: 13 elements (3 template, 8 wildcard, 2 bench boost) with ids not in `player-data`; `playerview.js` `open()` silently returns.
- **Fix:** Either (preferred) extend `player_payload` with a bootstrap-only variant (no match log; season tiles, next fixtures, set pieces) and emit it for every id that appears on any pitch; or drop `role`, `tabindex` and `data-player` from those cards and remove the pointer cursor.

### B8. Fixture-outlook columns will shift left at the first blank gameweek
- **Where:** `ffs.ticker` (ffs.py:93) advances `gw` past a missing entry without emitting a row; `ticker.fixture_ticker` (ticker.py:189–192) writes headers `GW{start}..GW{start+weeks-1}` and drops cells under them positionally.
- **Fix:** In `ffs.ticker` return `{"gw": gw, "blank": True}` for a missing key; in `_rows_for` give it `score=0` and in `fixture_ticker` render a grey "—" cell. Also `ffs.summary` and `chips._xi_stats` should treat blank as 0 rather than skipping.

### B9. Scatter axis ticks are not round numbers
- **Where:** `scatter.js` `draw()` computes ticks as quarters/fifths of the padded domain (`2.21, 1.65, 1.10, 0.55`; `3.3, 5.9, 8.5…`).
- **Fix:** Reuse the `niceTicks` approach from `leaguechart.js` (step from `{1,2,2.5,5}×10^k`), and pad the domain to the tick, not the other way round.

### B10. Average start minutes includes substitute minutes
- **Where:** `analysis.expected_points` 922 `r.minutes / r.starts`.
- **Fix:** `sum(h["minutes"] for h in r.history if h["starts"]) / r.starts`.

### B11. DefCon expectation double-counts minutes
- **Where:** analysis.py:974–975 `hit_rate * DEFCON_POINTS * share`; `hit_rate` is already per appearance (which includes short appearances).
- **Fix:** multiply by `p_start` (from L5), not `share`.

---

## 3. Information design

### I1. The Planning tab is sixteen full-width cards with no hierarchy
- **Where:** `dashboard.render` (dashboard.py:4580–4595).
- **What is wrong:** Odds tiles, best XI, knee-jerk, verdict board, six transfer cards, five pairing cards, radar, chip planner, two collapsed rebuilds, fixture table, fixture runs, six leader columns, price watch, scatter, three elite tables — in one scroll, all open. There is no ten-second read.
- **Fix:** Add a "This week" strip at the top of Planning: four tiles — *Captain* (top of `cap_matrix`, with EP), *One transfer* (top of `suggest` after L2, with 5-GW gain), *Chip?* ("No chip this week" unless the planner's chosen week == `next_gw`), *Roll or use?* (see O6). Below it, wrap the rest in four `<details>` groups, collapsed by default: **Transfers** (verdict board, suggested, pairings, knee-jerk), **Chips** (planner + rebuilds), **Fixtures & market** (odds, outlook, runs), **Market & data** (price watch, leaders, scatter, elite). Remember the open state in `localStorage` keyed by group.

### I2. Numbers without units read as expected points
- **Where:** verdict board (`vb-ep`, dashboard.py:4117), watchlist "5-week 55.0" (ok), pairing totals, knee-jerk (B3).
- **Fix:** Suffix every 5-GW figure with a muted "/5 GW" span; every single-week figure with "GW3". Apply in `verdict_board_card`, `pairing_cards`, `transfer_cards`, `differential_watchlist_card`.

### I3. "Who owns whom" is 45 identical doughnuts in a carousel
- **Where:** `dashboard.ownership_carousel` (2527). Live: first three cards are all 8/8 100%.
- **Fix:** Replace with one horizontal bar list (same component as "Scoring against you", `_rivals_list`): player, owner count bar out of n, captain count as a darker segment, "you" rows in the mine tone, top 15 by owners, "show all" toggle for the rest. Delete `donut` usage here (keep it for the line-up card).

### I4. The findings grid repeats the same players across eight cards
- **Where:** `findings_section` (2901). Attacking returns, Goals-vs-xG, Big chances/chances, Big chances missed are four cards about the same six attackers.
- **Fix:** Merge into one **Attack** card: per player one row — returns (G+A), xG dumbbell, big chances created/missed as small pills. Keep Line-ups, DefCon, Set pieces, Price movement, Fixture swings. Also: "Big chances missed" currently carries the *good* (green) tone (analysis.py:702) — a viewer reads "missed" + green as a contradiction; use the neutral tone and let the note explain.

### I5. Hover-only information on 120 fixture cells
- **Where:** `ticker.fixture_ticker` cells carry xG/CS/source only in `title` (ticker.py:160–162); `rating_pill` likewise. Verified: 120 title-only cells. No tooltip on touch.
- **Fix:** Tap/click a cell to swap its content between rating and "1.62 xG · 24% CS" (toggle a class on the table, one listener in `ticker.js`), and add a one-line legend under the table.

### I6. The premium-fixture gradient reads as a rendering glitch
- **Where:** `.fx-premium` (dashboard.py:1377) — a green→grey→blue diagonal gradient on cells ≥ 9.0. Live: MCI "COV 9.4", CHE "HUL 9.4" look like a broken image.
- **Fix:** Solid `#0b5f4a` with white text and a small ★ before the score. (See colour section for the token.)

### I7. Chip planner: four single-number cards hide the series that produced them
- **Where:** `chip_planner_card` (3857).
- **Fix (the "more like the captaincy matrix" ask):** Draw one small SVG timeline GW3→GW19: three thin rows (Free Hit gap, Bench Boost bench points, Triple Captain best EP per week) with the chosen week marked and hover showing the number; chip cards become the legend. `free_hit` already returns `by_gw`; extend `bench_boost` and `triple_captain` to return per-week series.

### I8. Verdict board as a quadrant chart
- **Where:** `verdict_board_card` (4100).
- **Fix:** Above the four lists, a scatter of every scored player: x = crowd movement (`transfers_in_event − transfers_out_event`, symlog), y = 5-GW projection, owned players ringed; the four quadrants *are* Buy/Sell/Keep/Avoid. Reuse `scatter.js` machinery (pass a second dataset and axis config). The lists stay as the accessible fallback.

### I9. Interaction mismatches found in testing
- Radar: clicking a *shape* highlights but does not pin; only the legend pins (captaincy.js `toggle` is legend-only). Add the same click handler to `.radar-area`.
- Scatter: a pinned dot cannot be un-pinned (scatter.js `pinnedG` is cleared only on redraw). Click on empty SVG → `pinnedG = null; unpick()`.
- "Gameweek 2" in the pitch view toggle (dashboard.py:4557) is not a view; it swaps one figure on the Overview pitch. Move it into the `statsel` group as a fourth stat ("this GW").
- The "i" buttons (32 of them) hide the units and caveats that change how a number should be read (I2 fixes the worst of it). Keep the buttons, but never hide a *unit*.

### I10. Mobile
- The predicted-points column stacks under the pitch (verified at 390px); acceptable. The fixture table needs its own horizontal scroll hint (add "scroll →" affordance via `mask-image` fade on `.scroll`). The hero verdict and tiles work.

---

## 4. Opportunities (concrete, all from free public sources)

### O1. Effective ownership, league-level now, elite-level once L4 lands
- Mini-league EO per player = `(owners + captains) / n` from `analysis.league_ownership`. Add it to the captaincy radar (L8), to "Scoring against you" (rank by `points × EO`, which is the actual rank damage), and as an "EO" column in the template pitch.
- Once L4 gives a proven-manager sample, compute EO there too and show "captained by 61% of proven managers".

### O2. Real expected minutes (xMins) on every card
- Compute `xmins = p_start × avg_start_minutes + p_cameo × avg_sub_minutes` (L5) and print it on the Pick-team card and in the squad table as a column, with the three FPL Review-style bands (≥ 80 nailed, 60–80 rotation risk, < 60 avoid). It is the single number experts check first and the page currently only shows a green/red dot.

### O3. Opponent xGC last six, split home/away
- Team defensive strength per match is derivable with 20 calls: each club's first-choice keeper's `element-summary` history carries `expected_goals_conceded` per fixture. Build `team_xgc[(club, home)]` over the last six and use it (a) as the opponent-strength input for L6, (b) as a "opponent leaks" pill on transfer targets.

### O4. Model validation card
- Each build, append `{gw, player_id, projected, source}` for all scored players to a `projections_history.json` (same pattern as `price_history.json`, dashboard.py:4657). From GW4 render a small "How good is the model" card: MAE and bias vs actual, vs FPL's `ep_next`, split by position. Every constant in this codebase is annotated "starting guess, not fitted" — this is the mechanism that lets you fit them.

### O5. Rank-aware swing vs each rival
- For each rival: `Σ EP(players they start that you do not) − Σ EP(players you start that they do not)` ± captain doubling, next GW. Render as a signed bar per rival on the Mini-league tab ("expected swing"). Everything needed is already loaded (`by_name`, `eps`, shared scorer after L11). No other tool shows this for a private league.

### O6. "Roll or use" for the five-transfer bank
- If the best XI-gain transfer (L2) is below `MIN_CASE_GAIN` and `free_ts < 5`, say "Roll — you bank a 2nd free transfer for GW4". If `free_ts == 5`, say "Use one — a 6th cannot be banked". Two lines in `dashboard.build`, one tile in I1.

### O7. Price-change exposure
- `price_watch` already has per-player projections. Add one number to the hero "In the bank" tile: expected squad-value change in the next 24h (`Σ ±0.1 × likelihood/100` over owned players), so "0.0m bank" gets its forward-looking half.

### O8. Team-news timing
- Print "Built N hours before the GW3 deadline" in the top bar using `events[next_gw]["deadline_time"]`, so a reader knows how stale the predicted line-ups may be (FFS re-tunes after pressers).

---

## 5. Colour and visual identity

### What is working, keep it
- **Purple as ink** (`#37003c`) on white cards with a warm-ish grey ground, and the hero as a flat purple block with one green rule (`.hero`, dashboard.py:324) — this is the one thing on the page that reads "FPL" without a logo.
- **Green as fill only** (`#01fc7a`): the hero's top rule, the tile tone, the tab focus ring, the green "1" pills on set pieces. Right instinct; B6 lists where it leaked into type.
- **Mono numerals** (IBM Plex Mono, tabular) against Archivo headings — the tabular columns are the page's most distinctive texture.
- **Delta chips** (wedge + wash) as the one loud component.
- **Pitch greens** `#0e7a3c / #0a6733` — correct saturation, not the neon FPL app green.
- **Fixture ramp** rose→teal (`#a4133c, #f4845f, #eae7ec, #7ac9a0, #17876a`) — better than traffic lights, and CVD-safe because the number is printed.

### What is not working
- **No system for the other hues.** Leaders use six accents (`#953bff, #00b3d6, #e6007e, #00a35c, #1b5ce0, #e07b00`), EP segments use six (`#953bff, #00b3d6, #00a35c, #87668a, #e07b00, #d81b8c`), scatter uses three, the radar three (ink, green, amber). None of these agree on what a hue *means*, so colour never carries information across cards.
- **Violet `#953bff` for "you"** competes with the purple ink and is also "goals" in the EP bar.
- **Amber has two jobs**: warn (`#e07b00`) and radar candidate 3 and DefCon segment.
- **The ground `#f5f2f5`** is a purple-tinted grey; with white cards it is the generic SaaS ground the code comments are trying to avoid.
- **`.fx-premium` gradient** is off-palette (I6).

### Proposed palette — "floodlit night", building on purple + green
Keep every existing token name; add the ones marked *new*. Values are sRGB hex; contrast ratios are against the surface named.

| Token | Value | Role and where to apply |
|---|---|---|
| `--ink` | `#37003c` | unchanged: headings, table text, hero, name bars |
| `--ground` *change* | `#f4f1ea` | page background: warm chalk instead of purple-grey; cards stay `#ffffff`. Reads as programme paper, separates cards without shadow |
| `--surface-variant` *change* | `#f8f5ef` | inner panels (`.oi`, `.pr-card`, `.tile` on light) |
| `--accent` | `#01fc7a` | unchanged, fills only: hero rule, tile-good bg at 9%, set-piece "1" pill, `.bxi-bar` mine |
| `--good-ink` | `#046b39` | all green *text* (B6); 6.9:1 on white |
| `--mine` *new* | `#e6007e` | everything that is *you*: scatter `--mark-mine`, `.me` row in league table (wash `#fff0f7`), `tpl-mine` outline, `.epkey` for your XI, mini-pitch "IN" tag becomes `--mine` outline instead of green |
| `--mine-ink` *new* | `#a3005a` | text version, 7.2:1 on white |
| `--market` *new* | `#00708a` | anything priced by the bookmaker: `.fx-mkt` dot, "market" source labels, odds tiles' top border, `mkt-cs/mkt-xg` (replaces green text) |
| `--market-wash` *new* | `#e3f4f8` | odds tile background |
| `--rival` *new* | `#1b5ce0` | other managers: league chart default line hue base, rival bars in "Scoring against you" (replaces `--bad` red, which currently makes every rival return look like an error) |
| `--attention` *new* | `#ffb000` | the sodium-amber the CSS comment describes and never used: knee-jerk card left rule, `tile-warn`, "Needs a look", TC chosen week on the chip timeline. Ink `#7a4b00`, wash `#fff4d6` |
| `--warn` | `#e07b00` → *retire* | fold into `--attention`; keep `--warn-ink #9c5400` for "borderline" pills |
| `--bad` / `--bad-ink` | `#e60023` / `#c0001d` | unchanged, but only for *errors and losses*: price falls, not-predicted, Sell |
| `--premium` *new* | `#0b5f4a` | replaces the `.fx-premium` gradient; white text, ★ glyph |
| `--bar` *change* | `#1e0021` | top bar goes to the deepest purple (`--p120`) so the hero (`#37003c`) sits *lighter* than the chrome above it |

**EP stacked bar** (`components.EP_PARTS` and `playerview.js` `parts`), ordered as the scoring order a manager thinks in:
goals `#37003c` (ink) · assists `#7d5980` (p70) · clean sheet `#0b5f4a` (premium teal) · saves/GC *new* `#00708a` (market teal, hatched via `repeating-linear-gradient` for negative) · appearance `#d7ccd8` (p20) · DefCon `#ffb000` · bonus `#e6007e`. One family (purples) for the "who scores" terms, three role hues for the rest. Check adjacent ΔE ≥ 8 for deuteranopia as the current comment does; the purple/teal/amber/magenta set passes.

**Radar candidates** (`--radar-c0/1/2`): `#37003c`, `#e6007e`, `#ffb000` — ink, mine-magenta, attention-amber. Drop the green fill; green means "good" everywhere else on the page and a green shape reads as the recommended one.

**Leaders card accents** (`dashboard.leader_groups`): stop giving each stat its own hue. Use `--ink` for the four attacking cards, `--premium` for xGC, `--attention` for DefCon.

**Scatter**: `--mark-mkt #bcae9e` (warm neutral on the chalk ground), `--mark-mine #e6007e`, `--mark-outlier #37003c` with a hollow ring.

**Hero tiles**: keep white-on-purple; `tile-good` uses `rgb(1 252 122 / 9%)` as now; `tile-warn` switches to `rgb(255 176 0 / 14%)` with `#ffd166` numerals (7.4:1 on `#37003c`).

Apply in this order: tokens in `:root` (dashboard.py:166–189) → B6 text fixes → EP_PARTS → radar vars (712–714) → scatter vars (615) → leaders (3611–3630) → `.fx-premium` (1377) → `.rv-track i` and `.me` row → mini-pitch IN tag. Then rebuild and screenshot the Planning tab against the current build to confirm no green text remains (grep the built HTML for `color:#01fc7a` and `color:var(--accent)` inside text-bearing rules).
