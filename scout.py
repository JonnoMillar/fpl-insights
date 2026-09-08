#!/usr/bin/env python3
"""
Position comparison labs - "which defender do I actually buy", generalised
to any outfield position.

Everything here is deliberately position-agnostic. What varies between a
defender lab, a midfielder lab and a forward lab is a handful of numbers -
the DEFCON threshold, which metric drives which archetype, which two axes
open the hero scatter - captured in `POSITIONS` below. Add a position by
adding an entry, not by copying this file.

See docs/superpowers/plans/2026-09-08-scout-section-plan.md for the design
rationale, including four places this deliberately does not follow the
original spec it was built from (§2 of that plan): the hero axis is gated by
sample size rather than always using the hit rate, archetype zones are not
shaded on the scatter canvas, `role` (CB/FB/WB) is cut for lacking a data
source, and the DEFCON-difficulty fixture row is a modelled proxy and is
labelled as one.
"""

import statistics
from dataclasses import dataclass, field

import analysis
import ffs
import fplapi
import ticker
import transfers

# A played gameweek's stats never change once FPL has settled it, so it is
# cached far longer than the live default - the whole point of a season
# harvest is to stop re-fetching weeks that are already final.
FINISHED_LIVE_TTL = 60 * 60 * 24 * 30

# Below this many minutes a per-90 rate is the same noise the rest of the
# dashboard already guards against (analysis.DEFCON_MIN_MINUTES) - reused
# rather than re-invented, so "too little football behind this number"
# means the same thing everywhere on the page.
RATE_MIN_MINUTES = analysis.DEFCON_MIN_MINUTES

# The hero scatter's x-axis swaps from a per-90 rate to the hit rate once
# the pool has enough football behind it to make a hit rate resolve into
# more than two or three values (see plan §2.1). Twice the per-player rate
# floor is about four full matches for the *median* player in whatever pool
# is currently filtered in - early enough in a run of matches to still be
# informative, late enough that the rate is not three-valued.
HERO_GATE_MINUTES = RATE_MIN_MINUTES * 2

# Fixtures are always fetched out to this many gameweeks and embedded in
# full - the filter bar's own horizon control just shows or hides columns
# client-side, the same pattern ticker.py already uses for its own 1-8 game
# selector (see FIXTURE_GAMES_DEFAULT in ticker.py) - so narrowing or
# widening the horizon never needs a server rebuild.
MAX_FIXTURE_HORIZON = 8

# Filter bar defaults (spec §4.1). Applied client-side, in scout.js, against
# the full pool this module sends - never baked into which rows are sent in
# the first place, or loosening a filter in the browser would have nothing
# left to reveal. Python's own _apply_filters/apply_derivations below exist
# to be ported 1:1 into scout.js, and as the reference the tests check.
DEFAULT_FILTERS = {
    "priceMin": None,
    "priceMax": None,
    "minStartRate": 0.6,
    "minMinutesPerStart": None,
    "team": None,
    "fixtureHorizon": 6,
}


def _clamp01(v):
    return max(0.0, min(1.0, v))


@dataclass
class PositionConfig:
    key: str                 # FPL element_type short code: DEF, MID, FWD
    label: str                # plural, for headings
    defcon_threshold: int      # analysis.DEFCON_THRESHOLD[key]
    hero_y: str                # y-axis metric key, see METRIC_LABELS
    archetypes: dict           # {archetype: driving metric key}
    metrics: list              # heatmap / z-bar column order, metric keys


# Metric keys shared across positions, with the direction each is "good" in
# and a short label. `invert` means the raw value must be flipped before a
# percentile or z-score is computed - a lower xGC is better, so its rank has
# to run backwards for "high percentile = good" to hold everywhere else on
# the page.
METRICS = {
    "defcon_hit_rate": ("DefCon hit rate", False),
    "defcon90": ("DefCon per 90", False),
    "xgi90": ("xGI per 90", False),
    "xgc90": ("xGC per 90", True),
    "start_rate": ("Start rate", False),
    "minutes_per_start": ("Minutes per start", False),
    "bps90": ("BPS per 90", False),
    "bonus90": ("Bonus per 90", False),
    "cards90": ("Cards per 90", True),
    "xp": ("xP", False),
}

