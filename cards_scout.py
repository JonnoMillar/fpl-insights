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


def _scout_fixture_card(runs, cfg):
    """Two ranked club lists over a horizon the reader picks, each reading
    one difficulty from the position's own `fixture_lists`.

    Two lists rather than one blended column because the two questions
    genuinely pull apart (spec §3.2) - the clubs whose defenders are
    likeliest to keep a clean sheet are usually the clubs whose defenders
    will have least to do. A club near the top of one list and the bottom
    of the other is the useful thing to notice, and a single combined
    number would erase it. Forwards have one question, not two, so their
    second list is the same question upside down: the runs to avoid.

    Ranked in the browser so the horizon selector re-ranks immediately,
    the same shape as ticker.js's own games-count control. The runs
    themselves are one data island shared by every position's card."""
    if not runs:
        return ""
    horizon_opts = "".join(
        f'<option value="{n}"{" selected" if n == 6 else ""}>next {n}</option>'
        for n in range(1, scout.MAX_FIXTURE_HORIZON + 1)
    )
    cols = "".join(
        f'<div class="fxrun-col"><h4>{e(fl["title"])}'
        + (' <span class="fxrun-tag">modelled</span>' if fl.get("modelled") else "")
        + f'</h4><ol class="fxrun-list" data-fx="{e(fl["fx"])}"'
        + (' data-hardest="1"' if fl.get("hardest") else "")
        + "></ol></div>"
        for fl in cfg.fixture_lists
    )
    modelled = any(fl.get("modelled") for fl in cfg.fixture_lists)
    return (
        '<section class="card scoutfx">'
        f'<div class="card-head"><h2>Fixture runs{components.info_btn()}</h2>'
        '<span class="sub" hidden>Difficulty runs 1 to 5, lower is kinder, '
        "and the number is printed in every cell. Capitals are home games."
        + (" Contribution difficulty is modelled from the opponent's expected "
           "goals rather than measured, so read it as a steer, not a stat."
           if modelled else "")
        + '</span>'
        f'<label class="sf sf-inline">Horizon<select class="sf-horizon">'
        f"{horizon_opts}</select></label>"
        "</div>"
        f'<div class="card-body"><div class="fxruns">{cols}</div>'
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


# One line under each chapter heading, per position. Short on purpose: the
# cards below say the rest, and the info buttons carry the method.
_CHAPTER_SUBS = {
    "DEF": ("Contributions, threat, solidity and minutes, each ranked on its own.",
            "Kind runs for clean sheets, and busy ones for defensive contributions."),
    "MID": ("Goals, chances, defensive work and minutes, each ranked on its own.",
            "Where the goals are, and where the defensive work is."),
    "FWD": ("Goals, chances, bonus and minutes, each ranked on its own.",
            "The runs to buy into, and the runs to steer clear of."),
}


def _scout_position_switch(scout_pools):
    """The three labs as one segmented control, rather than three labs
    stacked down one tab. Stacked, the Scout tab was three times the height
    of any other with the same three chapters repeating, and the question
    anyone opens it with is about one position at a time."""
    btns = "".join(
        f'<button type="button" role="tab" data-pos="{e(pos)}" '
        f'aria-selected="{"true" if i == 0 else "false"}">'
        f'<span class="scoutpos-code">{e(pos)}</span>'
        f'<span class="scoutpos-label">{e(data["label"])}</span>'
        f'<span class="scoutpos-n tnum">{len(data["rows"])}</span>'
        "</button>"
        for i, (pos, data) in enumerate(scout_pools.items())
    )
    return (f'<div class="scoutpos" role="tablist" aria-label="Position">'
            f"{btns}</div>")


def _scout_lab(pos, data, fixture_runs, owned_ids):
    """Leaders, fixture runs and the pool explorer for one position."""
    cfg = scout.POSITIONS[pos]
    label = data["label"]
    singular = label.lower().rstrip("s")
    groups = scout.leader_groups(data["rows"], owned_ids=owned_ids, pos=pos)
    played = max((r["teamMatches"] for r in data["rows"]), default=0)
    lead_sub, fx_sub = _CHAPTER_SUBS.get(pos, ("", ""))
    return (
        '<div class="chapter"><h2>Worth a look</h2>'
        f'<span class="sub">{e(lead_sub)}</span></div>'
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
            lede=(f"{played} matches in, at most. A shortlist to look "
                  "into, not a ranking."),
        )
        + '<div class="chapter"><h2>Fixture runs</h2>'
        f'<span class="sub">{e(fx_sub)}</span></div>'
        + _scout_fixture_card(fixture_runs, cfg)
        + '<div class="chapter"><h2>Explore the pool</h2>'
        f'<span class="sub">Every {e(singular)} who has played. Click a '
        "name for his match log, or tick up to six to compare.</span></div>"
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
        f'<span class="subvis">{len(data["rows"])} {e(singular)}s, sorted '
        "by projected points. The start-rate filter hides the fringe.</span>"
        f'<span class="sub" hidden>The scatter puts '
        f"{e(scout.METRICS[cfg.hero_y][0])} up the side against "
        + ("defensive contribution along the bottom"
           if cfg.hero_x == scout.HERO_X_DEFCON
           else e(scout.METRICS[cfg.hero_x][0]) + " along the bottom")
        + f". {e(cfg.size_label)}. Everyone is also one row of the table "
        "below it, shaded by where he sits in the filtered pool.</span>"
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

    Three chapters per lab rather than one wall. The leaderboards and the
    fixture runs answer the questions someone opens this tab with and are
    readable at a glance; the full pool - scatter, heatmap, shortlist
    compare - comes after, for when the summary is not enough. The
    leaderboards borrow the League leaders card outright, because these are
    four separate questions rather than four columns of one."""
    if not scout_pools:
        return ""
    views = "".join(
        f'<div class="scoutview" data-pos="{e(pos)}"{"" if i == 0 else " hidden"}>'
        + _scout_lab(pos, data, fixture_runs, owned_ids)
        + "</div>"
        for i, (pos, data) in enumerate(scout_pools.items())
    )
    return (
        _scout_position_switch(scout_pools)
        + views
        # Fixture runs are per club, not per position, so they are embedded
        # once and every lab's card ranks the same runs its own way.
        + (f'<script type="application/json" class="scout-fixtures">'
           f"{json.dumps(fixture_runs)}</script>" if fixture_runs else "")
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
