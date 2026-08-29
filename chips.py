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