POSITIONS = {
    "DEF": PositionConfig(
        key="DEF",
        label="Defenders",
        defcon_threshold=analysis.DEFCON_THRESHOLD["DEF"],
        hero_y="xgi90",
        archetypes={
            "volume": "defcon_hit_rate",
            "cleanSheet": "solidity_pct",
            "attacking": "xgi90",
        },
        metrics=["defcon_hit_rate", "xgi90", "xgc90", "start_rate",
                 "minutes_per_start", "bps90", "cards90", "xp"],
    ),
}


# --- colour and accessibility primitives -----------------------------------
#
# Scoped to this section, not the dashboard (plan §2.4): most of the rest of
# the page is already CVD-conscious for documented reasons (the fixture
# ticker's rose-teal ramp, size+ring+label on the value scatter, a triangle
# on every delta chip), and a global rewrite to Okabe-Ito would fight the
# standing FPL-purple-and-green brand constraint rather than serve it. These
# constants are for the new concepts this section introduces that have no
# existing scale to reuse: the percentile heatmap, the z-score bars, and an
# optional categorical toggle on the hero scatter. Fixture difficulty
# deliberately reuses ticker.py's own rose-teal ramp instead of a second
# diverging scale - see fixture_rows below and plan §2.5.

OKABE_ITO = {
    "blue": "#0072B2", "orange": "#E69F00", "sky": "#56B4E9",
    "yellow": "#F0E442", "green": "#009E73", "vermillion": "#D55E00",
    "purple": "#CC79A7",
}

# Okabe-Ito is built for hue separation under red-green and blue-yellow
# colourblindness, not for luminance separation under full greyscale -
# 'orange' and 'sky' differ by a relative luminance of 0.01, and
# 'green'/'vermillion'/'purple' sit within 0.04 of each other (measured
# below, see GREYSCALE_MIN_STEP). Picking straight from OKABE_ITO for an
# n-way categorical toggle can silently fail the dashboard's own greyscale
# acceptance test even though every colour is individually CVD-correct.
# This is the widest ordered subset - by relative luminance - that clears
# GREYSCALE_MIN_STEP against every other entry in it, for whenever the
# categorical toggle needs more than two colours. Marker shape still carries
# the distinction regardless (spec §1) - this only keeps the colour channel
# honest as a second one.
CATEGORICAL_ORDER = ["blue", "green", "sky", "yellow"]

# White->blue for a good percentile, white->orange for a bad one (spec
# §4.3) - the two ends of Okabe-Ito's blue and orange, shaped like the
# ticker's own five-step ramp (a genuine neutral middle, solid bands rather
# than a wash) so a new scale still feels native to the page. Never used for
# fixture difficulty - see the module docstring above.
DIVERGING_SCALE = [
    (20.0, "#08306b", "#ffffff"),
    (40.0, "#6baed6", "#0b3053"),
    (60.0, "#f4f2ee", "#37003c"),
    (80.0, "#fdae6b", "#5c2c00"),
    (100.1, "#e6550d", "#ffffff"),
]


def diverging_tone(percentile):
    """(bg, fg) for a 0..100 percentile against DIVERGING_SCALE - the
    heatmap and z-bar equivalent of ticker._tone."""
    for edge, bg, fg in DIVERGING_SCALE:
        if percentile < edge:
            return bg, fg
    return DIVERGING_SCALE[-1][1], DIVERGING_SCALE[-1][2]


def radius_for_percentile(pct, r_min=5.0, r_max=22.0):
    """Bubble radius from a 0..100 percentile, not the raw value (spec
    §4.2): raw xGC spans roughly 0.8 to 1.6, which is a few percent of the
    area difference between the smallest and largest circle - invisible.
    The percentile mapping is what makes the size channel legible at all,
    and is the formula scout.js must port for the live scatter."""
    pct = max(0.0, min(100.0, pct))
    return r_min + (r_max - r_min) * (pct / 100.0)


def _srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_colour):
    """WCAG relative luminance, 0 (black) to 1 (white).

    This is what a greyscale render actually preserves - converting to
    greyscale is exactly "keep luminance, discard hue and saturation" - so
    it is the mechanical form of spec §1's acceptance test: "render each
    chart in greyscale; if it is still readable, it passes."."""
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (_srgb_to_linear(x) for x in (r, g, b))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# The smallest luminance gap most people can still tell apart on an
# ordinary screen - used as the pass/fail line for both greyscale checks
# below rather than a bare "not identical" comparison.
GREYSCALE_MIN_STEP = 0.06


