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

# Minutes of prior belief mixed into every rate, keeping a defender who
# scored in gameweek one from reading as a 0.9-goals-per-90 defender.
#
# Was 600, which left a player's own numbers carrying under a quarter of the
# weight two matches in. That much humility had a cost the original note did
# not anticipate: with everyone flattened onto the same prior, nothing about
# the players themselves could separate them and the fixture multiplier
# became the only thing the ranking actually responded to. 400 still leans
# on the prior, but a genuine hot streak can now outweigh a kind fixture,
# and the price-aware prior below means the thing being shrunk toward is a
# far better guess than it was.
PRIOR_MINUTES = 400.0

# Price is what stops a premium being judged against a bench-warmer. A 14.0m
# forward and a 4.5m forward share a position and nothing else, so shrinking
# both toward one "average forward" rate is the wrong prior for each: it
# flatters the cheap player and buries the expensive one.
#
# Fitted as a line through price rather than cut into bands. Bands were tried
# first and could not separate the top: FPL prices are dense at the bottom
# and long-tailed at the top, so any quantile cut puts a 14.0m striker and a
# 6.5m squad man in one bucket with one prior. A line has no such boundary
# and extrapolates sensibly to the handful of players above every cut.
#
# Weighted by minutes, so regular starters set the slope and a cameo does
# not. Floored well below any real rate so the fit can never hand out a
# negative expectation at the cheap end.
RATE_FLOOR = 0.01

# How much of the attacking rate comes from expected goals rather than the
# goals actually scored. xG is the better predictor and stays the majority
# of the signal, but ignoring real returns entirely - which is what this
# used to do - means a player who keeps scoring is never credited for it.
XG_WEIGHT = 0.75

# A player with no football behind him this season is not evidence of an
# average starter; he is evidence of nothing. Below this many minutes his
# expected involvement is tempered toward a squad player's, however
# confidently a predicted-lineup feed names him. Roughly two full matches.
EVIDENCE_MINUTES = 180.0


def _acc_new():
    return {"min": 0.0, "xg": 0.0, "xa": 0.0, "bonus": 0.0, "dc": 0.0,
            "bps": 0.0}


def _acc_add(a, el, ctx, mins):
    a["min"] += mins
    # Real returns sit alongside expected ones so the blend below has a
    # like-for-like average to shrink toward.
    a["xg"] += (XG_WEIGHT * f(el.get("expected_goals"))
                + (1 - XG_WEIGHT) * el.get("goals_scored", 0))
    a["xa"] += (XG_WEIGHT * f(el.get("expected_assists"))
                + (1 - XG_WEIGHT) * el.get("assists", 0))
    a["bonus"] += el.get("bonus", 0)
    a["dc"] += el.get("defensive_contribution", 0)
    a["bps"] += analysis.other_bps_per90(el, ctx, mins) * mins / 90.0


def _rates(a):
    m = a["min"] or 1.0
    return {"xg90": per90(a["xg"], m), "xa90": per90(a["xa"], m),
            "bonus90": per90(a["bonus"], m), "dc90": per90(a["dc"], m),
            "bps90": per90(a["bps"], m), "minutes": a["min"]}


RATE_KEYS = ("xg90", "xa90", "bonus90", "dc90", "bps90")


def _fit_on_price(samples, key):
    """Minutes-weighted least squares of one rate against price.

    Returns (intercept, slope). Falls back to a flat line at the weighted
    mean when the prices carry no spread - one club's worth of players all
    priced identically would otherwise divide by zero."""
    sw = sum(w for _p, _v, w in samples)
    if sw <= 0:
        return 0.0, 0.0
    mx = sum(p * w for p, _v, w in samples) / sw
    my = sum(v * w for _p, v, w in samples) / sw
    var = sum(w * (p - mx) ** 2 for p, _v, w in samples)
    if var <= 1e-9:
        return my, 0.0
    cov = sum(w * (p - mx) * (v - my) for p, v, w in samples)
    slope = cov / var
    return my - slope * mx, slope


