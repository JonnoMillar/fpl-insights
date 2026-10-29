# How this account will be managed

## Objective and authority

Maximise expected points **from this account's first deadline onward**, with
ordinary uncertainty and sensible transfer restraint. A GW9 entry cannot recover
GW1–8 points; judge improvement against a fixed GW9 starting squad, a simple
captain-the-premium baseline, and managers who started in GW9. Overall rank is
informative but confounded by the late start. Do not chase unlikely rank swings
with low-ownership punts just because the account begins behind.

Jonno has delegated initial selection and season management. Routine XI,
bench, captain/vice and free-transfer decisions do not need a weekly question.
The initial operating policy is **no points hits and no chips without explicit
expanded authority**. This is the assistant's conservative starting policy,
announced in chat, not a claim Jonno expressly chose those limits. Prepare chip
recommendations early enough for one useful decision, not four last-minute
questions. Never change profile/security settings, enter paid competitions,
claim prizes, publish the dashboard, or alter another account as part of this.

## Evidence hierarchy

1. Signed-in team: account identity, private holdings, purchase/selling prices,
   bank, FT allowance, chips, saved XI/bench/armbands. This outranks a static page.
2. Fresh FPL bootstrap and fixtures: player IDs/positions/clubs/prices, flags,
   deadlines and scheduled fixtures. A green flag is not proof of a start.
3. Dated club press conferences/injury updates and actual recent lineups,
   including Europe/cups: availability, role, workload and competition for places.
   Club social hints and training pictures alone do not prove full fitness.
4. Fixture-bound FFS club projections, predicted XIs and matching market odds:
   estimate team goals/clean sheets and starting chances. Store source and read
   time; re-fetch near the deadline. Prediction is not a confirmed lineup.
5. Existing per-player season and match-history evidence: minutes, starts,
   non-penalty threat, chance creation, actual duties and defensive award hits.
   Use per-90 rates with minutes/sample-size context. Regress tiny samples.
6. Elite ownership, transfers, points form and the Scout's editorial picks:
   challenge a decision or identify a missing candidate; not an instruction to
   follow the crowd. Multiple websites reprinting one quote are one source.

No paid feed is required. No new dependency or speculative physical/medical
inference. Extra research must change a concrete decision to justify its effort.

## Existing model: reuse and limits

The initial comparison uses `transfers.candidate_score` via
`planner.player_weeks`, then `squadbuilder.best_squad` for seeds and
`squadbuilder.owned_xi` for each held squad's weekly XI. This keeps candidates
on one yardstick. Rates blend xG/xA with actual returns, shrink toward
price/position priors using 400 minutes, and include appearance, clean sheet,
defensive contribution, bonus, saves, cards and conceded-goal components.
Recent starts and the imminent predicted XI inform the planner's minutes view;
future starts drift toward the season baseline. All those numerical choices
are heuristics, not measured calibration or independent evidence of an edge.

Check opponent, home/away, gameweek **and priced date** before using odds.
Never apply a separate home advantage on top of one already in the fixture.
The model's double-gameweek handling is deliberately absent. A confirmed blank
is zero; missing or mismatched projections are unknown and must block model-led
action. A star's old stats can be stale after a club, manager, role or penalty
taker change. The headline model does not fully capture those changes, cup
workload, new signings or exact return dates. Review them explicitly.

The history-based own-team scorer differs from the bootstrap transfer scorer.
Do not sell a player because those two different scoring systems disagree by a
point. Never infer an accurate probability from the captaincy radar's shape.
The radar's top recommendation itself is sorted by expected points.

## Initial squad construction

- Plan over 4, 6 and 8 weeks; give nearer weeks more weight. The initial
  comparison discounts later weeks by 0.9 per week, uses each week's best legal
  XI and doubles its best captain. Bench contributions use the existing
  planner's small weights; these are planning allowances, not simulated autosubs.
- Compare ordinary seeds with captain-emphasised seeds. A £15m forward competes
  with the entire squad he displaces, not only another forward. Price-per-point
  rankings alone underprice captaincy and overfill the squad with cheap players.
- Prefer starters with secure roles, at least one useful outfield first sub,
  and cheap remaining cover. Paying for fifteen equal stars wastes bench money;
  buying non-players leaves an avoidable failure during congestion. A cheap
  second GK should ideally play, but do not spend £1m to insure one week cheaply.
- Candidate seeds initially require 180+ minutes, 2+ season starts and 2 of the
  last 3 starts; exclude current doubts/known predicted substitutes. This is a
  deliberately conservative **initial-screen rule**, not a permanent prohibition
  on a newly promoted starter. Review omitted high-upside/new-role candidates.
- Compare using £99.5m and £100m limits. Cash is useful flexibility, not a target
  worth sacrificing clear points for. A good 0.5m buffer protects against price
  movements but no rise is guaranteed. Reprice the complete fifteen on entry.
- Check all 15 unique IDs, 2/5/5/3 quotas, max-three clubs and exact integer
  prices. Choose XI/bench/armbands separately for GW9. Never auto-pick and call
  it a researched team. No preseason WC/FH is needed for an initial squad.

Heuristic seeds are not a global optimum. Inspect alternatives, structural
costs and model sensitivity. An attractive projection cannot overrule a current
injury, confirmed benching, registration problem or unaffordable live price.

## Weekly decisions

**Roll is a real action.** Recompute the no-transfer baseline first. A free
transfer is valuable optionality: compare a one-move gain with keeping it for a
pair or future injury. Do not spend one automatically every week. At five banked
FTs, the next accrual has less option value; still reject a negative move.

For a buy/sell: evaluate the whole resulting squad and its best XIs/captains over
4–8 weeks, using actual sale proceeds, budget, club slots and future flexibility.
Paired moves share one budget; never add two isolated gains. The existing
planner's 3-point margin per move and 1.5-point terminal FT value are a screening
aid, not scientifically tuned thresholds. Prefer a robust gain across reasonable
minutes/fixture assumptions over a fractionally higher mean in one model run.
Until authority expands, reject all proposed hits regardless of model score.

Do not buy after a haul merely for points already scored. Inspect the role and
underlying chances. A good player blanking twice with intact minutes/role is
normally a hold. An injured, suspended or persistently dropped expensive starter
is a genuine problem. A cheap reserve does not need an upgrade while he remains
on the bench. Do not replace an enabler with expensive cover without measuring
the lost starter elsewhere.

Captain: highest credible expected points among owned starters; explicit review
of fitness, chance of 60+, penalties, fixture and recent role. Vice must be a
different owned starter and should have independent availability where close.
Avoid selecting two armbands from one uncertain postponed fixture if a similar
alternative exists. Bench order follows expected usable points **and** formation
cover. Do not bench an attacker just because the opposing GK/DEF is owned.

## Timing and operating routine

Availability triggers and review completion bookkeeping are defined in
`startup-operation.md`. Routine reviews aim for three per week with extra
deadline checks; the Windows task and daily fallback share one due guard.
These timings below describe desired review stages when the laptop, app and
authenticated browser are available, not guaranteed executions.

- After each GW: reconcile confirmed scores/holdings; record transfers and chips,
  investigate meaningful minutes/role surprises, refresh the next 8-week picture.
- Midweek: monitor injuries, suspensions, cup/European minutes and price risk.
  Treat scheduled publication as best-effort, not a promise of source freshness.
- Around 24h before deadline: provisional XI, captain, watchlist and transfer
  decision; identify unresolved press conferences and minimum required checks.
- Around 3h before: refresh inputs and execute defensible transfers after major
  team news where possible. Delay an uncertain move rather than letting an old
  model force it; an early price-sensitive move needs explicit documented benefit.
- Around 60 minutes before the **FPL deadline**, not kickoff: final saved-lineup
  check, legal bench order, captain/vice, chip status and news. Start early enough
  to tolerate browser failures; do not rely on a last-minute save.
- After the deadline: verify the published week once available; no attempt to
  change locked current-week results. During matches, record relevant news only.

Cadence must follow `deadline_time`, including midweek/holiday rounds and UK
clock changes. A schedule needs an actual unattended test and a verified account
write before it can be described as managing the account automatically.

## Chips and season transitions

Maintain a live chip ledger. WC when a squad-wide restructure beats incremental
repair over a window after accounting for future fixture swings. FH when a
temporary blank/double opportunity beats keeping the permanent squad. BB when
the marginal four actually have starts and fixtures; include the transfers/cash
needed to build and unwind the bench. TC compares the extra **single captain
share** now against remaining opportunities and minutes uncertainty.

With eight total chips, saving everything for a hypothetical double can waste
the first set. Beginning at GW9 leaves GW9–19 for first-half BB/TC and GW10–19
for WC/FH, subject to the live account's eligibility. Review before GW12, resolve
an actual first-half chip plan by GW15, then re-evaluate each deadline. These are
review gates, not a commitment to a dated chip. First-half expiry is tied to
GW19's live deadline; January resets need verification. Second-half planning
uses confirmed cup-driven blanks/doubles, not rumours or a fixture list with
postponements forced into arbitrary weeks. Use manual per-fixture comparison
for doubles until a separately authorised validated model exists.

## Safe execution and recovery

1. Confirm correct signed-in account; compare current UI against the last saved
   ledger. If another person changed it, analyse the actual new state.
2. Prepare the complete action; check live prices/allowances/deadline, legality,
   no hit/chip outside authority and that source quality supports the decision.
3. Record intent before a consequential submission. Submit once.
4. Reload/inspect the saved team; record actual IDs, roles, bank, FT/chip state
   and verification time. A click or success toast alone is insufficient.
5. On timeout, inspect the real state **before retrying**. Never repeat an
   uncertain transfer blindly. If authentication/coverage is unavailable, keep
   the last confirmed legal squad, record the blocker and notify Jonno once.
6. No unverified unattended transfer endpoint, browser-token extraction or
   transfer-via-GitHub-comment workaround. Existing alert tooling is scoped to
   a different configured account until proven otherwise; do not repoint it.

## Evaluation and memory

Before each deadline save forecast, inputs/read times, rationale, no-action
alternative and exact submitted state. After final scoring compare outcomes
with that frozen forecast; never rewrite an old prediction using new knowledge.
Track FT/hit/chip use, available starters, avoidable zeroes, captain opportunity
cost and points versus the frozen baseline. A single bad outcome does not prove
a bad decision; consistent forecast bias or missing news is a process problem.
Review monthly and at January reset. Do not tune model weights on the same few
weeks used to judge improvement; the research audit found no established
predictive lift or calibrated uncertainty.