def greyscale_readable(hex_colours, min_step=GREYSCALE_MIN_STEP):
    """True if every *adjacent* pair of colours, in the order a reader
    encounters them on a sequential or diverging scale, differs in relative
    luminance by at least `min_step`. Use this for an ordered ramp such as
    DIVERGING_SCALE or ticker.SCALE, where only neighbours need to be told
    apart at a glance down a column."""
    lums = [relative_luminance(c) for c in hex_colours]
    return all(abs(b - a) >= min_step for a, b in zip(lums, lums[1:]))


def greyscale_distinguishable(hex_colours, min_step=GREYSCALE_MIN_STEP):
    """True if *every pair* of colours, not just adjacent ones, clears
    `min_step`. Use this for a categorical set such as CATEGORICAL_ORDER,
    where any two members can end up next to each other in the same chart -
    unlike a ramp, there is no fixed reading order to rely on."""
    lums = [relative_luminance(c) for c in hex_colours]
    return all(
        abs(lums[i] - lums[j]) >= min_step
        for i in range(len(lums)) for j in range(i + 1, len(lums))
    )


def season_live(ctx, upto_gw, ttl=fplapi.DEFAULT_TTL):
    """{player_id: [per-gameweek stat dict]}, oldest first, one row per
    finished gameweek up to and including `upto_gw`.

    One fplapi.event_live call per gameweek covers every player in the game
    at once - the alternative, fplapi.element_summary per player, is 600+
    requests for the same numbers (see plan §1). A gameweek FPL has already
    marked finished cannot change, so it is cached for a month; the current,
    possibly still-live gameweek keeps the caller's own ttl.

    FPL's public API has no notion of "benched" or "unavailable" outside a
    single manager's own picks - a player who did not feature this gameweek
    looks identical whether he was an unused substitute, dropped, or injured.
    Match status therefore collapses to three states here, not the four the
    original spec assumed: 'started', 'subbedOn', 'unplayed'."""
    fixtures_by_id = {fx["id"]: fx for fx in ctx.fixtures}
    finished_events = {e["id"] for e in ctx.events if e.get("finished")}
    by_player = {}
    for gw in range(1, upto_gw + 1):
        week_ttl = FINISHED_LIVE_TTL if gw in finished_events else ttl
        try:
            live = fplapi.event_live(gw, ttl=week_ttl)
        except fplapi.FplError:
            continue
        for el in live.get("elements", []):
            stats = el.get("stats") or {}
            pid = el["id"]
            player = ctx.players.get(pid)
            if not player:
                continue
            team = player["team"]
            explain = el.get("explain") or []
            # A double gameweek carries two entries in `explain`; only the
            # first fixture is used here, matching the rest of the codebase's
            # documented DGW blindness (quality-audit-2026-09-02, L1) rather
            # than silently disagreeing with it inside one new module.
            fx = fixtures_by_id.get(explain[0]["fixture"]) if explain else None
            opp, home = None, None
            if fx:
                if fx["team_h"] == team:
                    opp, home = fx["team_a"], True
                elif fx["team_a"] == team:
                    opp, home = fx["team_h"], False
            minutes = stats.get("minutes", 0)
            started = bool(stats.get("starts"))
            status = "started" if started else ("subbedOn" if minutes else "unplayed")
            by_player.setdefault(pid, []).append({
                "gw": gw,
                "opp": ctx.team_name(opp) if opp is not None else None,
                "home": home,
                "status": status,
                "minutes": minutes,
                "points": stats.get("total_points", 0),
                "defcon": stats.get("defensive_contribution", 0),
                "defconHit": stats.get("defensive_contribution", 0) >= (
                    analysis.DEFCON_THRESHOLD.get(ctx.pos(player)) or 999),
                "cleanSheet": bool(stats.get("clean_sheets")),
                "goalsConceded": stats.get("goals_conceded", 0),
                "bonus": stats.get("bonus", 0),
                "bps": stats.get("bps", 0),
                "card": "red" if stats.get("red_cards") else (
                    "yellow" if stats.get("yellow_cards") else "none"),
                "xgc": round(analysis.f(stats.get("expected_goals_conceded")), 2),
                "xgi": round(analysis.f(stats.get("expected_goal_involvements")), 2),
            })
    return by_player


def _team_played_since(ctx, team_id, from_gw):
    """How many of this club's matches have been played from `from_gw`
    onward - the correct denominator for a player who was not there for
    the whole season (see plan §2.1 / spec §2.1 start_rate)."""
    if from_gw is None:
        from_gw = 1
    return sum(
        1 for fx in ctx.fixtures
        if fx.get("event") and fx["event"] >= from_gw
        and team_id in (fx["team_h"], fx["team_a"])
        and ctx._is_played(fx)
    )