def positional_priors(ctx):
    """Expected rates per position as a function of price, from the league.

    Derived rather than hardcoded so it tracks whatever this season turns out
    to be, and stable even now because it fits over a hundred-odd players per
    position rather than trusting one.

    Returns {pos: {"fits": {rate: (intercept, slope)}, "overall": rates)}} -
    `_prior_for` evaluates the fit; callers should not index this directly."""
    played, by_pos = {}, {}
    for el in ctx.players.values():
        mins = el.get("minutes", 0)
        if mins <= 0:
            continue
        pos = ctx.pos(el)
        by_pos.setdefault(pos, []).append(el)
        _acc_add(played.setdefault(pos, _acc_new()), el, ctx, mins)

    priors = {}
    for pos, els in by_pos.items():
        overall = _rates(played[pos])
        fits = {}
        for key in RATE_KEYS:
            samples = []
            for el in els:
                mins = el.get("minutes", 0)
                one = _acc_new()
                _acc_add(one, el, ctx, mins)
                samples.append((el["now_cost"] / 10.0, _rates(one)[key], mins))
            fits[key] = _fit_on_price(samples, key)
        priors[pos] = {"fits": fits, "overall": overall}
    return priors


DEFAULT_PRIOR = {"xg90": 0.1, "xa90": 0.1, "bonus90": 0.25, "dc90": 4.0,
                 "bps90": 12.0}


def _prior_for(el, pos, priors):
    """The rates this player should be shrunk toward - his position at his
    price, not his position at any price."""
    p = (priors or {}).get(pos)
    if not p:
        return DEFAULT_PRIOR
    price = el["now_cost"] / 10.0
    out = {}
    for key in RATE_KEYS:
        a, b = p["fits"][key]
        out[key] = max(RATE_FLOOR, a + b * price)
    return out


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

    # A predicted-lineup feed naming a man who has not kicked a ball this
    # season is a weaker claim than the same feed naming a regular, but the
    # branch above treats them identically - which is how a zero-minute
    # player came to be scored as a nailed-on 85-minute starter carrying
    # league-average rates, and outranked a fit player mid-hot-streak.
    # Temper toward a squad player's involvement until there is some
    # football to back the billing up.
    if minutes_played < EVIDENCE_MINUTES:
        evidence = minutes_played / EVIDENCE_MINUTES
        minutes = minutes * evidence + 45.0 * (1 - evidence)
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
    # Clamped tighter than the 0.5-2.0 this used to allow. That range let one
    # kind fixture move a player's score fourfold end to end, which swamped
    # every difference in the players themselves - a bench forward at home to
    # the worst side in the league outscored a proven starter away at a good
    # one. A fixture should tilt a decision, not decide it.
    mult = max(0.7, min(1.45, team_xg / baseline)) if baseline else 1.0
    if mk_matches:
        cs_prob = mk["cs"] / 100.0
    elif fixture:
        cs_prob = float(fixture.get("cs") or 0) / 100.0
    elif mk:
        cs_prob = mk["cs"] / 100.0
    else:
        cs_prob = 0.0

    prior = _prior_for(el, pos, priors)
    # Expected goals carry most of the weight, real ones the rest - a player
    # who keeps converting is telling you something xG alone will not.
    eff_xg = (XG_WEIGHT * f(el.get("expected_goals"))
              + (1 - XG_WEIGHT) * el.get("goals_scored", 0))
    eff_xa = (XG_WEIGHT * f(el.get("expected_assists"))
              + (1 - XG_WEIGHT) * el.get("assists", 0))
    xg90 = _shrink(per90(eff_xg, minutes_played), minutes_played, prior["xg90"])
    xa90 = _shrink(per90(eff_xa, minutes_played), minutes_played, prior["xa90"])
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


# How many gameweeks a transfer decision is ranked across, rather than the
# one directly ahead. A transfer is not undone next week, so scoring it on
# a single week of fixture luck was answering a longer-lived question with
# the shortest possible answer.
TRANSFER_HORIZON_WEEKS = 5

