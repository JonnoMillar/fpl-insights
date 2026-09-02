#!/usr/bin/env python3
"""
The Captaincy Decision Matrix: this gameweek's armband candidates from the
manager's own predicted XI, scored across five axes so their shapes can be
compared at a glance instead of read off a table.

Reuses analysis.expected_points rather than re-deriving fixture quality -
that function already prefers the betting market over the model wherever
one has priced the fixture, with everything labelled by source.

Axes, and where each number actually comes from:
  * Form            - points across the player's last 4 matches played.
  * Fixture         - fixture_mult from expected_points: how many more (or
                      fewer) goals the player's team is priced to score this
                      match than their own season baseline - the market's
                      read on the opponent's defence wherever it has priced
                      the game.
  * Goal threat     - the player's own expected-goal-involvement rate
                      (goals + assists) per 90, blended toward last season
                      while this season is thin, the same blend
                      analysis.expected_points applies to xg90/xa90. This
                      used to be exp_goals from expected_points, which
                      already carries fixture_mult and a share-of-minutes
                      discount inside it - counting fixture quality and
                      start certainty a second time, on top of their own
                      dedicated axes. The player-alone rate keeps this axis
                      about the player, Fixture about the fixture, and
                      Start certainty about his minutes.
  * Start certainty - start_probability from the same module: how nailed-on
                      he is to actually take the pitch. Not a scoring
                      dimension, but the one thing that zeroes out every
                      other axis if it does not hold - a captain who gets
                      benched is the real nightmare, not a quiet return.
  * Responsibilities - a blind weighting of the set-piece duties he's
                      actually named on: 50 if he takes penalties, +25 if
                      he also takes corners, +25 if he also takes free
                      kicks - so a penalty taker alone sits at 50, and a
                      man on all three reaches the edge. Penalties no
                      longer dominate the axis the way a 65-point floor
                      did: a penalty is worth roughly 0.08 xG per match to
                      its taker, not a whole scoring axis's worth of edge,
                      so this split leaves room for corners and free kicks
                      to matter too rather than being rounding error next
                      to the spot kick. "Blind" because it does not weigh
                      how often the duty actually arises or how well he
                      converts it - only whether the club has named him
                      for it. Home/away moved off the chart into a small
                      venue icon by each candidate's name instead: it was
                      the one axis that was not really about captaincy
                      risk or ceiling, and a fixed 0-100-of-something scale
                      does not suit a number that is naturally a ratio
                      around 1.0 anyway.

An earlier version used "record against this opponent" as the fifth axis,
but this early in a season almost every fixture is a first meeting, so it
was degenerate for most candidates most weeks - replaced with start
certainty, a genuine and always-available signal. Home/away edge held the
fifth slot after that, and was replaced in turn by responsibilities.

Every axis is scaled to a fixed, real-world range for that metric (0-100),
not to whichever candidates happen to be shown. Min-max across just the
shortlist was tried first and rejected: with 2-3 points, that scaling
stretches to fill the full 0-100 span regardless of how big the actual gap
is, so a fixture edge of a few tenths (a real but modest difference) read
identically to a fixture edge of a full point (an enormous one) - both
just "one candidate at the centre, one at the rim". A fixed scale means
the edge of the chart means the same thing every week: genuinely one of
the best fixtures anyone gets, not just the best of whoever is on screen
today. See SCALES below for where each bound comes from.
"""

import analysis

# 50% for penalties, 25% for corners, 25% for free kicks - see the module
# docstring for why this is "blind" rather than reliability-weighted, and
# L8 in the quality audit for why penalties dominate less than the old
# 65/20/15 split: a penalty is worth roughly 0.08 xG per match to its
# taker, not the full weight of a whole other scoring axis.
RESP_WEIGHTS = {"pens": 50.0, "fk": 25.0, "corners": 25.0}

