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
  * Home/away       - the player's points-per-game at this fixture's venue
                      against his other-venue rate this season. Falls back to
                      a flat home edge when one side has no sample yet.

An earlier version used "record against this opponent" as the fifth axis,
but this early in a season almost every fixture is a first meeting, so it
was degenerate for most candidates most weeks - replaced with start
certainty, a genuine and always-available signal.

Every axis is min-max normalised across just the candidates shown (0-100) -
the chart compares this week's shortlist against each other, not against
the whole league.
"""

import math

# (key, label, unit) - unit drives client-side tooltip formatting only.
METRICS = [
    ("form", "Form (last 4)", "pts"),
    ("fixture", "Fixture (xG mult)", "x"),
    ("goal_threat", "Goal threat", "xG"),
    ("start_cert", "Start certainty", "%"),
    ("home_away", "Home/away edge", "x"),
]


def _normalise(values):
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [70.0 for _ in values]
    return [round(100 * (v - lo) / (hi - lo), 1) for v in values]


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

        home_ppg, away_ppg = r.home_away_points()
        this_side = home_ppg if ep["home"] else away_ppg
        other_side = away_ppg if ep["home"] else home_ppg
        if this_side is None:
            venue_edge = 1.1 if ep["home"] else 0.9
            venue_note = "no venue sample yet, flat home edge assumed"
        elif not other_side:
            venue_edge = 1.0
            venue_note = f"{this_side:.1f} ppg at this venue, no comparison side yet"
        else:
            venue_edge = this_side / other_side
            venue_note = f"{this_side:.1f} vs {other_side:.1f} ppg (this venue vs other)"

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
            "home_away": venue_edge, "home_away_note": venue_note,
        })

    keys = [k for k, _, _ in METRICS]
    normed = {k: _normalise([row[k] for row in raw]) for k in keys}

    out = []
    for i, row in enumerate(raw):
        values = {k: normed[k][i] for k in keys}
        out.append({**row, "values": values,
                    "area": _polygon_area(values, keys)})

    top = max(out, key=lambda c: c["area"])
    for row in out:
        row["is_top_area"] = row is top

    return {"candidates": out, "metrics": METRICS, "top": top["player"]}