# These add a flat nudge on top of the windowed points total rather than
# replacing it - the points model stays the dominant term, per-90 rates and
# fixtures already run through it. Neither weight is a fitted or validated
# calibration; there is no season of transfer outcomes yet to fit one
# against, so both are kept deliberately small: enough that a genuine hot
# streak or a strong underlying rate the model has shrunk hard can tip a
# close call, never enough to override what the points total says outright.
#
# Flat, not scaled by the window length - form is already points-per-match,
# so multiplying it by every week in an 8-week window (an early version of
# this did) treats one hot recent match as if it were guaranteed to repeat
# for two months, which turned a single big early-season haul into a
# 40-point swing. A flat weight instead says "this recent form is worth
# about half a match's evidence", however long the window being ranked is.
FORM_CASE_WEIGHT = 0.5      # extra points/match of recent form, flat
EXPECTED_CASE_WEIGHT = 3.0  # extra xGI (xGI minus xGC for def/gk), per 90

# A meaningful gain in case_score, scaled to the horizon it's summed over -
# the single-gameweek thresholds this replaced (0.15, 0.05) were tuned to a
# one-week number and would pass almost everything once the total is
# summed across TRANSFER_HORIZON_WEEKS weeks instead.
MIN_CASE_GAIN = 0.15 * TRANSFER_HORIZON_WEEKS


def player_case_factors(el, ctx):
    """Two signals a transfer decision should weigh beyond one gameweek's
    fixture-adjusted points, both already sitting in the bootstrap payload
    so neither costs an extra request per candidate.

    `form` is FPL's own recent-points-per-match average - a different
    read from the season-long, price-shrunk rate candidate_score uses
    internally, since a player heating up or cooling off shows here before
    enough matches exist to move his season rate much. `expected` is xGI
    alone for a midfielder or forward, and xGI net of xGC for a defender or
    keeper, because the defensive half of the game matters as much as the
    attacking half for those two positions and a shrunk points total can
    still be sitting on a stale prior for a player just breaking out."""
    pos = ctx.pos(el)
    form = f(el.get("form"))
    xgi90 = f(el.get("expected_goal_involvements_per_90"))
    if pos in ("DEF", "GKP"):
        expected = xgi90 - f(el.get("expected_goals_conceded_per_90"))
    else:
        expected = xgi90
    return {"form": form, "expected": expected}


def case_score(el, ctx, proj, gw, market, baselines, priors=None,
               weeks=TRANSFER_HORIZON_WEEKS):
    """A transfer candidate's score for one decision: points summed across
    the next few gameweeks rather than one, nudged by recent form and each
    player's own underlying numbers rather than fixture-adjusted points
    alone.

    Shaped exactly like candidate_score's return value - opponent, home and
    cs still come from the coming fixture specifically, since "who do they
    play next" stays useful context even though the total behind it now
    looks further ahead. Every existing caller reading s["total"],
    s["opponent"] or s["home"] keeps working unchanged; only what "total"
    means gets richer, which is the same principle by which
    windowed_candidate_score already extends candidate_score."""
    priors = priors or positional_priors(ctx)
    here = candidate_score(el, ctx, proj, gw, market, baselines, priors)
    if not here:
        return None
    windowed_total, _ = windowed_candidate_score(
        el, ctx, proj, market, baselines, priors, gw, weeks)
    factors = player_case_factors(el, ctx)
    case_total = (windowed_total
                  + FORM_CASE_WEIGHT * factors["form"]
                  + EXPECTED_CASE_WEIGHT * factors["expected"])
    return {**here, "total": case_total, "next_gw_total": here["total"], **factors}


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


def league_scores(ctx, proj, gw, market, baselines, priors=None):
    """Every eligible player in the game scored for one gameweek,
    {player_id: score}. Includes players already owned - the caller decides
    what "owned" means for its own purposes, and the Buy/Sell/Keep/Avoid
    board needs both sides of that line scored on identical terms.

    Deliberately the same scorer `suggest` uses on both the squad and the
    candidates, for the reason given there: a board that scored owned
    players with the richer history-backed model and everyone else with
    this one would be comparing two different yardsticks and calling the
    difference a recommendation. Scored with case_score, not
    candidate_score directly - a few weeks and each player's own numbers,
    not one gameweek of fixture-adjusted points alone."""
    priors = priors or positional_priors(ctx)
    out = {}
    for el in ctx.players.values():
        if not _eligible(el, ctx):
            continue
        s = case_score(el, ctx, proj, gw, market, baselines, priors)
        if s:
            out[el["id"]] = s
    return out


