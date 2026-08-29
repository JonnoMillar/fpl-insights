# Chip suggester — design

## Problem

FPL gives every manager one Wildcard, one Free Hit, one Bench Boost and one
Triple Captain to use between GW1 and GW19, then a fresh set of the same four
between GW20 and GW38. Deciding *when* to use each is one of the biggest
swings in a season's points total, and today the dashboard gives no help with
it at all. This adds a "chip planner" that looks across the remaining
gameweeks in the current half and recommends a target week per chip, with a
plain-language reason and a confidence read on how strong the case actually
is.

Out of scope for this pass, by earlier agreement: a forward-looking advisory
that suggests transfers now to *shape* a squad for a stronger future Bench
Boost or Wildcard. The core recommender ships first; that's a follow-up once
this is live and its output has been seen for a few gameweeks.

## Foundations

### Two scorers, not one

`analysis.expected_points` needs a full `PlayerReport`, which needs that
player's per-match history - one API call each. Fine for the manager's own
15, whose history is already fetched for the rest of the dashboard, but the
optimizer scores the *entire* player pool (~600), and `transfers.py`
already solved exactly this cost problem for its own candidate search:
`candidate_score(el, ctx, proj, gw, market, baselines, priors)` scores any
player from the bootstrap payload alone, no per-candidate request. The
optimizer's pool is built with `candidate_score` (windowed the same way
`expected_points` is, see below); the manager's own squad is scored with
the richer `expected_points` it already pays for elsewhere.

### Windowed expected points

`analysis.windowed_ep(r, ctx, proj, market, baselines, start_gw, weeks=8)` -
sums `expected_points()` for one player across `weeks` consecutive
gameweeks, returning both the total and the per-gameweek breakdown (a list of
`(gw, ep_dict)`), so callers can read a sum, an average, or find a peak week
from the same call. Weeks with no fixture or projection data (a blank
gameweek) are skipped rather than scored as zero, matching how
`expected_points` already returns `None` when it has nothing to go on.

The same shape exists for the cheap scorer: `transfers.windowed_candidate_score`
sums `candidate_score()` across a window instead, for building the
optimizer's full-pool candidates without per-player requests.

This is possible now specifically because of the market-staleness fix made
earlier this session - before that, calling `expected_points` for a future
gameweek could silently repeat the imminent gameweek's market line forever.

### The chip window

`chip_window(next_gw)`:

```
first_half = next_gw <= 19
end = 19 if first_half else 38
start = next_gw
weeks = min(8, end - start + 1)
```

Every chip's search is scoped to `[start, start+weeks)`. Eight gameweeks is
the agreed cap even when more remain in the half, since a projection further
out than that is mostly noise.

### Already-used chips