def raw_rows(ctx, pos, live, min_minutes=1, proj=None, next_gw=None,
             market=None, baselines=None, priors=None):
    """One row per player at `pos` with at least `min_minutes`, carrying
    every directly observed field. No percentile, z-score, hit rate or
    archetype yet - see `apply_derivations`, since all four depend on
    whichever subset of the pool is currently filtered in, not on the full
    league.

    `proj`/`next_gw`/`market`/`baselines`/`priors` are optional and only
    feed the `xp` column (plan §2.8: the dashboard's one shared expected-
    points model, transfers.candidate_score, appears here as a column
    never an axis or a sort default - a second scorer is not being
    introduced). Deliberately called *without* per-player match history,
    the same choice chips.py already makes for market-wide candidate pools
    rather than one manager's owned fifteen (see shared-scorer-architecture
    memory) - Scout compares many players symmetrically, none of them the
    "owned squad" that history-backed scoring exists to protect. Omit any
    of the five and every row's xp is 0.0, which is the honest value for
    "no fixture is priced for this gameweek" rather than a placeholder."""
    rows = []
    for el in ctx.players.values():
        if ctx.pos(el) != pos:
            continue
        minutes = el.get("minutes", 0)
        if minutes < min_minutes:
            continue
        pid = el["id"]
        matches = sorted(live.get(pid, []), key=lambda m: m["gw"])
        starts = el.get("starts", 0)
        first_start = next((m["gw"] for m in matches if m["status"] == "started"), None)
        team_matches = _team_played_since(ctx, el["team"], first_start)
        team_matches_total = _team_played_since(ctx, el["team"], None)
        started_matches = [m for m in matches if m["status"] == "started"]
        hit_n = len(started_matches)
        hits = sum(1 for m in started_matches if m["defconHit"])
        flag, news = "", ""
        chance = el.get("chance_of_playing_next_round")
        status = el.get("status", "a")
        if status == "i":
            flag, news = "injured", el.get("news", "")
        elif status == "s":
            flag, news = "suspended", el.get("news", "")
        elif chance is not None and chance < 100:
            flag, news = "doubtful", el.get("news", "")
        xp_val = 0.0
        if proj is not None and next_gw is not None and market is not None and baselines is not None:
            xp_result = transfers.candidate_score(
                el, ctx, proj, next_gw, market, baselines, priors)
            if xp_result:
                xp_val = xp_result["total"]
        rows.append({
            "id": pid,
            "webName": el["web_name"],
            "teamId": el["team"],
            "teamShort": ctx.team_name(el["team"]),
            "price": el["now_cost"] / 10.0,
            # Same convention as analysis.price_watch: this event's transfers
            # in minus out, signed net pressure rather than either alone.
            "priceChangeMomentum": (
                el.get("transfers_in_event", 0) - el.get("transfers_out_event", 0)),
            "ownership": round(analysis.f(el.get("selected_by_percent")), 1),
            "starts": starts,
            "teamMatchesSinceFirstStart": team_matches,
            "minutes": minutes,
            "minutesPerStart": round((minutes / starts) if starts else 0.0, 1),
            "startRate": round((starts / team_matches) if team_matches else 0.0, 3),
            # Bootstrap already carries this per-90, unlike bps/bonus/cards
            # below - reading it straight off avoids quietly disagreeing
            # with FPL's own rounding of the same figure.
            "defcon90": round(el.get("defensive_contribution_per_90", 0.0) or 0.0, 2),
            "xgi90": round(el.get("expected_goal_involvements_per_90", 0.0) or 0.0, 2),
            "xgc90": round(el.get("expected_goals_conceded_per_90", 0.0) or 0.0, 2),
            "bps90": round(analysis.per90(el.get("bps", 0), minutes), 2),
            "bonus90": round(analysis.per90(el.get("bonus", 0), minutes), 2),
            "cards90": round(analysis.per90(
                el.get("yellow_cards", 0) + el.get("red_cards", 0), minutes), 2),
            "defconHitRate": round((hits / hit_n) if hit_n else 0.0, 3),
            "defconHitN": hit_n,
            "defconHits": hits,
            "xp": round(xp_val, 2),
            "onCorners": bool(el.get("corners_and_indirect_freekicks_order")),
            "onFreeKicks": bool(el.get("direct_freekicks_order")),
            "onPens": bool(el.get("penalties_order")),
            "availability": flag or "available",
            "news": news,
            "matches": matches,
            "_teamMatchesTotal": team_matches_total,
        })
    return rows


def percentile_rank(values, v):
    """0..100, "share of the pool at or below this value" - ties split the
    difference so a three-way tie does not silently favour whichever value
    happens to be compared first."""
    n = len(values)
    if n <= 1:
        return 100.0 if n else 0.0
    below = sum(1 for x in values if x < v)
    equal = sum(1 for x in values if x == v)
    return 100.0 * (below + 0.5 * equal) / n


def zscore(values, v):
    n = len(values)
    if n < 2:
        return 0.0
    mean = statistics.mean(values)
    sd = statistics.pstdev(values)
    return (v - mean) / sd if sd else 0.0


def hero_x_key(rows):
    """'defcon_hit_rate' once the filtered pool has enough football behind
    it, else 'defcon90' - see HERO_GATE_MINUTES and plan §2.1. Gated on the
    *median* player's minutes so one or two nailed-on starters cannot pull
    the whole pool's axis over early."""
    if not rows:
        return "defcon90"
    med = statistics.median(r["minutes"] for r in rows)
    return "defcon_hit_rate" if med >= HERO_GATE_MINUTES else "defcon90"


# A couple of METRICS keys are spelled differently on the raw row, purely
# for readability elsewhere (rows are camelCase to match the JSON they
# become; metric keys are snake_case to read as axis/column identifiers).
# This is the one place that has to know both spellings.
_METRIC_FIELD = {
    "defcon_hit_rate": "defconHitRate",
    "start_rate": "startRate",
    "minutes_per_start": "minutesPerStart",
}


def _field(key):
    return _METRIC_FIELD.get(key, key)


# "Top third of the pool" (spec §3.4/§4) means exactly this once every
# metric is already expressed as a percentile rank against that pool -
# no second pass of sorting-and-slicing is needed, or correct: sorting
# percentiles-of-percentiles would double-apply the pool-relative step.
ARCHETYPE_PERCENTILE_FLOOR = 200.0 / 3.0


def apply_derivations(rows, archetypes):
    """Percentile ranks, z-scores, solidity and archetype membership,
    computed against exactly the rows passed in. Call this again after
    every filter change - never reuse a percentile computed against a
    different pool, per spec §2.1. Mutates and returns `rows`.

    `archetypes` is {name: driving_metric_key}, e.g. PositionConfig.archetypes,
    where a driving metric is either a METRICS key or the literal
    'solidity_pct'. Archetype membership additionally requires
    RATE_MIN_MINUTES of its own (spec's "top third" rule assigns near-
    randomly at n=2 matches - see plan §2.1), so a thin sample is never
    badged into an archetype it has not actually earned."""
    if not rows:
        return rows

    xgc_values = [r["xgc90"] for r in rows]
    for r in rows:
        # Inverted: a low xGC is a *high* solidity percentile. This is the
        # bubble-size metric, and raw xGC spans roughly 0.8-1.6 - invisible
        # as area without the inversion and the percentile mapping (spec §4.2).
        r["solidityPct"] = round(100.0 - percentile_rank(xgc_values, r["xgc90"]), 1)

    # xp is included here so its heatmap cell shades like every other
    # column - plan §2.8 only bars it from being an axis, a z-bar band or
    # a default sort, not from a percentile it is entitled to like anything
    # else in the table.
    metric_keys = list(METRICS)
    pool_values = {key: [r[_field(key)] for r in rows] for key in metric_keys}

    for r in rows:
        pct, z = {}, {}
        for key in metric_keys:
            invert = METRICS[key][1]
            val = r[_field(key)]
            vals = pool_values[key]
            p = percentile_rank(vals, val)
            pct[key] = round((100.0 - p) if invert else p, 1)
            zz = zscore(vals, val)
            z[key] = round(-zz if invert else zz, 2)
        pct["solidity_pct"] = r["solidityPct"]
        r["percentiles"] = pct
        r["z"] = z

    for r in rows:
        eligible = r["minutes"] >= RATE_MIN_MINUTES
        r["archetypes"] = [
            name for name, metric in archetypes.items()
            if eligible and r["percentiles"].get(metric, 0.0) >= ARCHETYPE_PERCENTILE_FLOOR
        ]
    return rows


