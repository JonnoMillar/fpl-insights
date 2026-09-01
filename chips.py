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


def literal_best_xi(ctx, xi_reports, proj, market, baselines, gw):
    """The highest-scoring valid eleven in the whole game, one week only -
    formation rules only, no budget and no club cap.

    This is a different question from points_team's "ideal", which is
    deliberately budget-capped at the manager's own XI value because it
    feeds the Free Hit gap - a chip you would actually play, so the
    comparison has to be a squad you could actually afford. The dashboard's
    "Highest predicted points XI" card is a different, unconstrained
    question ("what if points were all that mattered"), and reusing the
    budget-capped number there quietly answered the wrong question: a
    manager with a modest squad value saw a "best XI" that wasn't the best
    XI in the game at all, just the best one at his own price point.

    With no budget or club constraint, the optimal team for a fixed
    formation is simply the top N scorers at each position - so trying
    every legal formation (~40 of them) and keeping the best total is
    exact, not approximate."""
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
                picks = gks[:1] + defs[:d] + mids[:m] + fwds[:fw]
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
    here with that in mind rather than as the final word."""
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

    before = (_xi_stats(current_best["xi"], ctx, proj, market, start, weeks)
              if current_best else None)
    after = _xi_stats(ideal["xi"], ctx, proj, market, start, weeks)

    ideal_ids = {p["id"] for p in ideal["xi"] + ideal["bench"]}
    current_ids = {r.element["id"] for r in all_reports}
    outgoing = [own_reports_by_id[pid] for pid in current_ids - ideal_ids]
    incoming = [ctx.players[pid] for pid in ideal_ids - current_ids]

    # Pair within position, never across it. Both squads are 2/5/5/3 by
    # construction (squadbuilder fills exactly those quotas), so the two
    # sides have equal counts in every position and the zip below is total.
    # Sorting the two flat lists by price and zipping them - which is what
    # this used to do - produced legal *squads* but nonsense *pairs*: the
    # most expensive man leaving read as replaced by the most expensive man
    # arriving, so a forward "became" a midfielder on screen whenever the
    # price order happened to cross positions.
    by_pos_out, by_pos_in = {}, {}
    for r in outgoing:
        by_pos_out.setdefault(r.pos, []).append(r)
    for el in incoming:
        by_pos_in.setdefault(ctx.pos(el), []).append(el)

    pairs = []
    for pos, outs in by_pos_out.items():
        ins = by_pos_in.get(pos, [])
        outs.sort(key=lambda r: -r.price)
        ins.sort(key=lambda el: -(el["now_cost"] / 10.0))
        if len(outs) != len(ins):
            # Defensive: a pool too thin to fill a quota can leave these
            # uneven. Pair what is pairable rather than dropping the lot.
            print(f"[chips] wildcard {pos}: {len(outs)} out vs {len(ins)} in")
        pairs.extend(zip(outs, ins))
    # Most expensive change first, as before - now across matched pairs.
    pairs.sort(key=lambda p: -p[0].price)

    # Each move is built display-ready here, in the shape
    # components.transfer_cards already expects (out_score/in_score need
    # "total", "opponent", "home"; in_club is separate from in_score) -
    # scored at the window's first gameweek, real numbers rather than
    # placeholders, so the reused card shows an honest fixture and gain
    # per move instead of a flat, meaningless bar.
    moves = []
    for out_r, in_el in pairs:
        in_full = analysis.build_player(ctx, in_el["id"], ttl=fplapi.DEFAULT_TTL)
        # Same scorer both sides here too - out_r has match history and
        # in_el doesn't, so analysis.expected_points against
        # transfers.candidate_score would flatter whichever man got the
        # richer model on a card whose whole point is comparing the two.
        out_score = transfers.case_score(
            out_r.element, ctx, proj, start, market, baselines, priors
        ) or {"total": 0.0, "opponent": "-", "home": True}
        in_score = transfers.case_score(
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
        "moves": moves, "before": before, "after": after,
    }