Chip usage comes from `fplapi.entry_history(entry_id)["chips"]`, the same
field the existing league "Chips used" table already reads
(`dashboard.chips_table`).
Each entry is `{"name": "wildcard"|"freehit"|"bboost"|"3xc", "event": gw}`.
A chip whose `event` falls inside the *current* half is marked used and
excluded from the active recommendations (still worth showing, greyed out,
so the card doesn't just silently drop a row).

### True sell value

FPL sell a player back at purchase price plus half of any rise since,
rounded down to the nearest £0.1m, and the full price if it has fallen -
and this is the number that bounds every optimizer run below, so it has to
be right rather than approximated.

`analysis.squad_sell_value(entry_id, ctx, squad_reports, ttl)`:

1. Fetch `fplapi.get_json(f"{BASE}/entry/{entry_id}/transfers/")` - a public,
   unauthenticated endpoint (verified live) listing every transfer the
   manager has ever made, each row carrying `element_in`, `element_in_cost`
   (their exact buy price, in tenths of a million - not an estimate).
2. For each currently-held player, find their most recent `element_in`
   transaction for that player id. That is unambiguously their purchase
   basis for the copy they currently hold, regardless of any earlier
   sell/rebuy history.
3. For a player with no such transaction (held since GW1, never
   transferred), their purchase price is their `value` field from their own
   `element_summary(player_id)["history"]` row at `round == 1` - confirmed
   live to be present and to carry the price at that gameweek, not just the
   current one.
4. Apply FPL's rule per player: `sell = buy + (now_cost - buy) // 2` if
   `now_cost > buy`, else `sell = now_cost`.
5. Total squad sell value = sum of `sell` across all 15, which becomes the
   optimizer's budget together with the manager's current bank.

One extra cached API call per manager (`/transfers/`), same cost pattern as
everything else in `fplapi.py`.

## The optimizer (`squadbuilder.py`, new module)

A constrained best-team builder, shared by Free Hit and Wildcard with
different objectives. No ILP solver dependency is added - this is a greedy
fill followed by a hill-climbing swap pass:

1. **Fill**: for each position quota - 2 GKP / 5 DEF / 5 MID / 3 FWD for a
   full squad, or 1 GKP plus whichever valid outfield split (3-5 DEF /
   2-5 MID / 1-3 FWD, 10 outfield total, the same formations FPL itself
   allows) scores highest for XI-only mode - greedily take the
   highest-value-per-cost eligible player that fits the remaining budget
   and the 3-per-club limit.
2. **Improve**: repeatedly scan for a single swap (one held player for one
   unheld player, same position, affordable within the freed budget, club
   limit respected) that increases the objective. Keep applying the best
   available improving swap until none remains, capped at 50 swaps - not a
   performance concern (this runs unattended on the same 3-hourly build
   everything else already does), but a correctness guard against a
   hill-climb's real failure mode of two swaps flipping back and forth
   forever. Hitting the cap should log a warning rather than fail silently,
   since it would mean the answer wasn't fully converged.
3. **Eligibility filter**, applied before either step: exclude injured /
   suspended / unavailable-flagged players, and anyone with
   `start_probability(ctx) < 0.15` - a technically-nailed-on-paper player
   who is not going to play is not worth a slot regardless of rate stats.

   **Known limitation**: `start_probability` is a single "as of right now"
   estimate, not a per-gameweek projection. Over an 8-week Wildcard window
   this can wrongly exclude someone injured today but nailed-on and
   dangerous by week 4 - exactly a plausible Wildcard target. There's no
   clean fix without a genuinely bigger change (a per-gameweek availability
   model), so this pass just says so in the UI copy rather than pretending
   the window-wide filter is more accurate than it is.

This is a strong approximation, not a provable optimum, and the UI copy
says so plainly rather than implying a solved optimization.

**Two objective modes:**

- **XI-only** (Free Hit): maximize the starting XI's single-gameweek EP.
  The remaining 4 squad slots are legal, cheap fill (minimum-price eligible
  players per position) since Free Hit's bench never plays.
- **Full-squad** (Wildcard): maximize the starting XI's *windowed* EP (the
  8-gameweek sum, not one week), with the bench filled from realistically
  affordable, actually-playable options rather than pure minimum-price
  fodder - a Wildcard squad has to survive more than one week.

## Points team / Free Hit

For each gameweek in the window: run the XI-only optimizer, and separately
compute the manager's own best-XI EP for that same week (same selection the
existing "Expected points" card already ranks). The gap is that week's
Free Hit case; the single largest gap in the window is the recommendation.

