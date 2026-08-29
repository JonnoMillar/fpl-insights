#!/usr/bin/env python3
"""
Suggested transfers.

The honest caveat first, because it governs the whole design: one gameweek of
player data is not enough to trust a recommendation. What follows is therefore
built to be *inspectable* rather than obeyed - every suggestion shows the
projection on both sides and the money it costs, so you can see why it was
made and dismiss it when it is obviously daft. As the season lengthens the
same machinery gets better without changing.

Two constraints shape the implementation:

* **No extra API calls per candidate.** Scoring six hundred players by pulling
  each one's match history would be six hundred requests. Everything here is
  computed from the bootstrap payload, which is one request for the lot, at
  the cost of approximating the two fields that normally come from history.
* **Selling price is unknown.** FPL sell a player back at purchase price plus
  half the rise, and purchase price only exists behind a login. Current price
  is used instead, so a long-held riser is worth slightly less than shown.
  Stated wherever the numbers appear.
"""

import analysis
from analysis import f, per90

SQUAD_LIMIT_PER_CLUB = 3

# Minutes of prior belief mixed into every rate. At 90 minutes played a
# player's own numbers carry about an eighth of the weight and the positional
# average the rest, which is the correct humility one match into a season:
# a defender who scored in gameweek one is not a 0.9-goals-per-90 defender.
PRIOR_MINUTES = 600.0


def positional_priors(ctx):
    """Minutes-weighted mean rates per position, from the league itself.

    Derived rather than hardcoded so it tracks whatever this season turns out
    to be, and stable even now because it averages over a hundred-odd players
    per position rather than one."""
    acc = {}
    for el in ctx.players.values():
        mins = el.get("minutes", 0)
        if mins <= 0:
            continue
        pos = ctx.pos(el)
        a = acc.setdefault(pos, {"min": 0.0, "xg": 0.0, "xa": 0.0, "bonus": 0.0,
                                 "dc": 0.0, "bps": 0.0})
        a["min"] += mins
        a["xg"] += f(el.get("expected_goals"))
        a["xa"] += f(el.get("expected_assists"))
        a["bonus"] += el.get("bonus", 0)
        a["dc"] += el.get("defensive_contribution", 0)
        a["bps"] += analysis.other_bps_per90(el, ctx, mins) * mins / 90.0
    priors = {}
    for pos, a in acc.items():
        m = a["min"] or 1.0
        priors[pos] = {
            "xg90": per90(a["xg"], m), "xa90": per90(a["xa"], m),
            "bonus90": per90(a["bonus"], m), "dc90": per90(a["dc"], m),
            "bps90": per90(a["bps"], m),
        }
    return priors


def _shrink(rate, minutes, prior):
    """Pull a rate toward the positional average in proportion to how little
    football it is based on."""
    return (rate * minutes + prior * PRIOR_MINUTES) / (minutes + PRIOR_MINUTES)


def candidate_score(el, ctx, proj, gw, market, baselines, priors=None,
                    league_avg=1.45):
    """Expected points for any player, from the bootstrap payload alone.

    Mirrors analysis.expected_points, but `appearances` and the defensive
    threshold hit-rate normally come from match history. Starts stand in for
    appearances, and the hit rate is approximated from the season rate against
    the threshold - crude, but it only moves defenders and holding midfielders
    a fraction of a point."""
    pos = ctx.pos(el)
    club = ctx.team_name(el["team"])
    fixture = proj.get((club, gw))
    mk = (market or {}).get(club)
    if not fixture and not mk:
        return None

    minutes_played = el.get("minutes", 0)
    starts = el.get("starts", 0) or 0
    pred = ctx.is_predicted(el)
    if pred is True:
        minutes = 85.0
    elif pred is False:
        minutes = 15.0
    elif starts:
        minutes = min(90.0, minutes_played / max(1, starts))
    else:
        minutes = 30.0
    share = minutes / 90.0

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

    prior = (priors or {}).get(pos, {"xg90": 0.1, "xa90": 0.1, "bonus90": 0.25,
                                     "dc90": 4.0, "bps90": 12.0})
    xg90 = _shrink(per90(f(el.get("expected_goals")), minutes_played),
                   minutes_played, prior["xg90"])
    xa90 = _shrink(per90(f(el.get("expected_assists")), minutes_played),
                   minutes_played, prior["xa90"])
    other_bps90 = _shrink(analysis.other_bps_per90(el, ctx, minutes_played),
                          minutes_played, prior["bps90"])

    goals = xg90 * share * mult * analysis.GOAL_POINTS.get(pos, 4)
    assists = xa90 * share * mult * analysis.ASSIST_POINTS
    defence = cs_prob * analysis.CS_POINTS.get(pos, 0) * (1.0 if share > 0.65 else 0.0)
    appearance = 2.0 * share if minutes >= 60 else 1.0 * share

    threshold = analysis.DEFCON_THRESHOLD.get(pos)
    defcon = 0.0
    if threshold and minutes_played:
        rate = _shrink(per90(el.get("defensive_contribution", 0), minutes_played),
                       minutes_played, prior["dc90"])
        # A rate at the threshold does not mean he clears it every week; this
        # curve is a stand-in for the real hit rate, deliberately conservative.
        defcon = min(1.0, max(0.0, (rate / threshold) ** 2)) * analysis.DEFCON_POINTS * share
    bonus = analysis.expected_bonus(pos, share, goals / max(1e-9, analysis.GOAL_POINTS.get(pos, 4)),
                                    assists / analysis.ASSIST_POINTS, cs_prob,
                                    other_bps90, minutes)

    return {
        "total": goals + assists + defence + appearance + defcon + bonus,
        "goals": goals, "assists": assists, "defence": defence,
        "appearance": appearance, "defcon": defcon, "bonus": bonus,
        "cs": cs_prob * 100,
        "opponent": fixture.get("opp") if fixture else mk["opp"],
        "home": (fixture.get("ven") or "H").upper() == "H" if fixture else mk["home"],
        "priced": bool(mk),
    }


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


