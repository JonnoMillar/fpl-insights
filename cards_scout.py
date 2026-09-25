"""Cards for the Scout tab: the position labs and fixture runs."""

import json

import components
import scout
from cards_common import e


# --- scout section ----------------------------------------------------------
#
# "Which defender do I actually buy" - a position comparison lab, built
# position-agnostic from the start (scout.py POSITIONS) so a second position
# is a config entry rather than a second implementation. See
# docs/superpowers/plans/2026-09-08-scout-section-plan.md.


def _scout_filter_bar(data):
    """Four controls for the pool explorer: price range, minimum start
    rate, minimum minutes per start (in place of role - see plan §2.3, cut
    for lacking any FPL data source), and team. Server-rendered like the
    rest of the page's controls; scout.js owns the listeners and every
    recompute that follows a change.

    The fixture horizon used to live here and did nothing visible, because
    nothing on this view shows a fixture. It now sits on the fixture-runs
    card, next to the thing it actually changes."""
    teams = sorted(
        {(r["teamId"], r["teamShort"]) for r in data["rows"]}, key=lambda t: t[1]
    )
    team_opts = "".join(
        f'<option value="{tid}">{e(short)}</option>' for tid, short in teams
    )
    return (
        '<div class="scoutfilters" role="group" aria-label="Filters">'
        '<label class="sf">Price'
        '<span class="sf-range"><input type="number" class="sf-price-min" '
        'step="0.5" min="3.5" max="15" placeholder="min">'
        '<input type="number" class="sf-price-max" step="0.5" min="3.5" '
        'max="15" placeholder="max"></span></label>'
        '<label class="sf">Min start rate'
        '<span class="sf-range"><input type="range" class="sf-start-rate" '
        'min="0" max="1" step="0.05" value="0.6">'
        '<span class="sf-start-rate-val tnum">60%</span></span></label>'
        '<label class="sf">Min minutes/start'
        '<input type="number" class="sf-mins-per-start" step="5" min="0" '
        'placeholder="any"></label>'
        f'<label class="sf">Team<select class="sf-team">'
        f'<option value="">All</option>{team_opts}</select></label>'
        '<span class="sf-count tnum" aria-live="polite"></span>'
        "</div>"
    )


def _scout_fixture_card(runs):
    """Two ranked club lists: kindest clean-sheet run, kindest run for
    defensive contributions, over a horizon the reader picks.

    Two lists rather than one blended column because the two genuinely
    point in opposite directions (spec §3.2) - the clubs whose defenders
    are likeliest to keep a clean sheet are usually the clubs whose
    defenders will have least to do. A club sitting near the top of one
    list and the bottom of the other is the useful thing to notice, and a
    single combined number would erase it.

    Ranked in the browser so the horizon selector re-ranks immediately,
    the same shape as ticker.js's own games-count control."""
    if not runs:
        return ""
    horizon_opts = "".join(
        f'<option value="{n}"{" selected" if n == 6 else ""}>next {n}</option>'
        for n in range(1, scout.MAX_FIXTURE_HORIZON + 1)
    )
    return (
        '<section class="card scoutfx">'
        f'<div class="card-head"><h2>Fixture runs{components.info_btn()}</h2>'
        '<span class="sub" hidden>Difficulty runs 1 to 5, lower is kinder, '
        "and the number is printed in every cell. Contribution difficulty is "
        "modelled from the opponent's expected goals rather than measured, "
        'so read it as a steer, not a stat.</span>'
        f'<label class="sf sf-inline">Horizon<select class="sf-horizon">'
        f"{horizon_opts}</select></label>"
        "</div>"
        '<div class="card-body"><div class="fxruns">'
        '<div class="fxrun-col"><h4>Kindest for clean sheets</h4>'
        '<ol class="fxrun-list" data-metric="cs"></ol></div>'
        '<div class="fxrun-col"><h4>Most to defend against'
        ' <span class="fxrun-tag">modelled</span></h4>'
        '<ol class="fxrun-list" data-metric="dc"></ol></div>'
        "</div>"
        f'<script type="application/json" class="scout-fixtures">'
        f"{json.dumps(runs)}</script>"
        "</div></section>"
    )


def _scout_heatmap_shell(data):
    """`<table>` shell with the header row rendered server-side - column
    order is fixed by PositionConfig.metrics, so nothing about it depends
    on the current filter. scout.js only ever touches `<tbody>`. The
    leftmost column is a shortlist checkbox, capped at six (spec §5) - the
    Level 2 compare view below appears once two or more are ticked."""
    head_cells = "".join(
        f'<th data-sort="{e(key)}" role="button" tabindex="0">'
        f'{e(scout.METRICS[key][0])}</th>'
        for key in data["metrics"]
    )
    return (
        '<div class="scroll scoutheat"><table class="scoutheatmap">'
        '<thead><tr><th class="scoutpick-h" aria-label="Shortlist"></th>'
        '<th data-sort="webName" role="button" tabindex="0">Player</th>'
        '<th data-sort="price" role="button" tabindex="0">Price</th>'
        f"{head_cells}"
        "<th>Archetype</th></tr></thead>"
        '<tbody></tbody></table></div>'
    )