# How much better a reachable replacement has to project before the man he
# would replace is called a sell rather than a hold. Scaled to
# TRANSFER_HORIZON_WEEKS now that scores are case_score's windowed total
# rather than one gameweek - 0.6 was a fraction under a point on a 2-6
# point single-week score, and comparing it against a several-week sum
# would call almost every gap a sell.
SELL_MARGIN = 0.6 * TRANSFER_HORIZON_WEEKS

# Net transfers in across a gameweek that mark a player as a bandwagon
# rather than quiet accumulation. Against an active manager base in the
# millions, six figures of net movement in a few days is a crowd.
BANDWAGON_NET = 60000


def verdict_board(ctx, squad_reports, scores, bank=0.0, per_list=4):
    """Buy, Sell, Keep and Avoid - four questions with four different
    rules, not one ranking sliced into quarters.

    Slicing one ranking is the obvious implementation and it is wrong: it
    makes "avoid" mean nothing more than "ranked low", which is already
    what "sell" means, and it can never say the one useful thing about a
    player the whole game is buying this week. So:

    * **Buy** - not owned, projects highest for the coming week, and is
      actually reachable by selling someone you own in that position.
    * **Sell** - owned, and a specific affordable replacement projects
      meaningfully higher. Named, so the claim is checkable.
    * **Keep** - owned, projects well, and nothing above wants to move
      him. The useful half of a recommendation engine is the part that
      tells you to sit still.
    * **Avoid** - not owned, being bought heavily right now, and a
      same-position player at the same price or less projects higher.
      This is the only list here that reads the market rather than the
      model, and the only one that can disagree with the crowd.

    One gameweek of projection underneath all four, the same as every
    other recommendation on the page.
    """
    owned = {r.element["id"]: r for r in squad_reports}
    scored_owned = [r for r in squad_reports if r.element["id"] in scores]
    if not scored_owned:
        return None

    # The most expensive man held in each position sets what a purchase
    # there can cost: you have to sell someone to buy someone.
    ceiling = {}
    for r in scored_owned:
        ceiling[r.pos] = max(ceiling.get(r.pos, 0.0), r.price + bank)

    # Three per club, the same rule `suggest` enforces. Without it the Buy
    # column filled with whichever club had the kindest fixture that week -
    # four Manchester City names, on top of the two City players already
    # owned - which is not a shortlist, it is an illegal squad.
    club_counts = {}
    for r in squad_reports:
        club_counts[r.element["team"]] = club_counts.get(r.element["team"], 0) + 1

    def club_ok(el, selling=None):
        """Whether signing `el` keeps the squad legal. `selling` is the
        player being sold to fund him where there is a designated one -
        leaving a club frees the slot that joining it fills."""
        count = club_counts.get(el["team"], 0)
        if selling is not None and selling.element["team"] == el["team"]:
            count -= 1
        return count < SQUAD_LIMIT_PER_CLUB

    def take(rows, n):
        """The first `n` rows, but no more from one club than there are
        squad slots left for it.

        Checking legality one row at a time is not enough for a column
        read as a shortlist: with two Manchester City players already
        owned, every City man passes that test on his own, and Buy came
        out as four City names when only one of them can actually be
        signed. The budget has to be spent across the list, not re-offered
        to each row."""
        room, out = {}, []
        for r in rows:
            team = ctx.players[r["id"]]["team"]
            if team not in room:
                room[team] = SQUAD_LIMIT_PER_CLUB - club_counts.get(team, 0)
            if room[team] <= 0:
                continue
            room[team] -= 1
            out.append(r)
            if len(out) >= n:
                break
        return out

    def row(el, s, note):
        return {
            "id": el["id"], "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "price": el["now_cost"] / 10.0,
            "ep": s["total"], "opponent": s["opponent"], "home": s["home"],
            "note": note,
        }

    # --- Sell, and the replacement that justifies calling it one -------
    sell, sell_ids = [], set()
    for r in scored_owned:
        mine = scores[r.element["id"]]["total"]
        budget = r.price + bank
        best = None
        for pid, s in scores.items():
            if pid in owned:
                continue
            el = ctx.players[pid]
            if ctx.pos(el) != r.pos:
                continue
            if el["now_cost"] / 10.0 > budget + 1e-9:
                continue
            if not club_ok(el, selling=r):
                continue
            if best is None or s["total"] > best[1]["total"]:
                best = (el, s)
        if not best or best[1]["total"] - mine < SELL_MARGIN:
            continue
        sell_ids.add(r.element["id"])
        sell.append({
            "id": r.element["id"], "name": r.name, "pos": r.pos,
            "club": r.team, "price": r.price, "ep": mine,
            "opponent": scores[r.element["id"]]["opponent"],
            "home": scores[r.element["id"]]["home"],
            "gap": best[1]["total"] - mine,
            "note": "{} projects {:+.1f} in his place".format(
                best[0]["web_name"], best[1]["total"] - mine),
        })
    sell.sort(key=lambda x: -x["gap"])

    # --- Buy: reachable, and projects highest ------------------------
    buy = []
    for pid, s in scores.items():
        if pid in owned:
            continue
        el = ctx.players[pid]
        pos = ctx.pos(el)
        if pos not in ceiling or el["now_cost"] / 10.0 > ceiling[pos] + 1e-9:
            continue
        if not club_ok(el):
            continue
        buy.append(row(el, s, "{:.1f} projected, {} {}".format(
            s["total"], "vs" if s["home"] else "at", s["opponent"])))
    buy.sort(key=lambda x: -x["ep"])

    # --- Keep: rated well, and nothing wants to move him -------------
    keep = []
    for r in scored_owned:
        if r.element["id"] in sell_ids:
            continue
        s = scores[r.element["id"]]
        keep.append({
            "id": r.element["id"], "name": r.name, "pos": r.pos,
            "club": r.team, "price": r.price, "ep": s["total"],
            "opponent": s["opponent"], "home": s["home"],
            "note": "no reachable upgrade at {:.1f}m".format(r.price + bank),
        })
    keep.sort(key=lambda x: -x["ep"])

    # --- Avoid: the crowd is buying, the numbers do not agree --------
    avoid = []
    for pid, s in scores.items():
        if pid in owned:
            continue
        el = ctx.players[pid]
        net = el.get("transfers_in_event", 0) - el.get("transfers_out_event", 0)
        if net < BANDWAGON_NET or not club_ok(el):
            continue
        pos, price = ctx.pos(el), el["now_cost"] / 10.0
        better = None
        for oid, os_ in scores.items():
            if oid == pid or oid in owned:
                continue
            oel = ctx.players[oid]
            if ctx.pos(oel) != pos or oel["now_cost"] / 10.0 > price + 1e-9:
                continue
            if os_["total"] <= s["total"] or not club_ok(oel):
                continue
            if better is None or os_["total"] > better[1]["total"]:
                better = (oel, os_)
        if not better:
            continue
        avoid.append({
            **row(el, s, "{} is {:.1f}m and projects {:+.1f}".format(
                better[0]["web_name"], better[0]["now_cost"] / 10.0,
                better[1]["total"] - s["total"])),
            "net": net,
        })
    avoid.sort(key=lambda x: -x["net"])

    # Sell and Keep are lists of players already owned, so the club budget
    # does not apply to them - it only constrains who you can sign.
    return {
        "buy": take(buy, per_list), "sell": sell[:per_list],
        "keep": keep[:per_list], "avoid": take(avoid, per_list),
    }