This doubles as its own small comparison ("what would the highest-scoring
possible team have got this week, against what we actually fielded") shown
for the *next* gameweek specifically, near the existing Expected Points
card - and reused as the Free Hit sub-card's supporting evidence for
whichever week it recommends.

## Triple Captain

For each of the manager's own predicted starters, take their per-gameweek
EP (not summed) across the window and find the single `(player, gameweek)`
pair with the highest value. That pair is the recommendation - captain this
player in this gameweek for this projected total, doubled for the armband.

## Bench Boost

For each gameweek in the window, sum the *current bench's* four players'
EP for that week (their fixtures change week to week same as anyone
else's). The peak week is the recommendation, captioned as conditional on
the bench staying as it is between now and then.

**Transfer support**: once the target week is known, call
`transfers.suggest(ctx, bench_reports, proj, target_gw, market, baselines,
bank=...)` with the squad list restricted to the *current four bench
players* and `gw` set to the target week instead of next week.
`transfers.suggest` already takes an arbitrary gameweek and an arbitrary
list of outgoing candidates - no change to that module is needed, only a
new call site with different arguments. This answers "what transfers would
make this bench boost better" using the same swap-search machinery the
existing transfer suggestions already use, scored against the target week
rather than next week.

## Wildcard

Run the full-squad optimizer with the windowed-EP objective over the
window. Diff the result against the current squad by position (removed
vs. added). Where more than one player swaps within the same position,
pair outgoing and incoming by descending price (most expensive change
first) - an arbitrary pairing would still be mathematically valid but
would read as a random shuffle rather than a story. Present it in the
same "sell X, buy Y" shape the existing transfer/pairing cards already
render, rather than a new UI language.

Score: the windowed-EP gap between the optimizer's ideal starting XI and
the manager's own current best XI, over the same window. Larger gap, more
compelling case for wildcarding now versus waiting.

Each incoming player who isn't currently owned is cross-referenced against
`PlayerReport.recent_form()` - if their `hot` flag is set, that's surfaced
directly as supporting text ("in the last N games: 4 returns"). This is
the "players we don't have who are performing very well" signal, and it's
free: `recent_form()` already exists from the pick-team work earlier this
session.

## Confidence

Each chip's recommended week is compared against the average of the *other*
weeks in the window (same metric the chip is scored on):

- Notably above average (starting guess: ≥20%) → **strong**
- Modestly above (5-20%) → **worth watching**
- Barely above (<5%) → **no clear best week yet - timing is flexible**

These two cutoffs are a starting guess, not a validated calibration - there
is no data yet on how these gaps are actually distributed across a real
season. Revisit once the recommender has run for a few gameweeks and the
real spread of gaps is visible, rather than treating 20%/5% as settled.

This keeps the tool from manufacturing false precision when a chip
genuinely has no standout week, which is a real and common state, not an
edge case to hide.

## UI

A new "Chip planner" card on the **Planning** tab. Four sub-cards, one per
chip:

- Target gameweek
- One-line reason (the number that drove the recommendation)
- Confidence tag
- Wildcard's sub-card additionally lists its top incoming names with their
  form context; Bench Boost's additionally lists the suggested transfers if
  any clear the usual gain threshold.

Chips already used this half render greyed-out with "used GW_n_" rather
than being silently omitted.

The points-team comparison lives as a small strip inside the Free Hit
sub-card (its primary consumer) rather than as a fully separate section.

## Error handling

- If `proj` or `market` are unavailable for a build, the chip planner card
  does not render - same pattern `ticker.fixture_ticker` already uses when
  `proj` is empty, rather than showing a card full of blanks or crashing
  the build.
- If the optimizer cannot fill a legal squad under the available budget
  (should be rare, but a squad far outside a normal value distribution is
  possible), it returns `None` and the affected chip's sub-card says there
  isn't enough to go on this week rather than guessing.
- If the hill-climb hits its 50-swap cap without converging (see the
  optimizer section), the run still returns its best-so-far answer, logged
  as a warning in the build output the same way a failed data source
  already is (`fplapi.note`) - a slightly-short-of-perfect squad is still
  useful; a missing card is not.

## Files touched

- `analysis.py` - `windowed_ep`, `chip_window`, `squad_sell_value`
- `squadbuilder.py` (new) - the constrained optimizer
- `chips.py` (new) - the four chip-specific recommenders + confidence
  labeling, orchestrating `windowed_ep` / `squadbuilder` / `transfers.py`
- `transfers.py` - no changes; reused as-is with new call-site arguments
- `dashboard.py` - new card renderer, CSS, wiring into `build()`'s
  returned dict and the Planning-tab template section
- `fplapi.py` - no changes; `/transfers/` reached via the existing
  `get_json` helper

## Testing plan

- Unit-style checks (synthetic `PlayerReport`s, same pattern used for
  `start_probability` earlier this session) for: `windowed_ep` skipping
  blank gameweeks correctly; `chip_window` at the GW19/20 boundary and near
  GW38; `squad_sell_value` against a hand-computed example (a riser, a
  faller, a never-transferred GW1 hold).
- Live verification against the real squad/league already configured:
  confirm the optimizer's chosen XI is legal (formation, budget, club
  limit) and its EP total is ≥ the manager's own current best XI (it should
  never recommend something worse than reality).
- Club-limit sanity check: the 3-per-club rule is where a single-swap
  hill-climb is most likely to get stuck (an early greedy pick can lock in
  3 players from one club and block a better combination that only a
  2-for-2 trade would reach). Run the optimizer once with that limit
  relaxed and compare - if the gap between the two answers is large, the
  constrained result is probably a weak local optimum, not a real
  club-limit effect, and the fill/improve approach needs a second look
  before shipping.
- Full `cli.py dashboard` rebuild with no exceptions, then a Playwright
  screenshot pass of the new card at desktop and mobile widths, same
  verification pattern used for every UI change earlier in this session.

## Decisions settled during design

- Bench Boost transfer suggestions use `transfers.py`'s existing
  `gain <= 0.15` cutoff rather than a second, separately-tuned number - one
  "is this worth mentioning" threshold for the whole app, not two.
- The optimizer chooses from the same formations FPL itself allows: 1 GKP
  fixed, 3-5 DEF, 2-5 MID, 1-3 FWD, 10 outfield total (covers 3-4-3, 3-5-2,
  4-4-2, 4-3-3, 4-5-1, 5-3-2, 5-4-1 and the rest of that family).