def _eligible(el, ctx):
    """Fit to be suggested at all."""
    if el.get("status") in ("u", "n"):
        return False
    chance = el.get("chance_of_playing_next_round")
    if chance is not None and chance < 50:
        return False
    if ctx.is_predicted(el) is False:
        return False
    return True


def pair_suggestions(ctx, squad_reports, proj, gw, market, baselines, bank=0.0,
                     shortlist=30, limit=4, elite=None, hit_cost=4):
    """Two out, two in - the moves a single transfer cannot reach.

    Pairs matter because the constraints interact. Selling one player frees
    money that makes a different upgrade affordable elsewhere; selling two
    from the same club opens a slot the three-per-club rule was blocking. A
    list of single transfers cannot see either of those.

    The rules being satisfied here:

    * **Shape.** A squad is fixed at 2 keepers, 5 defenders, 5 midfielders and
      3 forwards, so the positions going out must match the positions coming
      in. Nothing else keeps the squad legal.
    * **Money.** The bank plus both sale prices must cover both purchases.
      Sale price is taken as current price - the real figure needs a login.
    * **Three per club.** Checked after both sales and both purchases, since
      selling two from one club is exactly what makes a third signing legal.
    * **Distinct players.** Cannot buy the same man twice, or one already held.

    Search is bounded rather than exhaustive: every squad player keeps a
    shortlist of his best affordable replacements, and only those are paired.
    A full search over six hundred players squared is millions of combinations
    for no better answer.
    """
    squad_ids = {r.element["id"] for r in squad_reports}
    club_counts = {}
    for r in squad_reports:
        club_counts[r.element["team"]] = club_counts.get(r.element["team"], 0) + 1

    priors = positional_priors(ctx)
    scored = {}
    for el in ctx.players.values():
        if el["id"] in squad_ids or not _eligible(el, ctx):
            continue
        s = candidate_score(el, ctx, proj, gw, market, baselines, priors)
        if s:
            scored[el["id"]] = s

    elite_by_id = {}
    if elite:
        for row in elite.get("rows", []):
            elite_by_id[row["id"]] = row

    # Shortlist per squad player. The ceiling allows for money freed by the
    # other sale, so genuinely reachable upgrades are not filtered out early.
    here, shortlists = {}, {}
    for r in squad_reports:
        base = candidate_score(r.element, ctx, proj, gw, market, baselines, priors)
        if not base:
            continue
        here[r.element["id"]] = base
        ceiling = r.price + bank + 6.0
        options = []
        for pid, s in scored.items():
            el = ctx.players[pid]
            if ctx.pos(el) != r.pos:
                continue
            price = el["now_cost"] / 10.0
            if price > ceiling:
                continue
            gain = s["total"] - base["total"]
            if gain <= 0.05:
                continue
            options.append({"el": el, "score": s, "gain": gain, "price": price})
        options.sort(key=lambda o: -o["gain"])
        shortlists[r.element["id"]] = options[:shortlist]

    reports_by_id = {r.element["id"]: r for r in squad_reports}
    ids = [r.element["id"] for r in squad_reports if r.element["id"] in shortlists]

    pairings = []
    for i, a_id in enumerate(ids):
        for b_id in ids[i + 1:]:
            ra, rb = reports_by_id[a_id], reports_by_id[b_id]
            budget = bank + ra.price + rb.price
            # Freeing both slots before testing the club limit is the whole
            # point of looking at pairs.
            freed = dict(club_counts)
            freed[ra.element["team"]] -= 1
            freed[rb.element["team"]] -= 1

            best = None
            for oa in shortlists[a_id]:
                for ob in shortlists[b_id]:
                    if oa["el"]["id"] == ob["el"]["id"]:
                        continue
                    if oa["price"] + ob["price"] > budget + 1e-9:
                        continue
                    ta, tb = oa["el"]["team"], ob["el"]["team"]
                    if freed.get(ta, 0) + 1 > SQUAD_LIMIT_PER_CLUB:
                        continue
                    extra = 1 if ta == tb else 0
                    if freed.get(tb, 0) + 1 + extra > SQUAD_LIMIT_PER_CLUB:
                        continue
                    gain = oa["gain"] + ob["gain"]
                    if best is None or gain > best["gain"]:
                        best = {"gain": gain, "a": oa, "b": ob}
            if not best:
                continue
            spend = best["a"]["price"] + best["b"]["price"] - ra.price - rb.price
            pairings.append({
                "legs": [
                    {"out": ra, "out_score": here[a_id], "in": best["a"]["el"],
                     "in_score": best["a"]["score"], "gain": best["a"]["gain"],
                     "price": best["a"]["price"],
                     "spend": best["a"]["price"] - ra.price,
                     "elite": elite_by_id.get(best["a"]["el"]["id"])},
                    {"out": rb, "out_score": here[b_id], "in": best["b"]["el"],
                     "in_score": best["b"]["score"], "gain": best["b"]["gain"],
                     "price": best["b"]["price"],
                     "spend": best["b"]["price"] - rb.price,
                     "elite": elite_by_id.get(best["b"]["el"]["id"])},
                ],
                "gain": best["gain"],
                "spend": spend,
                "bank_after": bank - spend,
                "after_hit": best["gain"] - hit_cost,
            })

    pairings.sort(key=lambda p: -p["gain"])

    # One appearance per outgoing player across the whole list, so four
    # pairings read as four decisions rather than four ways of selling Konsa.
    used, picked = set(), []
    for p in pairings:
        outs = {leg["out"].element["id"] for leg in p["legs"]}
        if outs & used:
            continue
        used |= outs
        picked.append(p)
        if len(picked) >= limit:
            break
    return picked