def fixture_rows(team_short, proj, start_gw, weeks=6):
    """Clean-sheet difficulty and DEFCON difficulty, one row of each per
    gameweek, 1..5, higher always meaning harder - spec §3.2's two-metric
    fixture rule, never collapsed into one ticker.

    Clean-sheet difficulty reuses ticker.py's own CS anchors, so a fixture
    reads the same number here as it does in the existing ticker. DEFCON
    difficulty has no real data source (plan §2.6): it is modelled from the
    opponent's own expected goals in the same fixture, using the same XG
    anchors ticker.py already uses for attack - a stronger attacking
    opponent means more clearances, blocks and tackles for this club's
    defence, which is why the two rows point in opposite directions exactly
    as spec §3.2 requires. Every consumer must present this row as modelled,
    not measured (see the GW10 revisit note in the plan)."""
    out = []
    for fx in ffs.ticker(proj, team_short, start_gw, weeks):
        if fx.get("blank"):
            out.append({"gw": fx["gw"], "blank": True})
            continue
        cs_ease = _clamp01(
            (fx["cs"] / 100.0 - ticker.CS_LOW) / (ticker.CS_HIGH - ticker.CS_LOW))
        cs_diff = max(1, min(5, int((1 - cs_ease) * 5) + 1))
        opp_row = proj.get((fx["opp"], fx["gw"]))
        opp_xg = float(opp_row.get("g") or 0) if opp_row else 0.0
        dc_ease = _clamp01((opp_xg - ticker.XG_LOW) / (ticker.XG_HIGH - ticker.XG_LOW))
        dc_diff = max(1, min(5, int((1 - dc_ease) * 5) + 1))
        out.append({
            "gw": fx["gw"], "opp": fx["opp"], "home": fx["home"],
            "cleanSheetDifficulty": cs_diff,
            "defconDifficulty": dc_diff,
        })
    return out


def pool(ctx, pos, live, proj, min_minutes=1, next_gw=None, market=None,
         baselines=None, priors=None):
    """Everything scout.js needs for one position: the full raw pool (only
    gated on `min_minutes`, never on the *adjustable* filters - see
    DEFAULT_FILTERS), fixtures out to MAX_FIXTURE_HORIZON, and the config
    the client-side filter bar and archetype badges need.

    Deliberately un-filtered and un-derived beyond that gate: percentiles,
    z-scores, archetypes and the hero axis are all relative to whichever
    pool is currently filtered in (spec §2.1), so baking today's default
    filter into the payload would leave the browser with nothing to reveal
    the moment someone loosens a filter. scout.js runs _apply_filters,
    apply_derivations and hero_x_key itself, starting from `defaultFilters`
    on first draw and again on every change - those three Python functions
    exist to be the reference those JS ports are checked against.

    `next_gw`/`market`/`baselines`/`priors` are optional and only feed the
    `xp` column (see raw_rows) - omit them and every row's xp is 0.0."""
    cfg = POSITIONS[pos]
    rows = raw_rows(ctx, pos, live, min_minutes=min_minutes, proj=proj,
                    next_gw=next_gw, market=market, baselines=baselines,
                    priors=priors)
    start_gw = (ctx.current_event() or 1) + 1
    for r in rows:
        r["fixtures"] = fixture_rows(r["teamShort"], proj, start_gw, MAX_FIXTURE_HORIZON)
    return {
        "pos": pos,
        "label": cfg.label,
        "heroY": cfg.hero_y,
        "defconThreshold": cfg.defcon_threshold,
        "metrics": cfg.metrics,
        "archetypes": cfg.archetypes,
        "defaultFilters": DEFAULT_FILTERS,
        "rows": rows,
    }


def _apply_filters(rows, filters):
    price_min = filters.get("priceMin")
    price_max = filters.get("priceMax")
    min_start_rate = filters.get("minStartRate", 0.6)
    min_mins_per_start = filters.get("minMinutesPerStart")
    team = filters.get("team")
    out = []
    for r in rows:
        if price_min is not None and r["price"] < price_min:
            continue
        if price_max is not None and r["price"] > price_max:
            continue
        if min_start_rate is not None and r["startRate"] < min_start_rate:
            continue
        if min_mins_per_start is not None and r["minutesPerStart"] < min_mins_per_start:
            continue
        if team is not None and r["teamId"] != team:
            continue
        out.append(r)
    return out