def kneejerk(ctx, squad_reports, scores, bank=0.0):
    """The player who just hauled and you do not own - named as the
    impulse it is, and priced honestly.

    Every manager has this thought on a Saturday evening, so the card
    exists to answer it rather than pretend it does not get had. What
    makes it worth rendering is the second half: last week's points are
    the one number in this whole page with no predictive weight at all,
    so the card carries the projection for the coming week beside them,
    and the best available alternative at the same money. If the impulse
    survives that comparison it was not a knee-jerk.

    Returns None when the top scorer of the week is already in the squad,
    which is the happy case and needs no card."""
    owned = {r.element["id"]: r for r in squad_reports}
    best = None
    for el in ctx.players.values():
        if el["id"] in owned or not _eligible(el, ctx):
            continue
        pts = el.get("event_points") or 0
        if pts <= 0:
            continue
        if best is None or pts > (best.get("event_points") or 0):
            best = el
    if best is None:
        return None

    pos, price = ctx.pos(best), best["now_cost"] / 10.0
    score = scores.get(best["id"])

    # Who you would have to sell to afford him, and whether anyone at that
    # money is projected to do better.
    affordable = [r for r in squad_reports
                  if r.pos == pos and r.price + bank + 1e-9 >= price]
    funder = min(affordable, key=lambda r: r.price) if affordable else None

    club_counts = {}
    for r in squad_reports:
        club_counts[r.element["team"]] = club_counts.get(r.element["team"], 0) + 1

    rival = None
    if funder:
        budget = funder.price + bank
        for pid, s in scores.items():
            if pid in owned or pid == best["id"]:
                continue
            el = ctx.players[pid]
            if ctx.pos(el) != pos or el["now_cost"] / 10.0 > budget + 1e-9:
                continue
            # Same three-per-club rule: an alternative you cannot legally
            # sign is not an alternative.
            count = club_counts.get(el["team"], 0)
            if funder.element["team"] == el["team"]:
                count -= 1
            if count >= SQUAD_LIMIT_PER_CLUB:
                continue
            if rival is None or s["total"] > rival[1]["total"]:
                rival = (el, s)

    return {
        "id": best["id"], "name": best["web_name"], "pos": pos,
        "club": ctx.team_name(best["team"]), "price": price,
        "points": best.get("event_points") or 0,
        "owned": f(best.get("selected_by_percent")),
        # Gross, not net. Bruno Fernandes came out of gameweek 2 on 23
        # points with 182,843 managers buying him and almost as many
        # selling - a net of +2,090, which printed on a card headed "the
        # knee-jerk" reads as nobody wanting him. The crowd buying is the
        # signal this card is about, so the crowd buying is the number.
        "bought": best.get("transfers_in_event", 0),
        "ep": score["total"] if score else None,
        "opponent": score["opponent"] if score else None,
        "home": score["home"] if score else None,
        "funder": funder,
        "rival": ({"name": rival[0]["web_name"],
                   "price": rival[0]["now_cost"] / 10.0,
                   "ep": rival[1]["total"]} if rival else None),
    }


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
        s = case_score(el, ctx, proj, gw, market, baselines, priors)
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
        base = case_score(r.element, ctx, proj, gw, market, baselines, priors)
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
            if gain <= MIN_CASE_GAIN / 3:
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
    # Incoming players are held distinct across the whole list for the same
    # reason as in `suggest`: two pairings that both sign the same man are
    # one decision shown twice, and only one of them can be acted on.
    used, bought, picked = set(), set(), []
    for p in pairings:
        outs = {leg["out"].element["id"] for leg in p["legs"]}
        ins = {leg["in"]["id"] for leg in p["legs"]}
        if outs & used or ins & bought:
            continue
        used |= outs
        bought |= ins
        picked.append(p)
        if len(picked) >= limit:
            break
    return picked


def suggest(ctx, squad_reports, proj, gw, market, baselines, bank=0.0,
            per_slot=3, limit=6, elite=None):
    """Swaps worth a look: one out, one in, same position, affordable.

    Ranked on the gain in case_score, not one gameweek of raw projected
    points - see case_score for what that adds (a few weeks' points and
    each player's own form and underlying numbers) and why."""
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
        s = case_score(el, ctx, proj, gw, market, baselines, priors)
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
        here = case_score(r.element, ctx, proj, gw, market, baselines, priors)
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
            if gain <= MIN_CASE_GAIN:
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
    #
    # And one per *incoming* player too, which this used to miss: the same
    # replacement could be offered against two different squad players, so
    # a Bench Boost rebuild came out reading "Konsa to Davis" and "Diop to
    # Davis" on consecutive rows. You cannot buy him twice, and even where
    # the second row is a legal alternative it is the same decision twice
    # over, which is exactly what this filter exists to prevent.
    seen_out, seen_in, picked = set(), set(), []
    for row in out_rows:
        if row["out"].element["id"] in seen_out or row["in"]["id"] in seen_in:
            continue
        seen_out.add(row["out"].element["id"])
        seen_in.add(row["in"]["id"])
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked
