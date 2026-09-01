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
  * Goal threat     - exp_goals from the same calculation: this player's own
                      expected goals for this specific match. This is a
                      market-informed proxy for scoring likelihood, not a
                      quoted anytime-goalscorer price - odds.py reads
                      Pinnacle's team-level markets, not individual player
                      lines, so there is no genuine anytime-scorer number
                      available here.
  * Start certainty - start_probability from the same module: how nailed-on
                      he is to actually take the pitch. Not a scoring
                      dimension, but the one thing that zeroes out every
                      other axis if it does not hold - a captain who gets
                      benched is the real nightmare, not a quiet return.
  * Responsibilities - a blind weighting of the set-piece duties he's
                      actually named on: 65 if he takes penalties, +20 if
                      he also takes free kicks, +15 if he also takes
                      corners - so a penalty taker alone sits at 65, a
                      penalty-and-free-kick man at 85, and a man on all
                      three reaches the edge. "Blind" because it does not
                      weigh how often the duty actually arises or how well
                      he converts it - only whether the club has named him
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

Form, fixture, goal threat and start certainty are min-max normalised
across just the candidates shown (0-100) - the chart compares this week's
shortlist against each other, not against the whole league. Responsibility
is the one axis that is NOT normalised this way: 65/85/100 are fixed
points regardless of who else is shown, since "on penalties" means the
same thing whoever you are compared against.
"""

import math

# 65% for penalties, +20% for free kicks, +15% for corners - see the module
# docstring for why this is "blind" rather than reliability-weighted.
RESP_WEIGHTS = {"pens": 65.0, "fk": 20.0, "corners": 15.0}

# (key, label, unit) - unit drives client-side tooltip formatting only.
METRICS = [
    ("form", "Form (last 4)", "pts"),
    ("fixture", "Fixture (xG mult)", "x"),
    ("goal_threat", "Goal threat", "xG"),
    ("start_cert", "Start certainty", "%"),
    ("responsibility", "Responsibilities", "%"),
]


NORM_FLOOR = 6.0


def _normalise(values):
    """Min-max to 0-100, except the minimum lands on NORM_FLOOR, not 0.

    Two candidates from the same club share the same team-level fixture
    multiplier - a real tie, not missing data - and whichever axis they
    tie lowest on used to put both vertices exactly on the chart's centre
    point, radius zero. That reads as a missing line rather than a real,
    if unexceptional, value: the tooltip still had the honest number, but
    the shape gave the eye nothing to see. A small floor keeps every
    candidate's polygon visible on every axis without changing what the
    comparison actually says - the spread between candidates is untouched,
    only the bottom of the scale moved off exactly zero."""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [70.0 for _ in values]
    return [round(NORM_FLOOR + (100 - NORM_FLOOR) * (v - lo) / (hi - lo), 1)
            for v in values]


def _polygon_area(values, keys):
    """Shoelace formula over the pentagon, metrics evenly spaced by angle,
    each axis already 0-100. Used only to state which shape is largest in
    words - the chart itself is drawn client-side."""
    n = len(keys)
    pts = []
    for i, k in enumerate(keys):
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        r = values[k]
        pts.append((r * math.cos(angle), r * math.sin(angle)))
    area = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


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
        if r.element.get("penalties_order"):
            resp += RESP_WEIGHTS["pens"]
            resp_parts.append("penalties")
        if r.element.get("direct_freekicks_order"):
            resp += RESP_WEIGHTS["fk"]
            resp_parts.append("free kicks")
        if r.element.get("corners_and_indirect_freekicks_order"):
            resp += RESP_WEIGHTS["corners"]
            resp_parts.append("corners")
        resp_note = ("on " + ", ".join(resp_parts)) if resp_parts else "not on any set piece"

        raw.append({
            "player": r.name,
            "team": r.team,
            "opponent": ep["opponent"],
            "home": ep["home"],
            "ep_total": round(ep["total"], 1),
            "form": form, "form_note": form_note,
            "fixture": ep["fixture_mult"], "fixture_note": "vs season baseline",
            "goal_threat": ep["exp_goals"], "goal_threat_note": ep["xg_source"],
            "start_cert": start_cert, "start_cert_note": "chance of starting",
            "responsibility": resp, "responsibility_note": resp_note,
        })

    keys = [k for k, _, _ in METRICS]
    # Responsibility is fixed - 65/85/100 mean the same thing whoever else
    # is shown - so it skips the relative min-max normalisation every other
    # axis gets. Without this, a shortlist where nobody takes penalties
    # would stretch someone on corners alone out to the full edge.
    normed = {
        k: (list(row[k] for row in raw) if k == "responsibility"
            else _normalise([row[k] for row in raw]))
        for k in keys
    }

    out = []
    for i, row in enumerate(raw):
        values = {k: normed[k][i] for k in keys}
        out.append({**row, "values": values,
                    "area": _polygon_area(values, keys)})

    top = max(out, key=lambda c: c["area"])
    for row in out:
        row["is_top_area"] = row is top

    return {"candidates": out, "metrics": METRICS, "top": top["player"]}
