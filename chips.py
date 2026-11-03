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
import ticker
import transfers
from analysis import f

# Starting guesses, not a validated calibration - there is no data yet on
# how these gaps are actually distributed across a real season. Revisit
# once the recommender has run for a few gameweeks. Re-tuned for a
# runner-up comparison (L9): the mean of a dozen-plus rejected candidates
# these used to be checked against sits far below any of them, so the
# maximum was "strong" almost by construction and the pill carried no
# information. The runner-up is a much harder bar to clear.
CONFIDENCE_STRONG = 0.15
CONFIDENCE_WATCH = 0.05


def confidence(best_value, runner_up):
    """How much better the recommended pick is than its closest rival, as
    a plain-language read rather than a bare percentage.

    Compared against the runner-up, not the mean of every other candidate
    (L9) - the best of many candidates is, by construction, comfortably
    above their average, so a mean comparison always read "Strong"
    regardless of how close the actual second-best pick was. `runner_up`
    is `None` when there was only one candidate to begin with."""
    if runner_up is None:
        return "flexible"
    if runner_up <= 0:
        return "strong" if best_value > 0 else "flexible"
    lift = (best_value - runner_up) / runner_up
    if lift >= CONFIDENCE_STRONG:
        return "strong"
    if lift >= CONFIDENCE_WATCH:
        return "watch"
    return "flexible"


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


def build_pool(ctx, proj, market, baselines, start_gw, weeks, exclude_ids=()):
    """The whole-league candidate pool, windowed-scored and squadbuilder-
    shaped: {"id", "pos", "club", "price", "value"}. Excludes anyone
    unfit to be suggested at all (transfers._eligible - injured,
    suspended, or ruled out of the predicted lineup) and anyone whose
    start_probability is too low to be worth a squad slot regardless of
    rate stats.

    Pure windowed points, for every caller including Wildcard (L7): the
    form/underlying-numbers nudge transfers.case_score adds on top of that
    for a single transfer decision used to be mixed in here too, but that
    nudge is a cross-position adjustment (it penalises defenders and
    keepers against midfielders and forwards) and a formation choice is
    exactly the place a cross-position bias cannot be allowed to leak in.

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


def points_team(ctx, xi_reports, proj, market, baselines, gw, budget):
    """The highest-scoring possible team this gameweek, against what the
    manager's own current best XI actually projects to - single week
    only, since this is also Free Hit's one-week evidence.

    `budget` is the whole-squad sell value (15 players) plus the bank - what
    a Free Hit actually spends (L3). The manager's own current XI price is
    not that budget: it is roughly the sell value minus a cheap bench,
    which understates what a Free Hit XI can actually cost by however much
    the bench is worth, and made the "ideal" team look artificially weak."""
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


def free_hit(ctx, xi_reports, proj, market, baselines, next_gw, budget):
    """The gameweek in the current chip window where the manager's own XI
    is furthest behind the best possible team - the Free Hit case.

    `budget` is the whole squad's sell value plus the bank (L3) - what a
    Free Hit actually spends, not the current XI's own price."""
    start, weeks = analysis.chip_window(next_gw)
    gaps = {}
    pt_by_gw = {}
    for gw in range(start, start + weeks):
        pt = points_team(ctx, xi_reports, proj, market, baselines, gw, budget)
        gaps[gw] = pt["gap"]
        pt_by_gw[gw] = pt
    if not gaps:
        return None
    best_gw = max(gaps, key=gaps.get)
    runner_up = max((v for gw, v in gaps.items() if gw != best_gw), default=None)
    return {
        "gw": best_gw, "gap": gaps[best_gw],
        "confidence": confidence(gaps[best_gw], runner_up),
        # The whole window, so the card can show whether the recommended week
        # is a spike worth waiting for or the flat top of a plateau. One
        # number and one gameweek cannot tell those apart, and they call for
        # opposite decisions.
        "series": sorted(gaps.items()),
        "points_team": pt_by_gw[best_gw],
        # Every week's ideal team, not just the winning one. The dashboard's
        # "highest predicted points XI" card wants the *coming* gameweek
        # specifically, which is rarely the same week Free Hit picks, and
        # recomputing it would mean building the whole candidate pool a
        # second time for a number already sitting in this loop.
        "by_gw": pt_by_gw,
    }


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
    runner_up = max((c[2] for c in candidates if c is not best), default=None)
    per_gw = {}
    for _r, gw, total in candidates:
        if total > per_gw.get(gw, 0.0):
            per_gw[gw] = total
    return {
        "player": best[0], "gw": best[1], "ep": best[2],
        "confidence": confidence(best[2], runner_up),
        "series": sorted(per_gw.items()),
    }


def bench_boost(ctx, bench_reports, proj, market, baselines, next_gw, bank=0.0,
                full_squad=None, sell_values=None):
    """Best week for the current bench, plus one affordable legal upgrade."""
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
    runner_up = max((v for gw, v in totals.items() if gw != best_gw), default=None)

    # transfers.suggest computes its own positional_priors internally -
    # nothing else needed here. xi_based=False: the bench itself is what's
    # being scored here, not a full 15, so there is no best XI to measure a
    # swap against - and the bench genuinely does play this specific week,
    # so its own raw gain is the right question (L2).
    suggestions = transfers.suggest(
        ctx, bench_reports, proj, best_gw, market, baselines,
        bank=bank, per_slot=1, limit=1, xi_based=False,
        full_squad=full_squad, sell_values=sell_values)
    for t in suggestions:
        t["in_club"] = ctx.team_name(t["in"]["team"])

    return {
        "gw": best_gw, "ep": totals[best_gw],
        "confidence": confidence(totals[best_gw], runner_up),
        "series": sorted(totals.items()),
        "transfers": suggestions,
    }


def _xi_stats(xi_pool, ctx, proj, market, next_gw, weeks):
    """xP, season xGI, form and mean fixture rating across an XI - the
    before/after the Wildcard card compares, since "here are fifteen
    swaps" answers a different question from "is this actually better,
    and by how much on the numbers that matter". `xi_pool` is
    squadbuilder's own {"id","pos","club","price","value"} shape."""
    xgi = form = fixture_total = 0.0
    fixture_n = 0
    for p in xi_pool:
        el = ctx.players[p["id"]]
        xgi += f(el.get("expected_goal_involvements"))
        form += f(el.get("form"))
        cells = ticker._rows_for(p["club"], proj, market, next_gw, weeks)
        if cells:
            fixture_total += sum(c["score"] for c in cells) / len(cells)
            fixture_n += 1
    return {
        "xp": sum(p["value"] for p in xi_pool),
        "xgi": xgi, "form": form,
        "fixture": fixture_total / fixture_n if fixture_n else 0.0,
    }


def wildcard(ctx, all_reports, proj, market, baselines, next_gw, budget):
    """The best full-squad rebuild available right now, scored over the
    chip window (a permanent change needs a run of fixtures, not one
    week) and diffed against the current squad in sell/buy pairs, ranked
    by price so the story reads most-expensive-change-first.

    Own players and candidates are scored by the identical function
    (transfers.windowed_candidate_score, pure windowed points - see
    build_pool for why the case_score form/underlying-numbers nudge is not
    mixed in here, L7) - previously the own squad was scored by
    analysis.windowed_ep, a richer,
    match-history-backed model, while candidates got the cheaper
    bootstrap-only one. transfers.suggest already avoids exactly that
    asymmetry for single transfers with a comment explaining why; wildcard
    didn't, and the result was a rebuild that read as "sell everyone" far
    more often than the numbers actually supported - whichever side of
    that mismatch scored systematically higher always won, real quality
    aside. One scorer for both sides means an own player who is still
    genuinely one of the best in his position and price range now gets
    kept, rather than out-competed by a candidate measured on a different
    scale.

    Known limitation, found live-testing this against a real squad: the
    objective is flat expected points across 11 players, with no idea
    that a real captain scores double. That blind spot systematically
    undervalues an explosive, spiky-ceiling premium (a Haaland) against
    steadier mid-price options, and can suggest selling exactly the
    player worth keeping for the armband alone. Shipped with this noted
    rather than fixed, since a captaincy-aware objective is a real change
    to the algorithm, not a tweak - treat any "sell your premium" move
    here with that in mind rather than as the final word.

    Owned players also get a retention margin added to their value for the
    search only (see below), so a candidate has to beat an incumbent by a
    real amount, not just any amount, to displace him. Without it, the
    "rebuild" routinely swapped nearly the whole fifteen - almost none of
    it a move worth an actual transfer hit, just whichever side of a
    fractional-point tie happened to win at every single position."""
    start, weeks = analysis.chip_window(next_gw)
    exclude_ids = {r.element["id"] for r in all_reports}
    priors = transfers.positional_priors(ctx)
    pool = build_pool(ctx, proj, market, baselines, start, weeks,
                      exclude_ids=exclude_ids)
    own_pool = []
    for r in all_reports:
        total, _per_gw = transfers.windowed_candidate_score(
            r.element, ctx, proj, market, baselines, priors, start, weeks)
        own_pool.append({"id": r.element["id"], "pos": r.pos, "club": r.team,
                         "price": r.price, "value": total})
    full_pool = pool + own_pool

    # squadbuilder optimizes on value alone, with no notion of who is
    # already owned - so any candidate who edges out an incumbent by even
    # a fraction of a point displaces him, and a real squad of fifteen
    # rarely has zero such fractional edges lying around. That produced a
    # "rebuild" that swapped nearly the whole fifteen most weeks, most of
    # it churn no manager would actually pay a hit for, rather than the
    # handful of genuine upgrades the card is supposed to surface. A
    # retention margin - the same per-week bar the Sell column already
    # holds a transfer to - is added to owned players for this search only,
    # so a candidate has to beat the incumbent by a real amount, not just
    # any amount, to take his place. The margin is stripped back out again
    # below before anything is reported, so xP, the gap and every move's
    # gain are still the true numbers, not the boosted ones used to choose.
    retention_margin = (transfers.SELL_MARGIN / transfers.TRANSFER_HORIZON_WEEKS
                        * weeks)
    own_ids = {p["id"] for p in own_pool}
    search_pool = [dict(p) for p in full_pool]
    for p in search_pool:
        if p["id"] in own_ids:
            p["value"] += retention_margin

    # The single highest-value owned player gets a further, larger premium
    # for the same reason the docstring's captaincy blind spot names him
    # specifically: whoever owns the squad's best player almost certainly
    # captains him, so he is actually earning double his own total most
    # weeks, not the flat total this whole objective scores everyone on.
    # Without any allowance for that, a genuine premium (Haaland, on the
    # squad this was built against) got sold for a stack of cheaper
    # upgrades elsewhere that only looked net-positive because the model
    # never credited him with the extra copy of his own points he already
    # earns. Half his own windowed value again, added only for this
    # search, is not a fitted number - just enough that beating him
    # outright takes a real case, not a fractional one.
    CAPTAIN_PREMIUM_FRAC = 0.5
    if own_pool:
        likely_captain = max(own_pool, key=lambda p: p["value"])
        premium = CAPTAIN_PREMIUM_FRAC * likely_captain["value"]
        for p in search_pool:
            if p["id"] == likely_captain["id"]:
                p["value"] += premium

    ideal = squadbuilder.best_squad(search_pool, budget)
    if ideal is None:
        return None
    true_by_id = {p["id"]: p for p in full_pool}
    ideal["xi"] = [true_by_id[p["id"]] for p in ideal["xi"]]
    ideal["bench"] = [true_by_id[p["id"]] for p in ideal["bench"]]
    ideal["value"] = sum(p["value"] for p in ideal["xi"])

    # Compare like for like: the manager's own best XI over the same
    # window, formation-optimized the same way points_team finds one for
    # a single week - budget is unconstrained here since these 15 are
    # already owned, only which 11 of them to start is being decided.
    current_best = squadbuilder.owned_xi(own_pool)
    current_value = current_best["value"] if current_best else 0.0

    gap = max(0.0, ideal["value"] - current_value)

    before = (_xi_stats(current_best["xi"], ctx, proj, market, start, weeks)
              if current_best else None)
    after = _xi_stats(ideal["xi"], ctx, proj, market, start, weeks)

    ideal_ids = {p["id"] for p in ideal["xi"] + ideal["bench"]}
    current_ids = {r.element["id"] for r in all_reports}

    return {
        "gw_window": (start, weeks), "gap": gap,
        "confidence": confidence(ideal["value"], current_value),
        "before": before, "after": after,
        # The proposed fifteen itself (pool-shaped: id/pos/club/price/value),
        # for the dashboard's own mini-pitch view - "before" is just the
        # manager's real squad, which the caller already has as full
        # PlayerReports and has no need to get back from here.
        "ideal_xi": ideal["xi"], "ideal_bench": ideal["bench"],
        "incoming_ids": {p["id"] for p in ideal["xi"] + ideal["bench"]
                         if p["id"] not in current_ids},
    }
