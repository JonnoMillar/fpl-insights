"""Cards for the Scout tab: the position labs and fixture runs."""


import components
import scout
from cards_common import e, script_json


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
    recompute that follows a change. Fixture runs live on the Planning tab's
    band, so there is no horizon control here."""
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


def _scout_position_switch(scout_pools):
    """The three labs as one segmented control, rather than three labs
    stacked down one tab. Stacked, the Scout tab was three times the height
    of any other with the same three chapters repeating, and the question
    anyone opens it with is about one position at a time."""
    # Roving tabindex: only the selected tab sits in the Tab order, and
    # scout.js moves it with the arrow keys and on every switch.
    btns = "".join(
        f'<button type="button" role="tab" data-pos="{e(pos)}" '
        f'id="scoutpos-tab-{e(pos)}" aria-controls="scoutview-{e(pos)}" '
        f'tabindex="{0 if i == 0 else -1}" '
        f'aria-selected="{"true" if i == 0 else "false"}">'
        f'<span class="scoutpos-code">{e(pos)}</span>'
        f'<span class="scoutpos-label">{e(data["label"])}</span>'
        f'<span class="scoutpos-n tnum">{len(data["rows"])}</span>'
        "</button>"
        for i, (pos, data) in enumerate(scout_pools.items())
    )
    return (f'<div class="scoutpos" role="tablist" aria-label="Position">'
            f"{btns}</div>")


def _scout_lab(pos, data, owned_ids):
    """Leaders, then the pool explorer, for one position. Fixture runs
    live on the Planning tab's band."""
    cfg = scout.POSITIONS[pos]
    label = data["label"]
    groups = scout.leader_groups(data["rows"], owned_ids=owned_ids, pos=pos)
    return (
        components.stat_leaders(
            groups,
            title="Leaders",
            sub=(f"Over {scout.RATE_MIN_MINUTES} minutes and "
                 f"{scout.LEADER_MIN_STARTS} starts. Yours are marked."),
        )
        + f'<div class="scoutlab" data-pos="{e(pos)}">'
        f'<script type="application/json" class="scout-data" '
        f'data-pos="{e(pos)}">{script_json(data)}</script>'
        # Open by default. Collapsed, the most capable thing on the tab
        # was a title and a triangle - no row count, no hint of a
        # scatter, filters or a six-way compare behind it, and nothing
        # to suggest opening it was worth doing.
        f'<details class="card collapsible scoutexplorer" id="scout-explorer-{e(pos)}" open>'
        f'<summary class="card-head"><h2>All {e(label.lower())}</h2>'
        "</summary>"
        '<div class="card-body">'
        + _scout_filter_bar(data)
        + '<svg class="scoutscatter" viewBox="0 0 1040 520" role="img" '
        f'aria-label="{e(label)} comparison scatter"></svg>'
        '<p class="legend">'
        '<span class="key key-solid"></span>Enough minutes to trust the rate'
        '<span class="key key-thin"></span>Below the minutes floor'
        f'<span class="key key-size"></span>{e(cfg.size_label)}'
        "</p>"
        + '<p class="scoutcomparebar" hidden>'
        '<span class="scb-count" aria-live="polite"></span>'
        f'<a class="scb-compare" data-dashboard-jump href="#scout-compare-{e(pos)}" hidden>Compare players</a>'
        '<button type="button" class="scb-clear">Clear shortlist</button>'
        "</p>"
        + _scout_heatmap_shell(data)
        + "</div></details>"
        f'<section class="card scoutcompare" id="scout-compare-{e(pos)}" hidden>'
        f'<div class="card-head"><h2>Shortlist{components.info_btn()}</h2>'
        '<span class="sub" hidden>Each bar is distance from the filtered '
        "pool's own average on one shared scale. Right is always better, "
        "including where a lower raw number is the good one.</span></div>"
        '<div class="card-body">'
        '<div class="scoutzbars"></div>'
        '<h4 class="scoutsub">Fixtures</h4>'
        '<div class="scoutticker"></div>'
        "</div></section>"
        "</div>"
    )


def scout_section(scout_pools, fixture_runs=None, owned_ids=frozenset()):
    """One lab per position in `scout_pools` ({pos: scout.pool(...) dict}),
    one visible at a time behind a position switch.

    The leaderboards answer the question someone opens this tab with at a
    glance; the full pool - scatter, heatmap, shortlist compare - comes
    after, for when the summary is not enough."""
    if not scout_pools:
        return ""
    views = "".join(
        f'<div class="scoutview" data-pos="{e(pos)}" id="scoutview-{e(pos)}" '
        f'role="tabpanel" aria-labelledby="scoutpos-tab-{e(pos)}"'
        f'{"" if i == 0 else " hidden"}>'
        + _scout_lab(pos, data, owned_ids)
        + "</div>"
        for i, (pos, data) in enumerate(scout_pools.items())
    )
    return (
        _scout_position_switch(scout_pools)
        + views
        # Fixture runs are per club, not per position, so they are embedded
        # once for every lab's shortlist strip to look a club up in.
        + (f'<script type="application/json" class="scout-fixtures">'
           f"{script_json(fixture_runs)}</script>" if fixture_runs else "")
        # One shared card for every position and every player in every pool -
        # filled on demand from whichever row was clicked, the same "one
        # dialog, many payloads" shape as dialog.pv (dashboard.py:
        # player_dialog), but a separate element and a separate JSON path
        # rather than an extension of it. Reusing that dialog verbatim would
        # mean giving it match-history data for the whole pool - 400 players,
        # not just the owned fifteen - which only exists today via one
        # element_summary call per player. scout.py's season_live already
        # covers the same ground in one call per gameweek for the entire
        # league (see plan §1), so this card is built entirely from data
        # already sitting in each pool row.
        + '<dialog class="scoutpv" aria-label="Player detail">'
        '<button class="scpv-close" aria-label="Close player detail">&times;</button>'
        '<div class="scpv-body"></div></dialog>'
    )