def suggest(ctx, squad_reports, proj, gw, market, baselines, bank=0.0,
            per_slot=3, limit=6, elite=None):
    """Swaps worth a look: one out, one in, same position, affordable.

    Ranked on the gain in projected points for the coming gameweek, which is
    the shortest horizon there is - a longer view would need fixture runs
    weighted by how likely you are to still own him, and that is a bigger
    model than one gameweek of data deserves."""
    club_counts = {}
    squad_ids = set()
    for r in squad_reports:
        squad_ids.add(r.element["id"])
        club_counts[r.element["team"]] = club_counts.get(r.element["team"], 0) + 1

    priors = positional_priors(ctx)

    # Score the whole league once.
    scored = {}
    for el in ctx.players.values():
        if el["id"] in squad_ids or not _eligible(el, ctx):
            continue
        s = candidate_score(el, ctx, proj, gw, market, baselines, priors)
        if s:
            scored[el["id"]] = s

    elite_by_id = {}
    if elite:
        for row in elite.get("rows", []):
            elite_by_id[row["id"]] = row

    out_rows = []
    for r in squad_reports:
        # Deliberately the same scorer as the candidates. The richer model in
        # analysis.py blends a player's own last season, which candidates
        # cannot have without a request each - comparing the two would flatter
        # whichever side got the better treatment.
        here = candidate_score(r.element, ctx, proj, gw, market, baselines, priors)
        if not here:
            continue
        budget = r.price + bank
        pos = r.pos
        options = []
        for pid, s in scored.items():
            el = ctx.players[pid]
            if ctx.pos(el) != pos:
                continue
            price = el["now_cost"] / 10.0
            if price > budget + 1e-9:
                continue
            # Three-per-club: leaving this club frees a slot, joining fills one.
            count = club_counts.get(el["team"], 0)
            if el["team"] == r.element["team"]:
                count -= 1
            if count >= SQUAD_LIMIT_PER_CLUB:
                continue
            gain = s["total"] - here["total"]
            if gain <= 0.15:
                continue
            options.append({
                "element": el, "score": s, "gain": gain,
                "price": price, "spend": price - r.price,
                "elite": elite_by_id.get(pid),
            })
        options.sort(key=lambda o: -o["gain"])
        for opt in options[:per_slot]:
            out_rows.append({
                "out": r, "out_score": here,
                "in": opt["element"], "in_score": opt["score"],
                "gain": opt["gain"], "price": opt["price"],
                "spend": opt["spend"], "elite": opt["elite"],
            })

    out_rows.sort(key=lambda x: -x["gain"])

    # One suggestion per outgoing player, so the list reads as a set of
    # distinct decisions rather than five variations on selling the same man.
    seen, picked = set(), []
    for row in out_rows:
        key = row["out"].element["id"]
        if key in seen:
            continue
        seen.add(key)
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked
