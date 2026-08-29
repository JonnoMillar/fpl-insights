# Chip Suggester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recommend a target gameweek for each of the four FPL chips (Free
Hit, Triple Captain, Bench Boost, Wildcard), scoped to the gameweeks left in
the current half (GW1-19 or GW20-38), with a plain-language reason and a
confidence read - plus a standalone "points team" comparison and, for Bench
Boost, transfer suggestions that would improve the target week.

**Architecture:** A shared windowed expected-points layer (one version using
the manager's own already-fetched squad data, one using the bootstrap-only
scorer `transfers.py` already has, for scoring the wider player pool without
per-candidate API calls) feeds a constrained squad optimizer
(`squadbuilder.py`, generic - no EP-specific knowledge) and four
chip-specific recommenders (`chips.py`) that each consume the shared layer
differently. Rendered as a new card on the dashboard's Planning tab.

**Tech Stack:** Python 3.9+, stdlib only (no new dependencies). Follows the
existing codebase's module-per-concern layout (`analysis.py`,
`transfers.py`, `ticker.py`, ... ) and its established verification style:
there is no pytest suite in this repository, so every task's "test" step is
a standalone Python script run via the shell (`python - <<'EOF' ... EOF`),
matching how `start_probability` and the market-staleness fix were both
verified earlier in the session that produced this plan. Nothing under a
`tests/` directory is created - that would be a new convention this
codebase doesn't use anywhere else.

**Spec:** `docs/superpowers/specs/2026-08-29-chip-suggester-design.md`

## Global Constraints

- No new dependencies (no ILP/optimization library) - the optimizer is a
  greedy fill + capped hill-climb, per the spec.
- No per-candidate API calls when scoring the full ~600-player pool - use
  `transfers.candidate_score` (bootstrap-only), never
  `analysis.expected_points` (needs per-player match history), for anyone
  outside the manager's own 15.
- Hill-climb iteration cap: 50 swaps (correctness guard against a
  non-converging flip-flop, not a performance measure - this runs
  unattended on the existing 3-hourly build).
- 3-per-club limit and real FPL formations (1 GKP, 3-5 DEF, 2-5 MID, 1-3
  FWD, 10 outfield) apply to every squad the optimizer produces.
- Sell price uses FPL's real rule (purchase price + half of any rise,
  rounded down; full price if it has fallen), sourced from the manager's
  public `/transfers/` history plus a GW1 `value` fallback - never a flat
  £100m or raw `now_cost` for the manager's own squad value.
- Confidence thresholds (≥20% strong, 5-20% worth watching, <5% flexible)
  are a starting guess per the spec - implement as named constants so
  they're trivial to retune later, not magic numbers scattered through the
  code.

---

## Task 1: Fix the market-staleness bug in `transfers.candidate_score`

This is a prerequisite, not new functionality. `candidate_score` has the
exact same bug `analysis.expected_points` had before this session's earlier
fix: it trusts `market` (`mk`) unconditionally whenever it exists, but
`market` only ever prices the *imminent* gameweek. Every later task in this
plan calls `candidate_score` across a multi-gameweek window, which would
silently repeat gameweek+1's market line for every week after it if this
isn't fixed first - the same failure mode the earlier `analysis.py` fix
addressed, in the sibling function that was never patched because nothing
called it across multiple gameweeks until now.

**Files:**
- Modify: `transfers.py:82-141` (inside `candidate_score`)

**Interfaces:**
- Consumes: nothing new
- Produces: `candidate_score(el, ctx, proj, gw, market, baselines, priors=None, league_avg=1.45)` - same signature, corrected behavior. Callers unaffected.

- [ ] **Step 1: Read the current implementation to confirm line numbers**

Run: read `transfers.py` from `candidate_score`'s definition to its `return` statement. Confirm the two unguarded uses of `mk`:
```python
team_xg = mk["xg"] if mk else float(fixture.get("g") or league_avg)
...
cs_prob = (mk["cs"] / 100.0) if mk else float(fixture.get("cs") or 0) / 100.0
...
"opponent": (mk["opp"] if mk else fixture.get("opp")),
"home": (mk["home"] if mk else (fixture.get("ven") or "H").upper() == "H"),
```

- [ ] **Step 2: Apply the fix**

Replace:
```python
    baseline = (baselines or {}).get(el["team"], league_avg)
    team_xg = mk["xg"] if mk else float(fixture.get("g") or league_avg)
    mult = max(0.5, min(2.0, team_xg / baseline)) if baseline else 1.0
    cs_prob = (mk["cs"] / 100.0) if mk else float(fixture.get("cs") or 0) / 100.0
```
with:
```python
    baseline = (baselines or {}).get(el["team"], league_avg)
    # `market` only ever prices the imminent round - trusting it for a gw
    # it doesn't actually describe would silently repeat that round's line
    # for every later gameweek. Same guard analysis.expected_points uses.
    mk_matches = bool(mk and fixture and mk.get("opp") == fixture.get("opp"))
    if mk_matches:
        team_xg = mk["xg"]
    elif fixture:
        team_xg = float(fixture.get("g") or league_avg)
    elif mk:
        team_xg = mk["xg"]
    else:
        team_xg = league_avg
    mult = max(0.5, min(2.0, team_xg / baseline)) if baseline else 1.0
    if mk_matches:
        cs_prob = mk["cs"] / 100.0
    elif fixture:
        cs_prob = float(fixture.get("cs") or 0) / 100.0
    elif mk:
        cs_prob = mk["cs"] / 100.0
    else:
        cs_prob = 0.0
```

And replace the return dict's opponent/home lines:
```python
        "opponent": (mk["opp"] if mk else fixture.get("opp")),
        "home": (mk["home"] if mk else (fixture.get("ven") or "H").upper() == "H"),
```
with:
```python
        "opponent": fixture.get("opp") if fixture else mk["opp"],
        "home": (fixture.get("ven") or "H").upper() == "H" if fixture else mk["home"],
```

- [ ] **Step 3: Verify against live data**

Run:
```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import analysis, fplapi, ffs, odds, transfers

ctx = analysis.Ctx.load(ttl=3600)
haaland_id = next(pid for pid, el in ctx.players.items() if el["web_name"] == "Haaland")
el = ctx.players[haaland_id]

proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
next_gw = min(38, (ctx.current_event() or 1) + 1)

seen_opponents = set()
for off in range(5):
    gw = next_gw + off
    s = transfers.candidate_score(el, ctx, proj, gw, market, baselines)
    assert s is not None, f"GW{gw}: no score returned"
    seen_opponents.add(s["opponent"])
    print(f"GW{gw}: opp={s['opponent']} total={s['total']:.2f}")

assert len(seen_opponents) > 1, (
    "BUG STILL PRESENT: every gameweek in the window returned the same "
    f"opponent ({seen_opponents}) - candidate_score is still reusing "
    "next week's market line for later weeks."
)
print("OK: opponent varies across the window as expected")
EOF
```
Expected: 5 distinct-looking opponents printed (barring genuine fixture congestion coincidences), and the final assertion passes without raising.

- [ ] **Step 4: Commit**

```bash
git add transfers.py
git commit -m "Fix the same market-staleness bug in transfers.candidate_score

candidate_score had the identical unguarded-market bug expected_points
was fixed for earlier this session, just never triggered because nothing
called it across multiple gameweeks until the chip suggester needs to."
```

---

## Task 2: `transfers.windowed_candidate_score`

**Files:**
- Modify: `transfers.py` (add function after `candidate_score`)

**Interfaces:**
- Consumes: `candidate_score(el, ctx, proj, gw, market, baselines, priors, league_avg)` from Task 1
- Produces: `windowed_candidate_score(el, ctx, proj, market, baselines, priors, start_gw, weeks=8)` returning `(total, per_gw)` where `per_gw` is `[(gw, score_dict), ...]` for whichever gameweeks scored - used by `squadbuilder`'s pool-building in Task 8.

- [ ] **Step 1: Write the function**

Add directly below `candidate_score` in `transfers.py`:
```python
def windowed_candidate_score(el, ctx, proj, market, baselines, priors,
                             start_gw, weeks=8):
    """A candidate's score summed across a run of gameweeks rather than
    one - the pool-scoring half of the same idea as analysis.windowed_ep,
    using the bootstrap-only scorer so it stays cheap across ~600
    candidates. A blank gameweek is skipped rather than scored as zero."""
    per_gw = []
    for gw in range(start_gw, start_gw + weeks):
        s = candidate_score(el, ctx, proj, gw, market, baselines, priors)
        if s:
            per_gw.append((gw, s))
    total = sum(s["total"] for _gw, s in per_gw)
    return total, per_gw
```

- [ ] **Step 2: Verify**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import analysis, fplapi, ffs, odds, transfers

ctx = analysis.Ctx.load(ttl=3600)
haaland_id = next(pid for pid, el in ctx.players.items() if el["web_name"] == "Haaland")
el = ctx.players[haaland_id]

proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
priors = transfers.positional_priors(ctx)
next_gw = min(38, (ctx.current_event() or 1) + 1)

total, per_gw = transfers.windowed_candidate_score(
    el, ctx, proj, market, baselines, priors, next_gw, weeks=6)
assert len(per_gw) <= 6
manual_total = sum(s["total"] for _gw, s in per_gw)
assert abs(total - manual_total) < 1e-9
print(f"windowed total over {len(per_gw)} weeks: {total:.2f}")
for gw, s in per_gw:
    print(f"  GW{gw}: {s['total']:.2f} vs {s['opponent']}")
EOF
```
Expected: no assertion errors, a printed breakdown with varying opponents/totals per week.

- [ ] **Step 3: Commit**

```bash
git add transfers.py
git commit -m "Add windowed_candidate_score for scoring the wider player pool across a run of gameweeks"
```

---

## Task 3: `analysis.windowed_ep`

**Files:**
- Modify: `analysis.py` (add function after `expected_points`)

**Interfaces:**
- Consumes: `expected_points(r, ctx, proj, gw, market, baselines, league_avg_xg)` (existing)
- Produces: `windowed_ep(r, ctx, proj, market, baselines, start_gw, weeks=8)` returning `(total, per_gw)`, `per_gw` a list of `(gw, ep_dict)` - used for the manager's own 15 players throughout `chips.py`.

- [ ] **Step 1: Write the function**

Add directly below `expected_points` in `analysis.py`:
```python
def windowed_ep(r, ctx, proj, market, baselines, start_gw, weeks=8):
    """A player's expected points summed across a run of gameweeks, not
    just one - the building block every chip recommendation is scored
    from. Returns (total, per_gw); per_gw is [(gw, ep_dict), ...] for
    whichever gameweeks actually had a projection, since a blank gameweek
    is skipped rather than scored as zero, matching expected_points
    itself."""
    per_gw = []
    for gw in range(start_gw, start_gw + weeks):
        ep = expected_points(r, ctx, proj, gw, market=market, baselines=baselines)
        if ep:
            per_gw.append((gw, ep))
    total = sum(ep["total"] for _gw, ep in per_gw)
    return total, per_gw
```

- [ ] **Step 2: Verify**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import analysis, fplapi, ffs, odds

ctx = analysis.Ctx.load(ttl=3600)
haaland_id = next(pid for pid, el in ctx.players.items() if el["web_name"] == "Haaland")
r = analysis.build_player(ctx, haaland_id, ttl=3600)

proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
next_gw = min(38, (ctx.current_event() or 1) + 1)

total, per_gw = analysis.windowed_ep(r, ctx, proj, market, baselines, next_gw, weeks=6)
manual_total = sum(ep["total"] for _gw, ep in per_gw)
assert abs(total - manual_total) < 1e-9
assert len(per_gw) <= 6
print(f"Haaland windowed EP over {len(per_gw)} weeks: {total:.2f}")
opponents = {ep["opponent"] for _gw, ep in per_gw}
assert len(opponents) > 1, "every week scored the same opponent - staleness regression"
print("distinct opponents across window:", opponents)
EOF
```
Expected: prints a windowed total, no assertion errors.

- [ ] **Step 3: Commit**

```bash
git add analysis.py
git commit -m "Add windowed_ep for summing a player's expected points across a run of gameweeks"
```

---

## Task 4: `analysis.chip_window`

**Files:**
- Modify: `analysis.py` (add function; a good spot is near `THIN_APPEARANCES`/`THIN_SAMPLE_MINUTES`, the module's other small "how much to look at" constants)

**Interfaces:**
- Consumes: nothing
- Produces: `chip_window(next_gw, cap=8)` returning `(start, weeks)` - `start == next_gw`, `weeks` is how many gameweeks are in scope. Every later chips.py function takes this as its search range via `range(start, start + weeks)`.

- [ ] **Step 1: Write the function**

```python
def chip_window(next_gw, cap=8):
    """The gameweek range chip suggestions search: the rest of the current
    half - GW1-19, or GW20-38 once that resets - capped, since a
    projection further out than that is mostly noise. Returns
    (start, weeks); the caller's own search range is
    range(start, start + weeks)."""
    end = 19 if next_gw <= 19 else 38
    weeks = min(cap, max(0, end - next_gw + 1))
    return next_gw, weeks
```

- [ ] **Step 2: Verify the GW19/20 boundary and end-of-season behavior**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import analysis

cases = [
    (1, (1, 8)),     # early season, capped at 8
    (12, (12, 8)),   # mid first half, still capped at 8
    (15, (15, 5)),   # 5 gameweeks left before the GW19 boundary
    (19, (19, 1)),   # last gameweek of the first half
    (20, (20, 8)),   # fresh chips, second half begins
    (35, (35, 4)),   # 4 gameweeks left before GW38
    (38, (38, 1)),   # final gameweek of the season
]
for next_gw, expected in cases:
    got = analysis.chip_window(next_gw)
    assert got == expected, f"chip_window({next_gw}) = {got}, expected {expected}"
    print(f"chip_window({next_gw}) = {got}  OK")
print("all boundary cases pass")
EOF
```
Expected: all seven cases print `OK`, no `AssertionError`.

- [ ] **Step 3: Commit**

```bash
git add analysis.py
git commit -m "Add chip_window for the GW19/38-bounded chip search range"
```

---

## Task 5: `analysis.squad_sell_value`

**Files:**
- Modify: `analysis.py` (add function near `squad_for`/`build_player`, the other manager/squad-level helpers)

**Interfaces:**
- Consumes: `fplapi.get_json`, `fplapi.BASE`, `fplapi.element_summary` (existing)
- Produces: `squad_sell_value(entry_id, ctx, squad_reports, ttl=fplapi.DEFAULT_TTL)` returning `(total, per_player)`, `per_player` a `{element_id: sell_price_in_millions}` dict. Used by `chips.py` (Task 8+) to compute the optimizer's real budget.

- [ ] **Step 1: Write the function**

```python
def squad_sell_value(entry_id, ctx, squad_reports, ttl=fplapi.DEFAULT_TTL):
    """Real FPL sell value per player: purchase price plus half of any
    rise since (rounded down), or the current price outright if it has
    fallen - never a flat guess, since this bounds every chip-suggester
    optimizer run below.

    Purchase price comes from the manager's public transfer history (the
    exact price paid, not an estimate), falling back to a player's own
    price at gameweek 1 for anyone held since the start and never
    transferred. Both are unauthenticated, public FPL endpoints.

    Returns (total, per_player); per_player is {element_id: sell_price},
    values in millions."""
    transfers_history = fplapi.get_json(
        f"{fplapi.BASE}/entry/{entry_id}/transfers/", ttl=ttl)
    bought_at = {}
    for t in transfers_history:
        pid = t["element_in"]
        prev = bought_at.get(pid)
        if prev is None or t["event"] > prev[0]:
            bought_at[pid] = (t["event"], t["element_in_cost"])

    per_player = {}
    for r in squad_reports:
        pid = r.element["id"]
        now = r.element["now_cost"]
        if pid in bought_at:
            buy = bought_at[pid][1]
        else:
            s = fplapi.element_summary(pid, ttl=ttl)
            first = next((h for h in s.get("history", []) if h["round"] == 1), None)
            buy = first["value"] if first else now
        sell = buy + (now - buy) // 2 if now > buy else now
        per_player[pid] = sell / 10.0
    return sum(per_player.values()), per_player
```

- [ ] **Step 2: Verify against the configured manager's real squad**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import json, analysis

cfg = json.loads(open("config.json").read())
entry_id = cfg["entry_id"]

ctx = analysis.Ctx.load(ttl=3600)
gw = ctx.last_event_with_picks()
picks = analysis.squad_for(entry_id, gw, ctx)
ids = [p["element"] for p in picks["picks"]]
reports = [analysis.build_player(ctx, pid, ttl=3600) for pid in ids]

total, per_player = analysis.squad_sell_value(entry_id, ctx, reports, ttl=3600)
assert len(per_player) == 15, f"expected 15 priced players, got {len(per_player)}"
now_cost_total = sum(r.price for r in reports)
print(f"sell value:  {total:.1f}m")
print(f"now_cost sum: {now_cost_total:.1f}m")
assert total <= now_cost_total + 1e-6, (
    "sell value should never exceed the sum of current prices - FPL never "
    "pays more than the current price on a sale")
for r in reports:
    sell = per_player[r.element["id"]]
    print(f"  {r.name:20s} now={r.price:5.1f}  sell={sell:5.1f}")
print("OK")
EOF
```
Expected: 15 rows printed, `sell <= now` for every player, the total-vs-now_cost assertion passes.

- [ ] **Step 3: Unit-test the sell-price rule directly with synthetic data**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import analysis

class FakeReport:
    def __init__(self, pid, now_cost):
        self.element = {"id": pid, "now_cost": now_cost}

# Monkeypatch the two data sources squad_sell_value reads, so this runs
# with no network access.
import fplapi

def fake_get_json(url, ttl=0):
    if "/transfers/" in url:
        return [
            # pid 1: bought at 50, now 65 -> risen 15 -> keep floor(15/2)=7 -> sell 57
            {"element_in": 1, "element_in_cost": 50, "event": 3},
            # pid 2: bought at 80, now 72 -> fallen -> sell at current, 72
            {"element_in": 2, "element_in_cost": 80, "event": 5},
            # pid 1 bought again later at 60 after being sold and rebought -
            # the LATEST purchase should win, not the first
            {"element_in": 1, "element_in_cost": 60, "event": 10},
        ]
    raise AssertionError(f"unexpected URL {url}")

def fake_element_summary(pid, ttl=0):
    # pid 3: never transferred, held since GW1 at value 55
    return {"history": [{"round": 1, "value": 55}]}

fplapi.get_json = fake_get_json
fplapi.element_summary = fake_element_summary

reports = [FakeReport(1, 68), FakeReport(2, 72), FakeReport(3, 60)]
total, per_player = analysis.squad_sell_value(999, None, reports, ttl=0)

# pid 1: latest buy 60, now 68, risen 8 -> +4 -> sell 64
assert per_player[1] == 6.4, per_player[1]
# pid 2: bought 80, now 72, fallen -> sell 72
assert per_player[2] == 7.2, per_player[2]
# pid 3: GW1 value 55, now 60, risen 5 -> +2 (floor) -> sell 57
assert per_player[3] == 5.7, per_player[3]
assert abs(total - (6.4 + 7.2 + 5.7)) < 1e-9

print("all synthetic sell-price cases pass")
EOF
```
Expected: prints the pass message, no `AssertionError`. This specifically exercises the "bought, sold, rebought" case (latest purchase wins) and the GW1-fallback case, neither of which the live check above is guaranteed to hit.

- [ ] **Step 4: Commit**

```bash
git add analysis.py
git commit -m "Add squad_sell_value: true FPL sell price from the public transfers endpoint"
```

---

## Task 6: `squadbuilder.py` - core selection helpers

**Files:**
- Create: `squadbuilder.py`

This module knows nothing about expected points, Poisson, or FPL data
shapes - it is a generic constrained-selection algorithm over plain dicts,
by design (see spec: "squadbuilder.py itself is a generic
constrained-selection algorithm with no knowledge of EP/Poisson/etc").
Every candidate is `{"id": int, "pos": "GKP"|"DEF"|"MID"|"FWD",
"club": str, "price": float, "value": float}`.

**Interfaces:**
- Consumes: nothing (pure functions over plain dicts)
- Produces (private, used by Task 7's public API):
  `FORMATIONS: list[(def, mid, fwd)]`,
  `CLUB_LIMIT: int`, `MAX_SWAPS: int`,
  `_by_position(pool) -> {pos: [candidate, ...]}`,
  `_greedy_fill(by_pos, quotas, budget, club_counts=None) -> list[candidate] | None`,
  `_cheapest_fill(by_pos, quotas) -> list[candidate] | None`,
  `_hill_climb(picks, by_pos, budget, other_club_counts=None) -> list[candidate]`

- [ ] **Step 1: Write the module header and constants**

```python
#!/usr/bin/env python3
"""
A constrained best-team builder: given a pool of candidates, find the
highest-value legal selection within budget.

Deliberately generic - this module has no idea what "value" means (points,
xG, anything with higher-is-better semantics works), and no idea where a
candidate came from. That split is what lets Free Hit and Wildcard share
one algorithm with two different objectives (chips.py builds the pool and
picks the mode; this module just solves the selection problem).

No ILP solver dependency: a greedy value-per-cost fill, then a
hill-climbing swap pass. Both are approximations, not a proof of
optimality, and callers should say so rather than imply a solved
optimization. The one constraint this is genuinely weak against is the
3-per-club limit - a hill-climb only ever tries one swap at a time, so an
early greedy pick that locks in 3 players from one club can block a better
combination only a 2-for-2 trade would reach. Worth a sanity check against
a club-limit-relaxed run before trusting a surprising answer.
"""

CLUB_LIMIT = 3

# Correctness guard, not a performance one - this runs unattended on the
# existing build cadence. Protects against a hill-climb's real failure
# mode of two swaps flipping back and forth forever instead of converging.
MAX_SWAPS = 50

# The formations FPL itself allows: 1 GKP fixed, (DEF, MID, FWD) from this
# list, always summing to 10 outfield players.
FORMATIONS = [
    (3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2),
    (4, 5, 1), (5, 3, 2), (5, 4, 1),
]
```

- [ ] **Step 2: Write `_by_position`**

```python
def _by_position(pool):
    out = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for p in pool:
        out[p["pos"]].append(p)
    return out
```

- [ ] **Step 3: Write `_greedy_fill`**

```python
def _greedy_fill(by_pos, quotas, budget, club_counts=None):
    """Highest value-per-cost first, respecting position quotas, budget
    and the 3-per-club cap. `club_counts` seeds club membership from
    players already picked outside this call (e.g. a bench picked before
    the XI) so the combined squad still respects the cap jointly. Returns
    None if a quota cannot be filled within budget at all."""
    club_counts = dict(club_counts or {})
    ranked = {
        pos: sorted(players, key=lambda p: -p["value"] / max(p["price"], 0.1))
        for pos, players in by_pos.items()
    }
    picks, spent = [], 0.0
    for pos, need in quotas.items():
        taken = 0
        for p in ranked[pos]:
            if taken >= need:
                break
            if spent + p["price"] > budget + 1e-9:
                continue
            if club_counts.get(p["club"], 0) >= CLUB_LIMIT:
                continue
            picks.append(p)
            spent += p["price"]
            club_counts[p["club"]] = club_counts.get(p["club"], 0) + 1
            taken += 1
        if taken < need:
            return None
    return picks
```

- [ ] **Step 4: Write `_cheapest_fill`**

```python
def _cheapest_fill(by_pos, quotas, club_counts=None):
    """Same shape as _greedy_fill, but cheapest-first rather than
    value-per-cost first - for Free Hit's bench, which never plays and
    only needs to be legal and affordable, not good."""
    club_counts = dict(club_counts or {})
    picks = []
    for pos, need in quotas.items():
        taken = 0
        for p in sorted(by_pos[pos], key=lambda p: p["price"]):
            if taken >= need:
                break
            if club_counts.get(p["club"], 0) >= CLUB_LIMIT:
                continue
            picks.append(p)
            club_counts[p["club"]] = club_counts.get(p["club"], 0) + 1
            taken += 1
        if taken < need:
            return None
    return picks
```

- [ ] **Step 5: Write `_hill_climb`**

```python
def _hill_climb(picks, by_pos, budget, other_club_counts=None):
    """Repeatedly swap one held player for a higher-value affordable
    replacement in the same position, until no swap improves the total or
    MAX_SWAPS is hit. `other_club_counts` covers players held outside this
    group (e.g. the bench, while climbing the XI) who still count against
    the 3-per-club cap."""
    other_club_counts = other_club_counts or {}
    picks = list(picks)
    held_ids = {p["id"] for p in picks}
    spent = sum(p["price"] for p in picks)
    own_club_counts = {}
    for p in picks:
        own_club_counts[p["club"]] = own_club_counts.get(p["club"], 0) + 1

    def total_club(club):
        return own_club_counts.get(club, 0) + other_club_counts.get(club, 0)

    converged = False
    for _ in range(MAX_SWAPS):
        best = None  # (gain, index_in_picks, candidate)
        for i, out in enumerate(picks):
            free_budget = budget - spent + out["price"]
            for cand in by_pos[out["pos"]]:
                if cand["id"] in held_ids:
                    continue
                if cand["price"] > free_budget + 1e-9:
                    continue
                cand_total = total_club(cand["club"])
                if cand["club"] == out["club"]:
                    cand_total -= 1  # the outgoing player frees his own slot
                if cand_total >= CLUB_LIMIT:
                    continue
                gain = cand["value"] - out["value"]
                if gain <= 1e-9:
                    continue
                if best is None or gain > best[0]:
                    best = (gain, i, cand)
        if best is None:
            converged = True
            break
        _gain, i, cand = best
        out = picks[i]
        held_ids.discard(out["id"])
        held_ids.add(cand["id"])
        spent += cand["price"] - out["price"]
        own_club_counts[out["club"]] -= 1
        own_club_counts[cand["club"]] = own_club_counts.get(cand["club"], 0) + 1
        picks[i] = cand
    if not converged:
        print(f"[squadbuilder] hill-climb did not converge within {MAX_SWAPS} swaps")
    return picks
```

- [ ] **Step 6: Verify all four helpers with a small synthetic pool**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import squadbuilder as sb

# Five clubs - enough that a 15-player fill under the 3-per-club cap is
# actually feasible (a first draft of this test used 2 clubs, which caps
# out at 6 players total and made every fill below infeasible by
# construction - caught live rather than left in the plan).
pool = []
pid = 0
for club in ("A", "B", "C", "D", "E"):
    for pos, n in (("GKP", 2), ("DEF", 5), ("MID", 5), ("FWD", 4)):
        for i in range(n):
            pid += 1
            value = 5.0 + i * 0.3 + (0.5 if club == "A" else 0.0)
            price = 4.0 + i * 0.4
            pool.append({"id": pid, "pos": pos, "club": club,
                        "price": price, "value": value})

by_pos = sb._by_position(pool)
assert set(by_pos.keys()) == {"GKP", "DEF", "MID", "FWD"}
assert len(by_pos["DEF"]) == 25

quotas = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
picks = sb._greedy_fill(by_pos, quotas, budget=200.0)
assert picks is not None
assert len(picks) == 15
counts = {}
for p in picks:
    counts[p["club"]] = counts.get(p["club"], 0) + 1
assert max(counts.values()) <= sb.CLUB_LIMIT, (
    f"club limit violated in greedy fill: {counts}")
print("greedy fill respects club limit:", counts)

cheap = sb._cheapest_fill(by_pos, {"GKP": 1, "DEF": 1, "MID": 1, "FWD": 1})
assert cheap is not None
prices = [p["price"] for p in cheap]
# cheapest fill should pick low-price options, not high-value ones
assert sum(prices) < 20.0, prices

# Infeasible on pure inventory (only 10 GKPs exist across the whole pool)
assert sb._greedy_fill(by_pos, {"GKP": 99}, budget=200.0) is None
# Infeasible purely on the club cap: 2 clubs can supply at most 6 players
# under a 3-per-club limit, so a 15-player quota cannot be met even though
# each position individually has enough inventory.
two_club_pos = sb._by_position([p for p in pool if p["club"] in ("A", "B")])
assert sb._greedy_fill(two_club_pos, quotas, budget=200.0) is None

improved = sb._hill_climb(picks, by_pos, budget=200.0)
improved_value = sum(p["value"] for p in improved)
original_value = sum(p["value"] for p in picks)
assert improved_value >= original_value, (
    f"hill-climb made things worse: {improved_value} < {original_value}")
improved_counts = {}
for p in improved:
    improved_counts[p["club"]] = improved_counts.get(p["club"], 0) + 1
assert max(improved_counts.values()) <= sb.CLUB_LIMIT
print(f"hill-climb: {original_value:.2f} -> {improved_value:.2f}, "
     f"club split {improved_counts}")
print("OK")
EOF
```
Expected: no assertion errors; the hill-climb's improved value is `>=` the greedy fill's value; club counts never exceed 3 anywhere.

- [ ] **Step 7: Commit**

```bash
git add squadbuilder.py
git commit -m "Add squadbuilder core: generic greedy fill + capped hill-climb over a candidate pool"
```

---

## Task 7: `squadbuilder.py` - public API (`best_xi`, `best_squad`)

**Files:**
- Modify: `squadbuilder.py` (add after Task 6's helpers)

**Interfaces:**
- Consumes: `FORMATIONS`, `_by_position`, `_greedy_fill`, `_cheapest_fill`, `_hill_climb` from Task 6
- Produces:
  `best_xi(pool, budget) -> {"formation": (d,m,f), "xi": [...], "bench": [...], "value": float, "cost": float} | None`
  `best_squad(pool, budget, bench_reserve_frac=0.12) -> {same shape}`
  Used by `chips.py`: `best_xi` for Free Hit / points-team (bench doesn't matter), `best_squad` for Wildcard (bench should be playable).

- [ ] **Step 1: Write `best_xi`**

```python
def best_xi(pool, budget):
    """The highest-value legal starting XI within budget - formation
    chosen to maximize total XI value. The bench is filled cheaply first
    (it never plays on a Free Hit), then whatever budget remains goes
    entirely into the XI."""
    by_pos = _by_position(pool)
    best = None
    for d, m, fw in FORMATIONS:
        bench_quota = {"GKP": 1, "DEF": 5 - d, "MID": 5 - m, "FWD": 3 - fw}
        bench = _cheapest_fill(by_pos, bench_quota)
        if bench is None:
            continue
        bench_cost = sum(p["price"] for p in bench)
        bench_ids = {p["id"] for p in bench}
        bench_club_counts = {}
        for p in bench:
            bench_club_counts[p["club"]] = bench_club_counts.get(p["club"], 0) + 1

        remaining_by_pos = {
            pos: [p for p in players if p["id"] not in bench_ids]
            for pos, players in by_pos.items()
        }
        xi_quotas = {"GKP": 1, "DEF": d, "MID": m, "FWD": fw}
        xi_budget = budget - bench_cost
        picks = _greedy_fill(remaining_by_pos, xi_quotas, xi_budget, bench_club_counts)
        if picks is None:
            continue
        picks = _hill_climb(picks, remaining_by_pos, xi_budget, bench_club_counts)

        value = sum(p["value"] for p in picks)
        cost = sum(p["price"] for p in picks) + bench_cost
        if best is None or value > best["value"]:
            best = {"formation": (d, m, fw), "xi": picks, "bench": bench,
                    "value": value, "cost": cost}
    return best
```

- [ ] **Step 2: Write `best_squad`**

```python
def best_squad(pool, budget, bench_reserve_frac=0.12):
    """The highest-value legal 15 within budget: the XI hill-climbed for
    value the same as best_xi, the bench filled by the same value-per-cost
    rule from what's left rather than pure minimum price - a Wildcard
    squad has to survive more than one week, so its bench should be able
    to play if called on."""
    by_pos = _by_position(pool)
    best = None
    for d, m, fw in FORMATIONS:
        xi_quotas = {"GKP": 1, "DEF": d, "MID": m, "FWD": fw}
        xi_budget = budget * (1 - bench_reserve_frac)
        picks = _greedy_fill(by_pos, xi_quotas, xi_budget)
        if picks is None:
            continue
        picks = _hill_climb(picks, by_pos, xi_budget)
        xi_cost = sum(p["price"] for p in picks)

        held_ids = {p["id"] for p in picks}
        club_counts = {}
        for p in picks:
            club_counts[p["club"]] = club_counts.get(p["club"], 0) + 1
        remaining_by_pos = {
            pos: [p for p in players if p["id"] not in held_ids]
            for pos, players in by_pos.items()
        }
        bench_quotas = {"GKP": 1, "DEF": 5 - d, "MID": 5 - m, "FWD": 3 - fw}
        bench = _greedy_fill(remaining_by_pos, bench_quotas,
                             budget - xi_cost, club_counts)
        if bench is None:
            continue

        value = sum(p["value"] for p in picks)
        cost = xi_cost + sum(p["price"] for p in bench)
        if best is None or value > best["value"]:
            best = {"formation": (d, m, fw), "xi": picks, "bench": bench,
                    "value": value, "cost": cost}
    return best
```

- [ ] **Step 3: Verify legality and budget with a synthetic pool**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import squadbuilder as sb

pool = []
pid = 0
clubs = ["A", "B", "C", "D", "E"]
for club in clubs:
    for pos, n in (("GKP", 3), ("DEF", 8), ("MID", 8), ("FWD", 5)):
        for i in range(n):
            pid += 1
            value = 3.0 + (pid % 13) * 0.4
            price = 4.0 + (pid % 9) * 0.8
            pool.append({"id": pid, "pos": pos, "club": club,
                        "price": price, "value": value})

BUDGET = 100.0

result = sb.best_xi(pool, BUDGET)
assert result is not None
xi, bench = result["xi"], result["bench"]
assert len(xi) == 11
assert len(bench) == 4
d, m, fw = result["formation"]
assert 3 <= d <= 5 and 2 <= m <= 5 and 1 <= fw <= 3 and d + m + fw == 10
pos_counts = {}
for p in xi:
    pos_counts[p["pos"]] = pos_counts.get(p["pos"], 0) + 1
assert pos_counts.get("GKP", 0) == 1
assert pos_counts["DEF"] == d and pos_counts["MID"] == m and pos_counts["FWD"] == fw
all_ids = [p["id"] for p in xi + bench]
assert len(all_ids) == len(set(all_ids)), "duplicate player in squad"
assert result["cost"] <= BUDGET + 1e-6, result["cost"]
club_counts = {}
for p in xi + bench:
    club_counts[p["club"]] = club_counts.get(p["club"], 0) + 1
assert max(club_counts.values()) <= 3, club_counts
print(f"best_xi: formation {result['formation']}, value {result['value']:.2f}, "
     f"cost {result['cost']:.2f}/{BUDGET}, clubs {club_counts}")

result2 = sb.best_squad(pool, BUDGET)
assert result2 is not None
assert len(result2["xi"]) == 11 and len(result2["bench"]) == 4
assert result2["cost"] <= BUDGET + 1e-6
club_counts2 = {}
for p in result2["xi"] + result2["bench"]:
    club_counts2[p["club"]] = club_counts2.get(p["club"], 0) + 1
assert max(club_counts2.values()) <= 3, club_counts2
# best_squad's bench should be worth more than best_xi's minimum-price
# bench, since it competes for value instead of just being legal filler
xi_bench_value = sum(p["value"] for p in result["bench"])
squad_bench_value = sum(p["value"] for p in result2["bench"])
assert squad_bench_value >= xi_bench_value, (
    f"best_squad's bench ({squad_bench_value:.2f}) should be at least as "
    f"good as best_xi's cheap bench ({xi_bench_value:.2f})")
print(f"best_squad: formation {result2['formation']}, value {result2['value']:.2f}, "
     f"bench value {squad_bench_value:.2f} (vs best_xi's {xi_bench_value:.2f})")

# infeasible budget should return None, not raise
assert sb.best_xi(pool, budget=1.0) is None
print("OK")
EOF
```
Expected: no assertion errors; both functions print a legal, budget-respecting result; the infeasible-budget case returns `None` cleanly.

- [ ] **Step 4: Commit**

```bash
git add squadbuilder.py
git commit -m "Add squadbuilder.best_xi and best_squad public API"
```

---

## Task 8: `chips.py` - shared utilities

**Files:**
- Create: `chips.py`

**Interfaces:**
- Consumes: `analysis.chip_window`, `fplapi.entry_history`, `transfers.positional_priors`, `transfers.windowed_candidate_score`, `transfers._eligible`, `analysis.PlayerReport.start_probability`
- Produces:
  `used_chips_this_half(entry_id, next_gw, ttl) -> {"wildcard": gw|None, "freehit": gw|None, "bboost": gw|None, "3xc": gw|None}`
  `confidence(best_value, other_values) -> "strong"|"watch"|"flexible"`
  `build_pool(ctx, proj, market, baselines, start_gw, weeks, exclude_ids=()) -> list[candidate dict]` (squadbuilder-shaped)

- [ ] **Step 1: Write the module header and confidence labeling**

```python
#!/usr/bin/env python3
"""
The four chip recommenders: Free Hit, Triple Captain, Bench Boost,
Wildcard - what week to target, and how strong the case actually is.

Each chip reads the shared windowed-EP layer (analysis.windowed_ep for the
manager's own 15, transfers.windowed_candidate_score for the wider pool
squadbuilder optimizes over) differently: Free Hit and Wildcard hand their
pool to squadbuilder, Triple Captain and Bench Boost scan the manager's
own squad directly.
"""

import analysis
import fplapi
import squadbuilder
import transfers

# Starting guesses, not a validated calibration - there is no data yet on
# how these gaps are actually distributed across a real season. Revisit
# once the recommender has run for a few gameweeks.
CONFIDENCE_STRONG = 0.20
CONFIDENCE_WATCH = 0.05


def confidence(best_value, other_values):
    """How much better the recommended week is than the rest of the
    window, as a plain-language read rather than a bare percentage."""
    if not other_values:
        return "flexible"
    avg_other = sum(other_values) / len(other_values)
    if avg_other <= 0:
        return "strong" if best_value > 0 else "flexible"
    lift = (best_value - avg_other) / avg_other
    if lift >= CONFIDENCE_STRONG:
        return "strong"
    if lift >= CONFIDENCE_WATCH:
        return "watch"
    return "flexible"
```

- [ ] **Step 2: Write `used_chips_this_half`**

```python
CHIP_NAMES = ("wildcard", "freehit", "bboost", "3xc")


def used_chips_this_half(entry_id, next_gw, ttl=fplapi.DEFAULT_TTL):
    """Which of the four chips are already burned in the current half,
    {"wildcard": gw or None, ...} - the same data the existing league
    'Chips used' table already reads, for this one manager."""
    half_start = 1 if next_gw <= 19 else 20
    half_end = 19 if next_gw <= 19 else 38
    history = fplapi.entry_history(entry_id, ttl=ttl)
    used = {name: None for name in CHIP_NAMES}
    for c in history.get("chips", []):
        if half_start <= c["event"] <= half_end and c["name"] in used:
            used[c["name"]] = c["event"]
    return used
```

- [ ] **Step 3: Write `build_pool`**

```python
def build_pool(ctx, proj, market, baselines, start_gw, weeks, exclude_ids=()):
    """The whole-league candidate pool, windowed-scored and squadbuilder-
    shaped: {"id", "pos", "club", "price", "value"}. Excludes anyone
    unfit to be suggested at all (transfers._eligible - injured,
    suspended, or ruled out of the predicted lineup) and anyone whose
    start_probability is too low to be worth a squad slot regardless of
    rate stats.

    Known limitation: start_probability is a single as-of-now estimate,
    not a per-gameweek one, so a player out injured today but nailed-on
    again by mid-window can be wrongly excluded here. No per-gameweek
    availability model exists yet to fix this properly."""
    priors = transfers.positional_priors(ctx)
    exclude_ids = set(exclude_ids)
    pool = []
    for el in ctx.players.values():
        pid = el["id"]
        if pid in exclude_ids or not transfers._eligible(el, ctx):
            continue
        r = analysis.PlayerReport(
            element=el, pos=ctx.pos(el), team=ctx.team_name(el["team"]),
            history=[], past=[],
        )
        if r.start_probability(ctx) < 0.15:
            continue
        total, _per_gw = transfers.windowed_candidate_score(
            el, ctx, proj, market, baselines, priors, start_gw, weeks)
        if total <= 0:
            continue
        pool.append({
            "id": pid, "pos": ctx.pos(el), "club": ctx.team_name(el["team"]),
            "price": el["now_cost"] / 10.0, "value": total,
        })
    return pool
```

Note: `PlayerReport(..., history=[], past=[])` is deliberate - this is the
cheap-scoring path, so it must not fetch per-player match history.
`start_probability` only reads `self.element` and `self.appearances`
(which is `0` for an empty history, the correct "no current-season
evidence" state that already blends toward last season / a neutral prior
per Task-level behavior already shipped in `analysis.py`), so an empty
history list is safe here, not a shortcut that skips real logic.

- [ ] **Step 4: Verify all three helpers**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import json, analysis, chips, ffs, odds

ctx = analysis.Ctx.load(ttl=3600)

# confidence(): lift = (best - avg(others)) / avg(others)
assert chips.confidence(10.0, [10.0, 10.0]) == "flexible"  # lift 0.00
assert chips.confidence(10.8, [10.0, 10.0]) == "watch"      # lift 0.08
assert chips.confidence(10.0, [8.0, 8.0]) == "strong"       # lift 0.25
assert chips.confidence(5.0, []) == "flexible"              # no other weeks to compare
print("confidence() cases OK")

# used_chips_this_half against the configured real manager
cfg = json.loads(open("config.json").read())
entry_id = cfg["entry_id"]
next_gw = min(38, (ctx.current_event() or 1) + 1)
used = chips.used_chips_this_half(entry_id, next_gw, ttl=3600)
assert set(used.keys()) == set(chips.CHIP_NAMES)
print("used_chips_this_half:", used)

# build_pool - small window to keep this fast, real data
proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
pool = chips.build_pool(ctx, proj, market, baselines, next_gw, weeks=2)
assert len(pool) > 100, f"pool suspiciously small: {len(pool)}"
sample = pool[0]
assert set(sample.keys()) == {"id", "pos", "club", "price", "value"}
assert sample["pos"] in ("GKP", "DEF", "MID", "FWD")
print(f"pool size: {len(pool)}")
print("OK")
EOF
```
Expected: no assertion errors; `used_chips_this_half` prints a dict with
all four chip names as keys; the pool has a few hundred entries with the
right shape.

- [ ] **Step 5: Commit**

```bash
git add chips.py
git commit -m "Add chips.py shared utilities: confidence labeling, used-chip lookup, pool building"
```

---

## Task 9: Free Hit / points team

**Files:**
- Modify: `chips.py` (add after Task 8)

**Interfaces:**
- Consumes: `squadbuilder.best_xi`, `chips.build_pool`, `chips.confidence`, `analysis.chip_window`, `analysis.windowed_ep` is NOT used here (single-week only, per spec)
- Produces: `points_team(ctx, xi_reports, proj, market, baselines, gw) -> {"ideal_value": float, "ours_value": float, "gap": float, "ideal_xi": [...]}` and `free_hit(ctx, xi_reports, proj, market, baselines, next_gw) -> {"gw": int, "gap": float, "confidence": str, "points_team": {...}} | None`

- [ ] **Step 1: Write `points_team`**

```python
def points_team(ctx, xi_reports, proj, market, baselines, gw):
    """The highest-scoring possible team this gameweek, against what the
    manager's own current best XI actually projects to - single week
    only, since this is also Free Hit's one-week evidence."""
    exclude_ids = {r.element["id"] for r in xi_reports}
    pool = build_pool(ctx, proj, market, baselines, gw, weeks=1,
                      exclude_ids=exclude_ids)
    # The manager's own XI is eligible for the "ideal" comparison too -
    # a Free Hit that's just "keep what you have" is a valid answer.
    own_pool = []
    for r in xi_reports:
        ep = analysis.expected_points(r, ctx, proj, gw, market=market,
                                      baselines=baselines)
        own_pool.append({
            "id": r.element["id"], "pos": r.pos, "club": r.team,
            "price": r.price, "value": ep["total"] if ep else 0.0,
        })
    full_pool = pool + own_pool

    budget = sum(r.price for r in xi_reports)  # XI-only budget, bench excluded
    ideal = squadbuilder.best_xi(full_pool, budget)
    ours_value = sum(p["value"] for p in own_pool)
    if ideal is None:
        return {"ideal_value": ours_value, "ours_value": ours_value,
                "gap": 0.0, "ideal_xi": own_pool}
    return {
        "ideal_value": ideal["value"], "ours_value": ours_value,
        "gap": max(0.0, ideal["value"] - ours_value),
        "ideal_xi": ideal["xi"],
    }
```

- [ ] **Step 2: Write `free_hit`**

```python
def free_hit(ctx, xi_reports, proj, market, baselines, next_gw):
    """The gameweek in the current chip window where the manager's own XI
    is furthest behind the best possible team - the Free Hit case."""
    start, weeks = analysis.chip_window(next_gw)
    gaps = {}
    pt_by_gw = {}
    for gw in range(start, start + weeks):
        pt = points_team(ctx, xi_reports, proj, market, baselines, gw)
        gaps[gw] = pt["gap"]
        pt_by_gw[gw] = pt
    if not gaps:
        return None
    best_gw = max(gaps, key=gaps.get)
    others = [v for gw, v in gaps.items() if gw != best_gw]
    return {
        "gw": best_gw, "gap": gaps[best_gw],
        "confidence": confidence(gaps[best_gw], others),
        "points_team": pt_by_gw[best_gw],
    }
```

- [ ] **Step 3: Verify against the real configured squad**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import json, analysis, chips, ffs, odds

cfg = json.loads(open("config.json").read())
entry_id = cfg["entry_id"]

ctx = analysis.Ctx.load(ttl=3600)
gw = ctx.last_event_with_picks()
picks = analysis.squad_for(entry_id, gw, ctx)
xi_ids = [p["element"] for p in picks["picks"] if p["position"] <= 11]
xi_reports = [analysis.build_player(ctx, pid, ttl=3600) for pid in xi_ids]

proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
next_gw = min(38, (ctx.current_event() or 1) + 1)

pt = chips.points_team(ctx, xi_reports, proj, market, baselines, next_gw)
assert pt["ideal_value"] >= pt["ours_value"] - 1e-6, (
    "the ideal team should never score less than our own actual XI")
print(f"points team GW{next_gw}: ideal={pt['ideal_value']:.2f} "
     f"ours={pt['ours_value']:.2f} gap={pt['gap']:.2f}")

fh = chips.free_hit(ctx, xi_reports, proj, market, baselines, next_gw)
assert fh is not None
assert fh["gw"] >= next_gw
print(f"free hit recommendation: GW{fh['gw']}, gap {fh['gap']:.2f}, "
     f"confidence {fh['confidence']}")
print("OK")
EOF
```
Expected: `ideal_value >= ours_value` always (the optimizer including our
own players as candidates guarantees this), a printed recommendation with
a gameweek inside the current window.

- [ ] **Step 4: Commit**

```bash
git add chips.py
git commit -m "Add points_team comparison and free_hit recommendation"
```

---

## Task 10: Triple Captain

**Files:**
- Modify: `chips.py` (add after Task 9)

**Interfaces:**
- Consumes: `analysis.expected_points`, `analysis.chip_window`, `chips.confidence`
- Produces: `triple_captain(ctx, xi_reports, proj, market, baselines, next_gw) -> {"player": PlayerReport, "gw": int, "ep": float, "confidence": str} | None`

- [ ] **Step 1: Write the function**

```python
def triple_captain(ctx, xi_reports, proj, market, baselines, next_gw):
    """The single (player, gameweek) pair with the highest projected
    points among the manager's own predicted starters, across the current
    chip window - captain him then for the biggest armband."""
    start, weeks = analysis.chip_window(next_gw)
    candidates = []  # (player_report, gw, ep_total)
    for r in xi_reports:
        if ctx.is_predicted(r.element) is False:
            continue
        for gw in range(start, start + weeks):
            ep = analysis.expected_points(r, ctx, proj, gw, market=market,
                                          baselines=baselines)
            if ep:
                candidates.append((r, gw, ep["total"]))
    if not candidates:
        return None
    best = max(candidates, key=lambda c: c[2])
    others = [c[2] for c in candidates if c is not best]
    return {
        "player": best[0], "gw": best[1], "ep": best[2],
        "confidence": confidence(best[2], others),
    }
```

- [ ] **Step 2: Verify**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import json, analysis, chips, ffs, odds

cfg = json.loads(open("config.json").read())
entry_id = cfg["entry_id"]
ctx = analysis.Ctx.load(ttl=3600)
gw = ctx.last_event_with_picks()
picks = analysis.squad_for(entry_id, gw, ctx)
xi_ids = [p["element"] for p in picks["picks"] if p["position"] <= 11]
xi_reports = [analysis.build_player(ctx, pid, ttl=3600) for pid in xi_ids]

proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
next_gw = min(38, (ctx.current_event() or 1) + 1)

tc = chips.triple_captain(ctx, xi_reports, proj, market, baselines, next_gw)
assert tc is not None
assert tc["player"] in xi_reports
assert tc["ep"] > 0
print(f"triple captain: {tc['player'].name} in GW{tc['gw']} for "
     f"{tc['ep']:.2f} ({tc['ep']*2:.2f} as armband), confidence {tc['confidence']}")
print("OK")
EOF
```
Expected: a real player from the current XI, a gameweek in the window, positive EP.

- [ ] **Step 3: Commit**

```bash
git add chips.py
git commit -m "Add triple_captain recommendation"
```

---

## Task 11: Bench Boost + transfer support

**Files:**
- Modify: `chips.py` (add after Task 10)

**Interfaces:**
- Consumes: `analysis.expected_points`, `analysis.chip_window`, `chips.confidence`, `transfers.suggest`
- Produces: `bench_boost(ctx, bench_reports, proj, market, baselines, next_gw, bank=0.0) -> {"gw": int, "ep": float, "confidence": str, "transfers": [...]} | None`

- [ ] **Step 1: Write the function**

```python
def bench_boost(ctx, bench_reports, proj, market, baselines, next_gw, bank=0.0):
    """The gameweek in the window where the manager's current bench
    projects highest, plus any transfers that would meaningfully improve
    that specific week - reusing transfers.suggest exactly as it already
    works, just pointed at the bench and the target week instead of the
    whole squad and next week."""
    start, weeks = analysis.chip_window(next_gw)
    totals = {}
    for gw in range(start, start + weeks):
        total = 0.0
        any_scored = False
        for r in bench_reports:
            ep = analysis.expected_points(r, ctx, proj, gw, market=market,
                                          baselines=baselines)
            if ep:
                total += ep["total"]
                any_scored = True
        if any_scored:
            totals[gw] = total
    if not totals:
        return None
    best_gw = max(totals, key=totals.get)
    others = [v for gw, v in totals.items() if gw != best_gw]

    # transfers.suggest computes its own positional_priors internally -
    # nothing else needed here.
    suggestions = transfers.suggest(
        ctx, bench_reports, proj, best_gw, market, baselines,
        bank=bank, per_slot=1, limit=3)
    for t in suggestions:
        t["in_club"] = ctx.team_name(t["in"]["team"])

    return {
        "gw": best_gw, "ep": totals[best_gw],
        "confidence": confidence(totals[best_gw], others),
        "transfers": suggestions,
    }
```

`in_club` is added here rather than left for the display layer because
`components.transfer_cards` (reused in Task 13 to render these) requires
it and `transfers.suggest`'s own return rows don't include it - the same
enrichment `dashboard.build()` already does by hand for its regular
transfer-suggestion card.

- [ ] **Step 2: Verify against the real configured squad**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import json, analysis, chips, ffs, odds

cfg = json.loads(open("config.json").read())
entry_id = cfg["entry_id"]
ctx = analysis.Ctx.load(ttl=3600)
gw = ctx.last_event_with_picks()
picks = analysis.squad_for(entry_id, gw, ctx)
bench_ids = [p["element"] for p in picks["picks"] if p["position"] > 11]
bench_reports = [analysis.build_player(ctx, pid, ttl=3600) for pid in bench_ids]
assert len(bench_reports) == 4

proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
next_gw = min(38, (ctx.current_event() or 1) + 1)
bank = (picks.get("entry_history", {}).get("bank") or 0) / 10.0

bb = chips.bench_boost(ctx, bench_reports, proj, market, baselines, next_gw, bank=bank)
assert bb is not None
print(f"bench boost: GW{bb['gw']}, {bb['ep']:.2f} pts, confidence {bb['confidence']}")
print(f"{len(bb['transfers'])} improving transfer(s) suggested for that week")
for t in bb["transfers"]:
    assert "in_club" in t, "in_club missing - components.transfer_cards will KeyError on this"
    print(f"  OUT {t['out'].name} -> IN {t['in']['web_name']} ({t['in_club']})  (+{t['gain']:.2f})")
print("OK")
EOF
```
Expected: a gameweek and EP total, zero or more suggested transfers (zero
is a legitimate answer if nothing clears `transfers.py`'s existing gain
threshold - don't treat an empty list as a bug).

- [ ] **Step 3: Commit**

```bash
git add chips.py
git commit -m "Add bench_boost recommendation with target-week transfer suggestions"
```

---

## Task 12: Wildcard

**Files:**
- Modify: `chips.py` (add after Task 11)

**Interfaces:**
- Consumes: `squadbuilder.best_squad`, `chips.build_pool`, `chips.confidence`, `analysis.windowed_ep`, `PlayerReport.recent_form`
- Produces: `wildcard(ctx, all_reports, proj, market, baselines, next_gw, budget) -> {"gw_window": (start, weeks), "gap": float, "confidence": str, "moves": [...]} | None`, where each move is `{"out": PlayerReport, "in": el_dict, "in_form": dict|None}`

- [ ] **Step 1: Write the function**

```python
def wildcard(ctx, all_reports, proj, market, baselines, next_gw, budget):
    """The best full-squad rebuild available right now, scored over the
    chip window (a permanent change needs a run of fixtures, not one
    week) and diffed against the current squad in sell/buy pairs, ranked
    by price so the story reads most-expensive-change-first."""
    start, weeks = analysis.chip_window(next_gw)
    exclude_ids = {r.element["id"] for r in all_reports}
    pool = build_pool(ctx, proj, market, baselines, start, weeks,
                      exclude_ids=exclude_ids)
    own_pool = []
    for r in all_reports:
        total, _per_gw = analysis.windowed_ep(r, ctx, proj, market, baselines,
                                              start, weeks)
        own_pool.append({"id": r.element["id"], "pos": r.pos, "club": r.team,
                         "price": r.price, "value": total})
    full_pool = pool + own_pool

    ideal = squadbuilder.best_squad(full_pool, budget)
    if ideal is None:
        return None
    # Compare like for like: the manager's own best XI over the same
    # window, formation-optimized the same way points_team finds one for
    # a single week - budget is unconstrained here since these 15 are
    # already owned, only which 11 of them to start is being decided.
    own_reports_by_id = {r.element["id"]: r for r in all_reports}
    current_best = squadbuilder.best_xi(own_pool, budget=1e9)
    current_value = current_best["value"] if current_best else 0.0

    gap = max(0.0, ideal["value"] - current_value)

    ideal_ids = {p["id"] for p in ideal["xi"] + ideal["bench"]}
    current_ids = {r.element["id"] for r in all_reports}
    outgoing = [own_reports_by_id[pid] for pid in current_ids - ideal_ids]
    incoming = [ctx.players[pid] for pid in ideal_ids - current_ids]
    outgoing.sort(key=lambda r: -r.price)
    incoming.sort(key=lambda el: -(el["now_cost"] / 10.0))

    # Each move is built display-ready here, in the shape
    # components.transfer_cards already expects (out_score/in_score need
    # "total", "opponent", "home"; in_club is separate from in_score) -
    # scored at the window's first gameweek, real numbers rather than
    # placeholders, so the reused card shows an honest fixture and gain
    # per move instead of a flat, meaningless bar.
    priors = transfers.positional_priors(ctx)
    moves = []
    for out_r, in_el in zip(outgoing, incoming):
        in_full = analysis.build_player(ctx, in_el["id"], ttl=fplapi.DEFAULT_TTL)
        out_score = analysis.expected_points(
            out_r, ctx, proj, start, market=market, baselines=baselines
        ) or {"total": 0.0, "opponent": "-", "home": True}
        in_score = transfers.candidate_score(
            in_el, ctx, proj, start, market, baselines, priors
        ) or {"total": 0.0, "opponent": "-", "home": True}
        moves.append({
            "out": out_r, "in": in_el, "in_club": ctx.team_name(in_el["team"]),
            "out_score": out_score, "in_score": in_score,
            "gain": in_score["total"] - out_score["total"],
            "price": in_el["now_cost"] / 10.0,
            "spend": in_el["now_cost"] / 10.0 - out_r.price,
            "in_form": in_full.recent_form(),
        })

    return {
        "gw_window": (start, weeks), "gap": gap,
        "confidence": confidence(ideal["value"], [current_value]),
        "moves": moves,
    }
```

- [ ] **Step 2: Verify against the real configured squad**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python - <<'EOF'
import json, analysis, chips, ffs, odds

cfg = json.loads(open("config.json").read())
entry_id = cfg["entry_id"]
ctx = analysis.Ctx.load(ttl=3600)
gw = ctx.last_event_with_picks()
picks = analysis.squad_for(entry_id, gw, ctx)
all_ids = [p["element"] for p in picks["picks"]]
all_reports = [analysis.build_player(ctx, pid, ttl=3600) for pid in all_ids]
assert len(all_reports) == 15

proj = ffs.projections(ttl=3600)
odds.build_club_lookup(ctx)
market = odds.by_club(ctx, ttl=3600)
baselines = analysis.team_attack_baselines(ctx)
next_gw = min(38, (ctx.current_event() or 1) + 1)

total_sell, _ = analysis.squad_sell_value(entry_id, ctx, all_reports, ttl=3600)
bank = (picks.get("entry_history", {}).get("bank") or 0) / 10.0
budget = total_sell + bank

wc = chips.wildcard(ctx, all_reports, proj, market, baselines, next_gw, budget)
assert wc is not None
assert wc["gap"] >= 0
print(f"wildcard over GW{wc['gw_window'][0]}-{wc['gw_window'][0]+wc['gw_window'][1]-1}: "
     f"gap {wc['gap']:.2f}, confidence {wc['confidence']}")
required_keys = {"out", "in", "in_club", "out_score", "in_score", "gain", "price", "spend", "in_form"}
for mv in wc["moves"]:
    missing = required_keys - mv.keys()
    assert not missing, f"move missing {missing} - components.transfer_cards will KeyError"
    assert "total" in mv["out_score"] and "opponent" in mv["in_score"], mv
    hot = " [HOT]" if mv["in_form"] and mv["in_form"]["hot"] else ""
    print(f"  OUT {mv['out'].name} -> IN {mv['in']['web_name']} ({mv['in_club']}){hot} "
         f"gain {mv['gain']:+.2f}")
seen_out = {mv["out"].element["id"] for mv in wc["moves"]}
seen_in = {mv["in"]["id"] for mv in wc["moves"]}
assert len(seen_out) == len(wc["moves"])
assert len(seen_in) == len(wc["moves"])
print("OK")
EOF
```
Expected: no assertion errors, a printed list of proposed swaps (may be
empty if the current squad is already close to ideal - a legitimate
result, not a bug), gap `>= 0`.

- [ ] **Step 3: Commit**

```bash
git add chips.py
git commit -m "Add wildcard recommendation with sell/buy diff and hot-form cross-reference"
```

---

## Task 13: Dashboard wiring - CSS and card renderer

**Files:**
- Modify: `dashboard.py` (CSS block, new render function, `build()`'s returned dict, the Planning-tab template section)

**Interfaces:**
- Consumes: everything from Tasks 4, 9, 10, 11, 12; `components.transfer_cards` (existing, reused for Bench Boost's and Wildcard's transfer/move lists)
- Produces: `chip_planner_card(fh, tc, bb, wc, used, photos, shirts) -> str` (HTML), wired into `build()`'s dict as `"chip_planner"` and into the Planning tab template.

- [ ] **Step 1: Add CSS**

Add near the other card-family CSS (alongside `.oilist`/`.oi` - the
"What the odds mean for you" cards are the closest existing shape: a
label, a big value, supporting detail):

```css
/* --- chip planner --- */
.cplist{list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px}
.cp{
  position:relative; padding:14px 14px 12px; border-radius:var(--radius-m);
  background:var(--surface-variant); border-top:3px solid var(--lilac);
}
.cp.used{opacity:.55}
.cp-label{margin:0; font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant)}
.cp-gw{margin:4px 0 0; font-size:22px; font-weight:700; font-variant-numeric:tabular-nums}
.cp-reason{margin:4px 0 0; font-size:13px; color:var(--on-surface-variant)}
.cp-conf{
  display:inline-block; margin-top:8px; padding:2px 8px; border-radius:9999px;
  font-size:11px; font-weight:700;
}
.cp-conf-strong{background:var(--success); color:#fff}
.cp-conf-watch{background:var(--p40); color:var(--purple)}
.cp-conf-flexible{background:var(--outline-variant); color:var(--on-surface-variant)}
.cp-used-tag{font-size:11px; color:var(--on-surface-variant); margin-top:8px}
.cp-pt{
  margin-top:10px; padding-top:10px; border-top:1px solid var(--outline-variant);
  font-size:12px; color:var(--on-surface-variant);
}
```

- [ ] **Step 2: Write the render function**

Add to `dashboard.py`, near the other card-composition functions (a good
spot is just above `player_dialog`, since both sit at the "compose a
section from already-computed data" layer):

```python
CONFIDENCE_LABEL = {"strong": "Strong", "watch": "Worth watching",
                    "flexible": "Timing flexible"}


def _cp_card(label, used_gw, body_html):
    if used_gw:
        return (
            f'<div class="cp used"><p class="cp-label">{e(label)}</p>'
            f'<p class="cp-used-tag">Already used, GW{used_gw}</p></div>'
        )
    return f'<div class="cp"><p class="cp-label">{e(label)}</p>{body_html}</div>'


def chip_planner_card(fh, tc, bb, wc, used):
    """The four chip recommendations, one card each - target gameweek,
    the number behind it, and a plain-language confidence read."""
    if not (fh or tc or bb or wc):
        return ""

    def conf_pill(level):
        return (f'<span class="cp-conf cp-conf-{level}">'
               f'{e(CONFIDENCE_LABEL.get(level, level))}</span>')

    cards = []

    if fh:
        pt = fh["points_team"]
        body = (
            f'<p class="cp-gw">GW{fh["gw"]}</p>'
            f'<p class="cp-reason">Best possible XI projects {pt["ideal_value"]:.1f} pts '
            f'against your {pt["ours_value"]:.1f} - a gap of {fh["gap"]:.1f}.</p>'
            f'{conf_pill(fh["confidence"])}'
        )
        cards.append(_cp_card("Free Hit", used.get("freehit"), body))

    if tc:
        body = (
            f'<p class="cp-gw">GW{tc["gw"]}</p>'
            f'<p class="cp-reason">Captain {e(tc["player"].name)} for '
            f'{tc["ep"]:.1f} pts ({tc["ep"] * 2:.1f} with the armband).</p>'
            f'{conf_pill(tc["confidence"])}'
        )
        cards.append(_cp_card("Triple Captain", used.get("3xc"), body))

    if bb:
        body = (
            f'<p class="cp-gw">GW{bb["gw"]}</p>'
            f'<p class="cp-reason">Bench projects {bb["ep"]:.1f} pts that week'
            f'{" - if your bench stays as it is." if not bb["transfers"] else "."}</p>'
            f'{conf_pill(bb["confidence"])}'
        )
        if bb["transfers"]:
            # bb["transfers"] rows already carry every field
            # components.transfer_cards needs (transfers.suggest's own
            # shape, plus in_club added in chips.bench_boost) - only the
            # photo/shirt fields are missing, since chips.py has no photo
            # data to add them with.
            rows = [{**t, "out_photo": None, "in_photo": None,
                    "out_shirt": None, "in_shirt": None}
                   for t in bb["transfers"]]
            body += components.transfer_cards(
                rows, "Would improve that specific week.")
        cards.append(_cp_card("Bench Boost", used.get("bboost"), body))

    if wc:
        start, weeks = wc["gw_window"]
        body = (
            f'<p class="cp-gw">GW{start}-{start + weeks - 1}</p>'
            f'<p class="cp-reason">{wc["gap"]:.1f} pts of upside available '
            f'over the window.</p>'
            f'{conf_pill(wc["confidence"])}'
        )
        if wc["moves"]:
            # Same story as Bench Boost - chips.wildcard already builds
            # each move with real out_score/in_score/gain/in_club (Task
            # 12), so only photos are missing here.
            rows = [{**mv, "out_photo": None, "in_photo": None,
                    "out_shirt": None, "in_shirt": None}
                   for mv in wc["moves"]]
            body += components.transfer_cards(rows, "Suggested rebuild, most expensive first.")
        cards.append(_cp_card("Wildcard", used.get("wildcard"), body))

    return (
        '<section class="card"><div class="card-head"><h2>Chip planner</h2>'
        '<span class="sub">Best gameweek for each chip in the current half, '
        'scored from the same projections as the rest of the page.</span></div>'
        f'<div class="card-body"><ul class="cplist">{"".join(cards)}</ul></div></section>'
    )
```

- [ ] **Step 3: Wire into `build()`**

In `dashboard.py`, inside `build()`, after the existing `eps`/`market`/
`baselines`/`proj` block (the same spot `squad_table`/`pitch`/`pick_pitch`
are already called from) add:

```python
    # Same graceful-degradation shape ticker.fixture_ticker already uses
    # for the same reason: if proj never arrived this build, there is
    # nothing honest to recommend, so the whole card skips rather than
    # showing a set of zeroed or misleading cards.
    fh = tc = bb = wc = None
    used = {}
    if proj:
        bank_m = (picks.get("entry_history", {}).get("bank") or 0) / 10.0
        try:
            total_sell, _per_player = analysis.squad_sell_value(
                entry_id, ctx, xi + bench, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[chips] sell value unavailable, falling back to "
                  f"current price: {ex}")
            total_sell = sum(r.price for r in xi + bench)
        fh = chips.free_hit(ctx, xi, proj, market, baselines, next_gw)
        tc = chips.triple_captain(ctx, xi, proj, market, baselines, next_gw)
        bb = chips.bench_boost(ctx, bench, proj, market, baselines, next_gw,
                               bank=bank_m)
        wc = chips.wildcard(ctx, xi + bench, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        try:
            used = chips.used_chips_this_half(entry_id, next_gw, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[chips] chip history unavailable: {ex}")
```

And add `"chips" if it's imported` - add `import chips` to the top of
`dashboard.py` alongside the other local module imports (`import ticker`,
`import transfers`, etc.), and add to the returned dict:

```python
        "chip_planner": chip_planner_card(fh, tc, bb, wc, used),
```

- [ ] **Step 4: Wire into the Planning-tab template**

In `render()`'s template string, inside the `p-market` panel (the
Planning tab), add near the top, before the fixture ticker:

```html
    {d['chip_planner']}
```

- [ ] **Step 5: Commit**

```bash
git add dashboard.py
git commit -m "Wire the chip planner into the dashboard's Planning tab"
```

---

## Task 14: Full integration rebuild and visual verification

**Files:** none (verification only)

- [ ] **Step 1: Full rebuild with no exceptions**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python cli.py dashboard 2>&1 | tail -40
```
Expected: `wrote ...dashboard.html` with no traceback. If it fails, the
error will point at one of the Tasks above - fix there, not by patching
around it here.

- [ ] **Step 2: Serve and screenshot with Playwright**

```bash
cd "C:\Users\jonno\code\fpl-insights" && python -m http.server 8799
```
(run in background)

Navigate to `http://localhost:8799/dashboard.html`, click the "Planning"
tab, screenshot the "Chip planner" card at desktop width (1280) and at
mobile width (390) - same pattern used for every UI change earlier in the
session that produced this plan.

Check specifically:
- All four sub-cards render (or show "already used" if genuinely used
  this half - check against `chips.used_chips_this_half`'s printed output
  from Task 8's verification if any card is unexpectedly greyed out).
- Bench Boost's and Wildcard's `transfer_cards` rows render sensibly with
  `out_photo`/`in_photo` left as `None` (Task 13 - chips.py has no photo
  data to add, so `_face()`'s blank-initial fallback renders instead of a
  crest). Confirm that reads as acceptably plain rather than visibly
  broken; if it looks broken, that's the trigger to thread `photos`/
  `shirts` (already available in `build()`) through to `chips.py`'s
  Bench Boost and Wildcard move-building, the same way the regular
  transfer-suggestion card already gets them.
- No horizontal overflow on mobile.

- [ ] **Step 3: Stop the server and clean up**

```bash
# Stop whatever process is bound to port 8799
```
(kill the background http.server process; remove any screenshot files
from the repo working directory - none of this session's verification
artifacts belong in git, matching how every earlier screenshot pass in
this session was cleaned up afterward)

- [ ] **Step 4: Confirm nothing untracked or unwanted was left behind**

```bash
cd "C:\Users\jonno\code\fpl-insights" && git status --short
```
Expected: clean, or only `dashboard.html`/`dashboard-artifact.html` (both
gitignored build output) - nothing else.

This task has no commit step of its own - it's verification of Tasks 1-13
together, not new code.
