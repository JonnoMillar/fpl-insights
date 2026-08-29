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


def wildcard(ctx, all_reports, proj, market, baselines, next_gw, budget):
    """The best full-squad rebuild available right now, scored over the
    chip window (a permanent change needs a run of fixtures, not one
    week) and diffed against the current squad in sell/buy pairs, ranked
    by price so the story reads most-expensive-change-first.

    Known limitation, found live-testing this against a real squad: the
    objective is flat expected points across 11 players, with no idea
    that a real captain scores double. That blind spot systematically
    undervalues an explosive, spiky-ceiling premium (a Haaland) against
    steadier mid-price options, and can suggest selling exactly the
    player worth keeping for the armband alone. Shipped with this noted
    rather than fixed, since a captaincy-aware objective is a real change
    to the algorithm, not a tweak - treat any "sell your premium" move
    here with that in mind rather than as the final word."""
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