# (key, label, unit) - unit drives client-side tooltip formatting only.
METRICS = [
    ("form", "Form (last 4)", "pts"),
    ("fixture", "Fixture (xG mult)", "x"),
    ("goal_threat", "Goal threat", "xGI/90"),
    ("start_cert", "Start certainty", "%"),
    ("responsibility", "Responsibilities", "%"),
]

# The (low, high) each axis is scaled against - the real range the number
# is actually measured on, not the spread of whoever is on the chart this
# week. Two of these are exact by construction; the other two are set from
# where genuine top-of-the-game numbers actually land, not fitted or
# revisited week to week:
#   fixture         analysis.expected_points hard-clamps fixture_mult to
#                   [0.5, 2.0] itself - reusing that bound rather than
#                   inventing a second one keeps the axis honest about what
#                   the underlying number can even be.
#   start_cert      already a probability - 0-100% is exact, not a choice.
#   form            0 to 30: a 4-match haul of 30 (7.5 pts/match) is a
#                   season-defining hot streak - sampling this season's
#                   top-priced XIs, even a p99 run over the last 4 played
#                   sat at 25, so 30 leaves room above anything actually
#                   seen without needing revisiting most weeks.
#   goal_threat     0 to 1.5 blended xGI (goals + assists) per 90 - above
#                   what even an elite attacker's own rate reaches across a
#                   full season (a genuinely explosive early-season run,
#                   sampled this season, peaked around 1.2), so a hot
#                   streak still reads near, not past, the rim.
SCALES = {
    "form": (0.0, 30.0),
    "fixture": (0.5, 2.0),
    "goal_threat": (0.0, 1.5),
    "start_cert": (0.0, 100.0),
    "responsibility": (0.0, 100.0),
}

# A value sitting exactly at or below its scale's floor would draw as a
# zero-radius point - invisible, not "genuinely the worst possible", and
# indistinguishable from missing data. A small floor keeps every vertex on
# every candidate's polygon visible without changing what the position
# above it says.
SCALE_FLOOR = 6.0


def _scale(values, key):
    """Fixed-range 0-100 scaling for one metric's raw values, using
    SCALES[key] rather than this call's own min and max - see the module
    docstring for why."""
    lo, hi = SCALES[key]
    span = hi - lo
    out = []
    for v in values:
        pct = (v - lo) / span * 100
        out.append(round(max(SCALE_FLOOR, min(100.0, pct)), 1))
    return out


def _duty_active(ctx, r, field):
    """Whether this player will actually be the one taking this duty, not
    just whether the club has ever named him on it anywhere in the order.
    Order 1 always counts. A backup (order 2+) only counts if the club's
    order-1 man is known not to be playing this match - otherwise he is
    just the name on the team sheet who will not get the touches, and
    crediting him the same as the nailed-on taker (the Isak-behind-Isak...
    case: a backup penalty taker whose own club's #1 is predicted to
    start) overstates his responsibilities."""
    order = r.element.get(field)
    if not order:
        return False
    if order == 1:
        return True
    primary = next(
        (p for p in ctx.players.values()
         if p.get("team") == r.element.get("team") and p.get(field) == 1),
        None,
    )
    if primary is None:
        return True  # no recorded #1 for this duty - keep prior behaviour
    return ctx.is_predicted(primary) is False


def _blended_goal_threat(r):
    """This player's own expected-goal-involvement rate per 90, blended
    toward last season while this season is thin - the same blend
    analysis.expected_points applies to xg90/xa90, but with no fixture
    multiplier or minutes share folded in, so this stays a read on the
    player alone (see the module docstring's Goal threat entry)."""
    xgi90 = r.xgi90
    ls = r.last_season()
    if r.minutes < analysis.THIN_SAMPLE_MINUTES and ls and ls["minutes"] >= 900:
        blend = r.minutes / analysis.THIN_SAMPLE_MINUTES
        xgi90 = blend * xgi90 + (1 - blend) * analysis.per90(ls["xgi"], ls["minutes"])
        note = "blended with last season"
    else:
        note = "this season"
    return xgi90, note