def scout_section(scout_pools, fixture_runs=None, owned_ids=frozenset()):
    """One lab per position in `scout_pools` ({pos: scout.pool(...) dict}).

    Three chapters rather than one wall. The leaderboards and the fixture
    runs answer the questions someone opens this tab with and are readable
    at a glance; the full pool - scatter, heatmap, shortlist compare - sits
    behind a disclosure for when the summary is not enough. That is the
    same split the Squad tab already makes with its own Squad detail table,
    and the leaderboards borrow the League leaders card outright, because
    these are four separate questions rather than four columns of one."""
    if not scout_pools:
        return ""
    parts = []
    for pos, data in scout_pools.items():
        label = data["label"]
        singular = label.lower().rstrip("s")
        groups = scout.leader_groups(data["rows"], owned_ids=owned_ids)
        parts.append(
            f'<div class="chapter"><h2>{e(label)}</h2>'
            '<span class="sub">Four questions kept separate rather than '
            "blended into one rating: contributions, threat, solidity and "
            "minutes pull against each other, and averaging them hides the "
            "trade-off you are choosing between.</span></div>"
            + components.stat_leaders(
                groups,
                title=f"{label} worth a look",
                sub=("Ranked on each measure on its own, over "
                     f"{scout.RATE_MIN_MINUTES} minutes so a cameo cannot top "
                     "a column. Players you already own are marked."),
                # Said on the face of the card, not behind the info button.
                # Every column here is a rate off a handful of matches this
                # early, and a leaderboard reads as settled fact unless it
                # says otherwise.
                lede=(f"Two or three matches of evidence each. Treat the "
                      f"order as a shortlist to look into, not a ranking - "
                      f"the {scout.RATE_MIN_MINUTES}-minute floor keeps the "
                      f"cameos out but cannot make a small sample big."),
            )
            + '<div class="chapter"><h2>Fixture runs</h2>'
            '<span class="sub">Which defences have the kind run, and which '
            "have the run that actually generates defensive "
            "contributions.</span></div>"
            + _scout_fixture_card(fixture_runs)
            + '<div class="chapter"><h2>Explore the pool</h2>'
            f'<span class="sub">Every {e(singular)} with a minute played, '
            "filtered how you like. Click any name for his match-by-match "
            "card, or pick up to six to compare side by side.</span></div>"
            f'<div class="scoutlab" data-pos="{e(pos)}">'
            f'<script type="application/json" class="scout-data" '
            f'data-pos="{e(pos)}">{json.dumps(data)}</script>'
            # Open by default. Collapsed, the most capable thing on the tab
            # was a title and a triangle - no row count, no hint of a
            # scatter, filters or a six-way compare behind it, and nothing
            # to suggest opening it was worth doing.
            '<details class="card collapsible scoutexplorer" open>'
            f'<summary class="card-head"><h2>All {e(label.lower())}'
            f"{components.info_btn()}</h2>"
            f'<span class="subvis">Sorted by projected points, not by club. '
            f'{len(data["rows"])} {e(singular)}s in the pool; the start-rate '
            f'filter below hides the fringe by default. Click a name for his '
            f'match log, or tick up to six to compare.</span>'
            '<span class="sub" hidden>The scatter puts defensive '
            "contribution against attacking threat, with bubble size for how "
            "little the club concedes. Everyone else is one row of the table "
            "below it.</span></summary>"
            '<div class="card-body">'
            + _scout_filter_bar(data)
            + '<svg class="scoutscatter" viewBox="0 0 1040 520" role="img" '
            f'aria-label="{e(label)} comparison scatter"></svg>'
            '<p class="legend">'
            '<span class="key key-solid"></span>Enough minutes to trust the rate'
            '<span class="key key-thin"></span>Below the minutes floor'
            '<span class="key key-size"></span>Bigger bubble concedes less'
            "</p>"
            + _scout_heatmap_shell(data)
            + '<p class="scoutcomparebar" hidden>'
            '<span class="scb-count"></span>'
            '<button type="button" class="scb-clear">Clear shortlist</button>'
            "</p>"
            "</div></details>"
            '<section class="card scoutcompare" hidden>'
            f'<div class="card-head"><h2>Shortlist{components.info_btn()}</h2>'
            '<span class="sub" hidden>Each bar is distance from the filtered '
            "pool's own average on one shared scale. Right is always better, "
            "including for the two measures where a lower raw number is the "
            'good one.</span></div>'
            '<div class="card-body">'
            '<div class="scoutzbars"></div>'
            '<h4 class="scoutsub">Fixtures, both directions</h4>'
            '<div class="scoutticker"></div>'
            "</div></section>"
            "</div>"
        )
    # One shared card for every position and every player in every pool -
    # filled on demand from whichever row was clicked, the same "one dialog,
    # many payloads" shape as dialog.pv (dashboard.py:player_dialog), but a
    # separate element and a separate JSON path rather than an extension of
    # it. Reusing that dialog verbatim would mean giving it match-history
    # data for the whole pool - 130+ defenders, not just the owned fifteen -
    # which only exists today via one element_summary call per player.
    # scout.py's season_live already covers the same ground in one call per
    # gameweek for the entire league (see plan §1), so this card is built
    # entirely from data already sitting in each pool row.
    parts.append(
        '<dialog class="scoutpv" aria-label="Player detail">'
        '<button class="scpv-close" aria-label="Close player detail">&times;</button>'
        '<div class="scpv-body"></div></dialog>'
    )
    return "".join(parts)
