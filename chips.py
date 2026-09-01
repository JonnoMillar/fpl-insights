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


def build_pool(ctx, proj, market, baselines, start_gw, weeks, exclude_ids=(),
              case_weighted=False):
    """The whole-league candidate pool, windowed-scored and squadbuilder-
    shaped: {"id", "pos", "club", "price", "value"}. Excludes anyone
    unfit to be suggested at all (transfers._eligible - injured,
    suspended, or ruled out of the predicted lineup) and anyone whose
    start_probability is too low to be worth a squad slot regardless of
    rate stats.

    `case_weighted` adds the same form/underlying-numbers nudge
    transfers.case_score adds on top of a windowed points total - on for
    Wildcard, which wants the same weighing as an individual transfer;
    off for Free Hit and the literal-best-XI card, which are deliberately
    pure points with nothing else mixed in.

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
        if case_weighted:
            factors = transfers.player_case_factors(el, ctx)
            total += (transfers.FORM_CASE_WEIGHT * factors["form"]
                      + transfers.EXPECTED_CASE_WEIGHT * factors["expected"])
        pool.append({
            "id": pid, "pos": ctx.pos(el), "club": ctx.team_name(el["team"]),
            "price": el["now_cost"] / 10.0, "value": total,
        })
    return pool


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


def _club_capped_xi(gks, defs, mids, fwds, d, m, fw,
                    club_cap=transfers.SQUAD_LIMIT_PER_CLUB):
    """The highest-value eleven for one fixed formation, subject to the
    real 3-per-club squad rule - not just formation rules.

    Each position list arrives pre-sorted by descending value. Picking the
    top N per position independently (as a no-club-cap version can) can
    put nine players from one club on the same page, which is not a squad
    anyone can actually own. This instead walks all four position pointers
    together and, at each step, takes whichever remaining candidate has the
    single highest value across every position that still has a quota to
    fill - skipping (not permanently discarding) anyone whose club has
    already hit the cap. Because ties always resolve to the highest value
    first, a club that is "maxing out" is, by construction, represented by
    its own best 3 - never an arbitrary 3.

    A pure greedy rather than a proven-optimal solver: the position quota
    and the club cap are two separate constraints, and jointly optimizing
    both exactly is a harder problem than either alone. Good enough for a
    "what if points were all that mattered" card, not offered as a proof
    of the single best possible eleven."""
    quotas = {"GKP": 1, "DEF": d, "MID": m, "FWD": fw}
    pools = {"GKP": gks, "DEF": defs, "MID": mids, "FWD": fwds}
    ptrs = {pos: 0 for pos in quotas}
    club_counts = {}
    picks = []
    needed = sum(quotas.values())
    while len(picks) < needed:
        best_pos, best_p = None, None
        for pos, need in quotas.items():
            if need <= 0:
                continue
            pool = pools[pos]
            ptr = ptrs[pos]
            while ptr < len(pool) and club_counts.get(pool[ptr]["club"], 0) >= club_cap:
                ptr += 1
            ptrs[pos] = ptr
            if ptr >= len(pool):
                continue
            if best_p is None or pool[ptr]["value"] > best_p["value"]:
                best_pos, best_p = pos, pool[ptr]
        if best_pos is None:
            return None
        picks.append(best_p)
        quotas[best_pos] -= 1
        ptrs[best_pos] += 1
        club_counts[best_p["club"]] = club_counts.get(best_p["club"], 0) + 1
    return picks


def literal_best_xi(ctx, xi_reports, proj, market, baselines, gw):
    """The highest-scoring valid eleven in the whole game, one week only -
    formation rules AND the real 3-per-club squad limit, but no budget
    (nobody's actual price point).

    This is a different question from points_team's "ideal", which is
    deliberately budget-capped at the manager's own XI value because it
    feeds the Free Hit gap - a chip you would actually play, so the
    comparison has to be a squad you could actually afford. The dashboard's
    "Highest predicted points XI" card is a different, unconstrained-on-
    price question ("what if points were all that mattered"), and reusing
    the budget-capped number there quietly answered the wrong question: a
    manager with a modest squad value saw a "best XI" that wasn't the best
    XI in the game at all, just the best one at his own price point.

    The club cap still applies even here, though - it is a squad-legality
    rule, not a budget one, and dropping it produced elevens with most of
    one club's attack on the page at once, which nobody can actually field.
    See _club_capped_xi for how a fixed formation is filled under it."""
    pool = build_pool(ctx, proj, market, baselines, gw, weeks=1)
    by_pos = {}
    for p in pool:
        by_pos.setdefault(p["pos"], []).append(p)
    for lst in by_pos.values():
        lst.sort(key=lambda p: -p["value"])
    gks, defs, mids, fwds = (by_pos.get("GKP", []), by_pos.get("DEF", []),
                             by_pos.get("MID", []), by_pos.get("FWD", []))

    best = None
    for d in range(3, 6):
        for m in range(2, 6):
            for fw in range(1, 4):
                if 1 + d + m + fw != 11:
                    continue
                if len(gks) < 1 or len(defs) < d or len(mids) < m or len(fwds) < fw:
                    continue
                picks = _club_capped_xi(gks, defs, mids, fwds, d, m, fw)
                if picks is None:
                    continue
                total = sum(p["value"] for p in picks)
                if best is None or total > best["value"]:
                    best = {"value": total, "xi": picks}

    ours_value = 0.0
    for r in xi_reports:
        ep = analysis.expected_points(r, ctx, proj, gw, market=market,
                                      baselines=baselines)
        ours_value += ep["total"] if ep else 0.0

    if best is None:
        return {"ideal_value": ours_value, "ours_value": ours_value,
                "gap": 0.0, "ideal_xi": []}
    return {
        "ideal_value": best["value"], "ours_value": ours_value,
        "gap": max(0.0, best["value"] - ours_value),
        "ideal_xi": best["xi"],
    }


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
    others = [c[2] for c in candidates if c is not best]
    return {
        "player": best[0], "gw": best[1], "ep": best[2],
        "confidence": confidence(best[2], others),
    }


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
    (transfers.windowed_candidate_score, plus the same form/underlying-
    numbers nudge transfers.case_score adds to a single transfer) -
    previously the own squad was scored by analysis.windowed_ep, a richer,
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
                      exclude_ids=exclude_ids, case_weighted=True)
    own_pool = []
    for r in all_reports:
        total, _per_gw = transfers.windowed_candidate_score(
            r.element, ctx, proj, market, baselines, priors, start, weeks)
        factors = transfers.player_case_factors(r.element, ctx)
        total += (transfers.FORM_CASE_WEIGHT * factors["form"]
                  + transfers.EXPECTED_CASE_WEIGHT * factors["expected"])
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
    current_best = squadbuilder.best_xi(own_pool, budget=1e9)
    current_value = current_best["value"] if current_best else 0.0

    gap = max(0.0, ideal["value"] - current_value)

    before = (_xi_stats(current_best["xi"], ctx, proj, market, start, weeks)
              if current_best else None)
    after = _xi_stats(ideal["xi"], ctx, proj, market, start, weeks)

    ideal_ids = {p["id"] for p in ideal["xi"] + ideal["bench"]}
    current_ids = {r.element["id"] for r in all_reports}

    return {
        "gw_window": (start, weeks), "gap": gap,
        "confidence": confidence(ideal["value"], [current_value]),
        "before": before, "after": after,
        # The proposed fifteen itself (pool-shaped: id/pos/club/price/value),
        # for the dashboard's own mini-pitch view - "before" is just the
        # manager's real squad, which the caller already has as full
        # PlayerReports and has no need to get back from here.
        "ideal_xi": ideal["xi"], "ideal_bench": ideal["bench"],
        "incoming_ids": {p["id"] for p in ideal["xi"] + ideal["bench"]
                         if p["id"] not in current_ids},
    }