def matrix(ctx, xi, eps_by_id, top_n=3):
    """eps_by_id: {player_id: ep_dict}, from analysis.expected_points -
    computed once in dashboard.build() for the manager's XI + bench, reused
    here rather than recomputed. top_n defaults to 3 - the point of the
    chart is comparing a genuine shortlist by eye, and a 4th or 5th colour
    stops being reliably distinguishable at a glance."""
    candidates = [
        (r, eps_by_id[r.element["id"]])
        for r in xi
        if r.element["id"] in eps_by_id
    ]
    candidates.sort(key=lambda c: c[1]["total"], reverse=True)
    candidates = candidates[:top_n]
    if len(candidates) < 2:
        return None

    raw = []
    for r, ep in candidates:
        ppg = r.points / max(1, r.appearances)

        form = r.last_n_points(4)
        form_note = "last 4 played"
        if form is None:
            form, form_note = ppg, "season ppg (no run of 4 yet)"

        start_cert = round(100 * r.start_probability(ctx), 1)

        resp, resp_parts = 0.0, []
        if _duty_active(ctx, r, "penalties_order"):
            resp += RESP_WEIGHTS["pens"]
            resp_parts.append("penalties")
        if _duty_active(ctx, r, "direct_freekicks_order"):
            resp += RESP_WEIGHTS["fk"]
            resp_parts.append("free kicks")
        if _duty_active(ctx, r, "corners_and_indirect_freekicks_order"):
            resp += RESP_WEIGHTS["corners"]
            resp_parts.append("corners")
        resp_note = ("on " + ", ".join(resp_parts)) if resp_parts else "not on any set piece"
        # Shown on the chart itself instead of the 0-100 score - a captain
        # pick cares which duties he's actually on, not a blind weighting
        # number that happens to read like a percentage.
        resp_label = ", ".join(resp_parts).capitalize() if resp_parts else "None"
        # One duty per line for the chart itself: the Responsibilities axis
        # sits in a fixed, narrow spot (upper-left of the pentagon), and the
        # full comma-joined label ("Penalties, free kicks, corners") is
        # wider than the room the chart has there and gets clipped by the
        # SVG's own edge. Short, stacked lines fit regardless of how many
        # duties a player holds.
        resp_lines = [p.capitalize() for p in resp_parts] if resp_parts else ["None"]

        goal_threat, goal_threat_note = _blended_goal_threat(r)

        raw.append({
            "player": r.name,
            "team": r.team,
            "opponent": ep["opponent"],
            "home": ep["home"],
            "ep_total": round(ep["total"], 1),
            "form": form, "form_note": form_note,
            "fixture": ep["fixture_mult"], "fixture_note": "vs season baseline",
            "goal_threat": goal_threat, "goal_threat_note": goal_threat_note,
            "start_cert": start_cert, "start_cert_note": "chance of starting",
            "responsibility": resp, "responsibility_note": resp_note,
            "responsibility_label": resp_label, "responsibility_lines": resp_lines,
        })

    keys = [k for k, _, _ in METRICS]
    # Every axis, responsibility included, now scales against its own
    # fixed real-world range (SCALES) rather than whoever else is on the
    # chart - see the module docstring. Responsibility's raw values (0,
    # 50, 75, 100) already sit on that same 0-100 scale, so this is a
    # no-op for it beyond applying the visibility floor.
    normed = {k: _scale([row[k] for row in raw], k) for k in keys}

    out = []
    for i, row in enumerate(raw):
        values = {k: normed[k][i] for k in keys}
        out.append({**row, "values": values})

    # candidates (and so raw/out) are already sorted by ep_total descending
    # from the top of this function - the top pick is whoever projects the
    # most points, not whichever radar shape happens to enclose the most
    # area (which depends on axis order and scale, not on points).
    top = out[0]

    return {"candidates": out, "metrics": METRICS, "top": top["player"]}
