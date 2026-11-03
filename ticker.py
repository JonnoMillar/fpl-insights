#!/usr/bin/env python3
"""
Fixture difficulty, and what the market makes of the coming round.

The previous ticker asked you to choose between shading by clean sheet and
shading by goals, which is not a choice anyone wants to make while reading a
table - and it painted the good cells almost black, so a run of easy fixtures
was a wall of dark squares. Both are gone.

There is now one number per fixture: how good it is to own a player from that
club, 0 to 10, higher is better. It is mostly an absolute read - expected
goals and clean-sheet chance against fixed league-wide anchors, weighted
55/45 toward attack, because most of a squad scores its points at the other
end - because that is what the question actually is: a strong side's floor
usually beats a weak side's ceiling, so "who should I buy from" needs to stay
answered in real terms, not just "is this normal for them."

A smaller slice (see BLEND_WEIGHT) compares the same fixture against the
club's own season norm for that venue instead (home and away kept separate,
since a side's home and away level genuinely differ - see relative_rating).
That nudges the score for a fixture that is unusually kind or harsh for this
specific club, without ever letting "better than usual for a weak side"
outrank "actually good in absolute terms" - see blended_rating.

Where the betting market has priced a fixture its numbers are used; beyond
that, Fantasy Football Scout's model fills in, and the cell says which.

Colours are light throughout, with dark text - a rating is read from the
number, and the fill is there to let a run of green or a run of red show up
when you glance down a row.
"""

import html

import components
import ffs

# Anchors for the two components. Roughly the 10th and 90th percentile of a
# Premier League fixture, so most land inside and the extremes still separate.
XG_LOW, XG_HIGH = 0.65, 2.35
CS_LOW, CS_HIGH = 0.08, 0.55
ATTACK_WEIGHT = 0.55

# How much of the final score is the absolute read vs the club-relative one -
# deliberately lopsided. This is a "who should I buy from" card, and a strong
# side's ordinary week usually still outscores a weak side's best one, so
# absolute output has to keep the final say; the relative comparison only
# nudges it, it never overturns it.
BLEND_WEIGHT = 0.7

# Five solid bands, dark to bright: night for the hardest run, a grey, the
# paper neutral, then brand green and a deeper green for the kindest
# (adjacent steps differ in luminance - see scout.greyscale_readable). Lightness and
# saturation make a run visible down a column; the rating is printed in every
# cell, so the fill never carries the value alone. No red-to-green ramp.
SCALE = [
    (2.0, "#16001a", "#ffffff"),
    (4.0, "#6e6474", "#ffffff"),
    (6.0, "#eeecef", "#16001a"),
    (8.0, "#00ff87", "#16001a"),
    (10.1, "#2fbf7a", "#16001a"),
]


# A fixture this kind gets its own treatment rather than just the top step
# of the ordinary scale - the scale's job is to make a run of green or red
# visible down a column, and a 9+ is rare enough that it deserves to read
# as an event rather than blend into "also green".
PREMIUM_RATING = 9.0


def _cell_style(score):
    """(class, inline-style) for one rating - a class for a premium
    fixture, since a gradient reads badly as an inline string repeated on
    every such cell, otherwise the ordinary flat tone."""
    if score > PREMIUM_RATING:
        return "fx-premium", ""
    bg, fg = _tone(score)
    return "", "background:{};color:{}".format(bg, fg)


def _premium_star(cls):
    """A small star ahead of a premium-rated score, in place of the old
    gradient's own claim to being special - see _cell_style."""
    return '<i class="fx-star">&#9733;</i>' if cls == "fx-premium" else ""


def rating_pill(opp, home, score):
    if opp is None:
        return '<span class="rpill fxr-blank">Unavailable</span>'
    """A fixture chip using the same rating and ramp as the ticker, so a
    fixture looks the same wherever it appears."""
    cls, style = _cell_style(score)
    label = opp.upper() if home else opp.lower()
    # The star is the one glyph on the page with no legend beside it, so it
    # says what it means in its own tooltip rather than only in the CSS.
    star = _premium_star(cls)
    return (
        '<span class="rpill {cls}" style="{style}" '
        'title="{opp} {venue} - rating {score:.1f} of 10{starnote}">'
        "{label}<b>{star}{score:.1f}</b></span>".format(
            cls=cls, style=style, opp=e(opp),
            venue="at home (capitals)" if home else "away (lower case)",
            score=score, label=e(label), star=star,
            starnote=(", one of the very best on the board" if star else ""))
    )


def e(x):
    return html.escape(str(x), quote=True)


def _clamp01(v):
    return max(0.0, min(1.0, v))


def rating(xg, cs_pct):
    """One 0-10 score for how good a fixture is in absolute terms - how
    much a side is expected to score and keep out, full stop, against
    fixed league-wide anchors.

    This ranks *teams*, not fixtures: a genuinely strong side reads as a
    good fixture even against a tough opponent, because it correctly
    expects to score and defend well regardless of who it faces - which is
    exactly right for "who should I buy from", and exactly why it is the
    dominant term in blended_rating rather than being replaced outright by
    relative_rating. Also used alone for fixture_run_summary's "Expected
    output" column and FPL's own difficulty comparison."""
    attack = _clamp01((xg - XG_LOW) / (XG_HIGH - XG_LOW))
    defence = _clamp01((cs_pct / 100.0 - CS_LOW) / (CS_HIGH - CS_LOW))
    return 10.0 * (ATTACK_WEIGHT * attack + (1 - ATTACK_WEIGHT) * defence)


def _season_norms(proj):
    """Each club's own mean expected goals and clean-sheet chance across
    the whole season in `proj`, split home vs away - a side's home and away
    levels genuinely differ (crowd, no travel, and so on), so a fixture
    should be judged against whichever one it's actually being played
    under, not a blend of both.

    Both numbers are sourced from `proj` (FFS's own model) rather than
    real observed results, because `proj` is the only season-long feed
    that already tags every row with a venue - splitting real match xG by
    venue would mean an extra API call per player, for every player in the
    league, just for this. Returns (baseline_xg, club_mean_cs,
    league_avg_xg, league_avg_cs), the first two keyed
    {club: {"H": v, "A": v}}."""
    sums = {}
    for (club, _gw), row in proj.items():
        venue = "H" if (row.get("ven") or "H").upper() == "H" else "A"
        acc = sums.setdefault(club, {}).setdefault(venue, {"xg": 0.0, "cs": 0.0, "n": 0})
        acc["xg"] += float(row.get("g") or 0)
        acc["cs"] += float(row.get("cs") or 0)
        acc["n"] += 1

    baseline_xg, club_mean_cs = {}, {}
    league_xg_total, league_cs_total, league_n = 0.0, 0.0, 0
    for club, by_venue in sums.items():
        baseline_xg[club], club_mean_cs[club] = {}, {}
        for venue, acc in by_venue.items():
            if not acc["n"]:
                continue
            baseline_xg[club][venue] = acc["xg"] / acc["n"]
            club_mean_cs[club][venue] = acc["cs"] / acc["n"]
            league_xg_total += acc["xg"]
            league_cs_total += acc["cs"]
            league_n += acc["n"]
    league_avg_xg = league_xg_total / league_n if league_n else 1.45
    league_avg_cs = league_cs_total / league_n if league_n else 25.0
    return baseline_xg, club_mean_cs, league_avg_xg, league_avg_cs


def relative_rating(xg, cs_pct, baseline_xg, club_mean_cs):
    """How good this fixture is *for this club*, against its own season
    norm for the venue it's actually being played at - not how good the
    club is in absolute terms, and not blended across home and away. A
    fixture exactly at a club's own average (for that venue) scores a flat
    5 either half; an 80% swing either way moves that half from end to
    end, clamped there. `baseline_xg`/`club_mean_cs` are the single home
    or away number already selected by the caller - see _season_norms.
    Used alone nowhere on the page any more - see blended_rating."""
    attack = _clamp01((xg / baseline_xg - 0.6) / 0.8) if baseline_xg else 0.5
    defence = _clamp01((cs_pct / club_mean_cs - 0.6) / 0.8) if club_mean_cs else 0.5
    return 10.0 * (ATTACK_WEIGHT * attack + (1 - ATTACK_WEIGHT) * defence)


def blended_rating(xg, cs_pct, baseline_xg, club_mean_cs):
    """The rating actually shown everywhere on the page: mostly rating()
    (absolute output - who should I buy from), with a BLEND_WEIGHT-sized
    nudge from relative_rating (is this unusually kind or harsh for this
    specific club). Doing it this way round - absolute leading, relative
    nudging - keeps a strong side's ordinary week reading as better than a
    weak side's best one, which a pure relative score got backwards: Man
    City at home to a poor side scored below Fulham away to the same side,
    because 2.8 xG was merely "good for City" while 1.4 xG was "great for
    Fulham" - true, but not what "which club's players should I buy"
    needs to hear."""
    absolute = rating(xg, cs_pct)
    relative = relative_rating(xg, cs_pct, baseline_xg, club_mean_cs)
    return BLEND_WEIGHT * absolute + (1 - BLEND_WEIGHT) * relative


def _tone(score):
    for edge, bg, fg in SCALE:
        if score < edge:
            return bg, fg
    return SCALE[-1][1], SCALE[-1][2]


def _rows_for(club, proj, market, start_gw, weeks, baseline_xg=None, club_mean_cs=None):
    """Fixtures for one club, market first and model behind.

    `baseline_xg`/`club_mean_cs` are this club's own season norms, keyed
    by venue - {"H": v, "A": v} - so each row picks the one matching where
    that fixture is actually played (see relative_rating and
    _season_norms). Omit either to fall back to the absolute,
    team-ranking score instead."""
    out = []
    mk = (market or {}).get(club)
    for fx in ffs.ticker(proj, club, start_gw, weeks):
        if fx.get("blank"):
            out.append({
                "gw": fx["gw"], "opp": None, "home": None,
                "xg": 0.0, "cs": 0.0, "source": "blank",
                "score": 0.0, "blank": True,
            })
            continue
        xg, cs, source = fx["xg"], fx["cs"], "model"
        # The market only prices the imminent round, so it can only replace the
        # first cell - and only when the opponent matches, guarding against a
        # postponement putting the two sources out of step.
        if mk and not out and mk.get("opp") == fx["opp"]:
            xg, cs, source = mk["xg"], mk["cs"], "market"
        venue = "H" if fx["home"] else "A"
        bx = (baseline_xg or {}).get(venue)
        cm = (club_mean_cs or {}).get(venue)
        if bx and cm:
            score = blended_rating(xg, cs, bx, cm)
        else:
            score = rating(xg, cs)
        out.append({
            "gw": fx["gw"], "opp": fx["opp"], "home": fx["home"],
            "xg": xg, "cs": cs, "source": source,
            "score": score,
        })
    return out


def _club_norms(ctx, proj):
    """(baseline_xg, club_mean_cs) keyed by club short name, each a
    {"H": v, "A": v} dict, for relative_rating - each club's own
    season-long attack and defence norms, split by venue (_season_norms),
    with a league-wide fallback for a club/venue combination proj has no
    rows for."""
    baseline_xg, club_mean_cs, league_avg_xg, league_avg_cs = _season_norms(proj)
    for t in ctx.teams.values():
        club = t["short_name"]
        bx = baseline_xg.setdefault(club, {})
        bx.setdefault("H", league_avg_xg)
        bx.setdefault("A", league_avg_xg)
        cm = club_mean_cs.setdefault(club, {})
        cm.setdefault("H", league_avg_cs)
        cm.setdefault("A", league_avg_cs)
    return baseline_xg, club_mean_cs


FIXTURE_PAGE_SIZE = 8

# The selector's range is 1-8 games; the table always renders all 8 gameweek
# columns so the client can widen/narrow the window without a rebuild, but
# opens on FIXTURE_GAMES_DEFAULT so nothing on first paint looks different
# from before the selector existed.
FIXTURE_GAMES_MAX = 8
FIXTURE_GAMES_DEFAULT = 6

# A fixture below this doesn't get to hide behind a mediocre one any more
# when Target fixtures is on. Set from the shape of the score distribution
# itself: with the 70/30 absolute/relative blend, a single fixture only
# clears ~7.5 when a genuinely strong side is at home (or otherwise
# favoured) against a genuinely weak one - comfortably above what an
# average week for a good team looks like, so switching it on is a real
# filter, not one that leaves most of the board lit up.
TARGET_RATING = 7.5


def fixture_ticker(reports, ctx, proj, start_gw, weeks=FIXTURE_GAMES_MAX, market=None):
    """Every club in the league, not just yours - see fixture_run_summary
    for the same reasoning applied to the best/worst-run card. Twenty rows
    is too many to show at once without either a scrollbar or a wall of a
    table, so the card pages through FIXTURE_PAGE_SIZE at a time client
    side (ticker.js) rather than scrolling - sorted by rating first, so
    the page you land on is already the most useful one.

    All `weeks` (up to FIXTURE_GAMES_MAX) gameweek columns are always
    rendered, each fixture cell carrying its own score as `data-score` and
    a `fxc-target` class when it clears TARGET_RATING - ticker.js uses
    those to drive the games-count selector and the Target fixtures toggle
    without needing a second render."""
    if not proj:
        return ""
    owned = {}
    for r in reports:
        owned[r.team] = owned.get(r.team, 0) + 1
    baseline_xg, club_mean_cs = _club_norms(ctx, proj)

    rows = []
    for tid, t in ctx.teams.items():
        club = t["short_name"]
        cells = _rows_for(club, proj, market, start_gw, weeks,
                          baseline_xg.get(club), club_mean_cs.get(club))
        if not cells:
            continue
        default_cells = cells[:FIXTURE_GAMES_DEFAULT]
        avg = sum(c["score"] for c in default_cells) / len(default_cells)
        chips = []
        for c in cells:
            if c.get("blank"):
                chips.append(
                    '<td class="fxc fxc-blank" data-score="0" '
                    'title="GW{gw}, blank - no fixture">'
                    '<span class="fxc-opp">&mdash;</span></td>'.format(gw=c["gw"])
                )
                continue
            cls, style = _cell_style(c["score"])
            if c["score"] >= TARGET_RATING:
                cls = (cls + " fxc-target").strip()
            label = c["opp"].upper() if c["home"] else c["opp"].lower()
            mark = '<i class="fx-mkt" title="Priced by the market"></i>' if c["source"] == "market" else ""
            chips.append(
                '<td class="fxc {cls}" style="{style}" data-score="{score:.2f}" '
                'title="GW{gw}, {venue} to {opp} - rating {score:.1f} of 10, '
                '{xg:.2f} expected goals, {cs:.0f}% clean sheet ({src})">'
                '<span class="fxc-opp">{label}{mark}</span>'
                '<span class="fxc-score">{star}{score:.1f}</span></td>'.format(
                    cls=cls, style=style, gw=c["gw"],
                    venue="home" if c["home"] else "away", opp=e(c["opp"]),
                    score=c["score"], xg=c["xg"], cs=c["cs"], src=c["source"],
                    label=e(label), mark=mark, star=_premium_star(cls),
                )
            )
        acls, astyle = _cell_style(avg)
        own_n = owned.get(club, 0)
        own_cell = (
            f'<span class="fxown" title="{own_n} of your players">{own_n}</span>'
            if own_n else '<span class="fxown fxown-0">0</span>'
        )
        rows.append((
            avg, own_n,
            '<tr><td class="fxclub"><b>{club}</b></td>'
            '<td class="num" data-v="{own_n}">{own}</td>'
            '<td class="num fxavg-cell" data-v="{avg:.2f}">'
            '<span class="fxavg {acls}" style="{astyle}">{star}{avg:.1f}</span></td>'
            '{chips}</tr>'.format(
                club=e(club), own_n=own_n, own=own_cell, acls=acls, astyle=astyle,
                star=_premium_star(acls),
                avg=avg, chips="".join(chips)),
        ))
    if not rows:
        return ""
    rows.sort(key=lambda x: -x[0])
    heads = "".join(
        '<th scope="col" class="num">GW{}</th>'.format(g)
        for g in range(start_gw, start_gw + weeks)
    )
    # Deliberately not called "difficulty". The number here runs the opposite
    # way to FPL's own 1-to-5 FDR - ten is a great fixture, not a brutal one -
    # and heading a higher-is-better column "difficulty" invites exactly the
    # misreading it got: a club on 7.0 looks like the hard one when it is the
    # club with the kindest run on the page.
    page_count = -(-len(rows) // FIXTURE_PAGE_SIZE)  # ceil division
    nav = ""
    if page_count > 1:
        nav = (
            '<div class="fxnav">'
            '<button class="fxnav-btn" data-dir="-1" disabled '
            'aria-label="Previous clubs">&#8249;</button>'
            f'<span class="fxnav-pos">1 of {page_count}</span>'
            '<button class="fxnav-btn" data-dir="1" '
            'aria-label="Next clubs">&#8250;</button></div>'
        )
    controls = (
        '<div class="fxcontrols">'
        '<div class="fxgames">'
        '<span class="fxgames-label" id="fxgames-label">Games</span>'
        '<button type="button" class="fxnav-btn fxgames-btn" data-dir="-1" '
        'aria-label="Fewer games">&#8249;</button>'
        f'<span class="fxgames-n" role="status" aria-live="polite" '
        f'aria-labelledby="fxgames-label">{FIXTURE_GAMES_DEFAULT}</span>'
        '<button type="button" class="fxnav-btn fxgames-btn" data-dir="1" '
        'aria-label="More games">&#8250;</button>'
        "</div>"
        '<button type="button" class="chip fx-target" aria-pressed="false" '
        f'title="Only fixtures rated {TARGET_RATING:g} or above stay lit up">'
        "Target fixtures</button>"
        "</div>"
    )
    # Shut under the fixture-run band, which is its summary: the twenty-club
    # grid opens only when the band's best and worst three are not enough.
    return (
        '<details class="card collapsible fxcard"><summary class="card-head">'
        f'<h2>All {len(rows)} clubs{components.info_btn()}</h2>'
        '<span class="sub" hidden>Out of ten, higher is better. '
        'CAPITALS are home. A dot means the market priced it.</span></summary>'
        f'<div class="card-body">{controls}{nav}'
        f'<table data-sortable data-paged class="fxtable" '
        f'data-games="{FIXTURE_GAMES_DEFAULT}" data-target="{TARGET_RATING}">'
        '<thead><tr><th scope="col" class="sortable">Club</th>'
        '<th scope="col" class="num sortable" title="How many of your 15 '
        'play for this club">Owned</th>'
        '<th scope="col" class="num sortable" title="Mean rating over the '
        'games selected - higher is better">Rating</th>'
        f"{heads}</tr></thead><tbody>"
        f"{''.join(r[2] for r in rows)}</tbody></table></div></details>"
    )


def fixture_run_summary(reports, ctx, proj, market, next_gw, weeks=6, n=3, badges=None,
                        lenses=()):
    """The best and worst fixture runs in the whole league, not just yours.

    Two rankings, not one, because they answer different questions. Our own
    model bakes each club's attacking and defensive quality into the rating
    above - which means a genuinely weak side always reads as having a bad
    run, even against the division's softest opponents, because the model
    correctly expects them to struggle regardless of who they're facing.
    FPL's own 1-5 difficulty is scored from the opponent alone, so it can
    and does disagree. Showing only the model's answer would quietly bake
    in "bad teams have bad fixtures" as if it were a fact about the
    schedule rather than a fact about the team.

    Drawn as the page's night band: the three kindest runs as glass tiles
    with the club crest breaking out of the corner, the three hardest as a
    row beneath, and the rankings behind a switch.

    `lenses` adds position questions on the same 0-10 scale, as
    (key, label, [(team id, short name, mean rating)], note) - the clean
    sheet, goals and DefCon runs the Scout tab used to rank on its own."""
    badges = badges or {}
    owned = {}
    for r in reports:
        owned[r.element["team"]] = owned.get(r.element["team"], 0) + 1

    model_rows = []
    for tid, t in ctx.teams.items():
        cells = _rows_for(t["short_name"], proj, market, next_gw, weeks)
        if cells:
            avg = sum(c["score"] for c in cells) / len(cells)
            model_rows.append((tid, t["short_name"], avg))

    fdr_rows = []
    for tid, t in ctx.teams.items():
        score = ctx.fixture_score(tid, weeks)
        if score is not None:
            fdr_rows.append((tid, t["short_name"], score))

    if not model_rows and not fdr_rows:
        return ""

    def tile(tid, val, fmt, big):
        crest = badges.get(tid)
        name = ctx.teams[tid]["name"]
        count = owned.get(tid, 0)
        own = f" &middot; you own {count}" if count else ""
        img = f'<img src="{crest}" alt="">' if crest else ""
        if big:
            return (f'<li class="glass crest-tile">{img}<b class="big tnum">{fmt(val)}</b>'
                    f'<span>{e(name)}{own}</span></li>')
        return (f'<li class="glass crest-row">{img}<span>{e(name)}{own}</span>'
                f'<b class="tnum">{fmt(val)}</b></li>')

    def block(key, rows, note, kindest_first, fmt, first):
        if not rows:
            return ""
        ranked = sorted(rows, key=lambda x: x[2], reverse=kindest_first)
        best, worst = ranked[:n], ranked[-n:][::-1]
        return (
            f'<div class="fro-panel" data-fro="{key}"{"" if first else " hidden"}>'
            f'<p class="fronote">{e(note)}</p>'
            '<ul class="crest-tiles">'
            + "".join(tile(t, v, fmt, True) for t, _c, v in best)
            + '</ul><div class="crest-worst"><span class="lab">Worst</span><ul>'
            + "".join(tile(t, v, fmt, False) for t, _c, v in worst)
            + "</ul></div></div>"
        )

    def one_dp(v):
        return f"{v:.1f}"

    groups = [g for g in (
        ("model", "Expected output", model_rows, "Out of 10 · higher is better", True, one_dp),
        *((key, label, rows, note, True, one_dp) for key, label, rows, note in lenses),
        ("fdr", "FPL difficulty", fdr_rows, "FPL 1–5 · lower is easier", False, one_dp),
    ) if g[2]]
    tabs = "".join(
        f'<button type="button" role="tab" aria-selected="{"true" if i == 0 else "false"}" '
        f'data-fro="{key}">{e(label)}</button>'
        for i, (key, label, *_rest) in enumerate(groups))
    parts = "".join(block(key, rows, note, kind, fmt, i == 0)
                    for i, (key, _label, rows, note, kind, fmt) in enumerate(groups))
    return (
        '<section class="night-band fro-band" aria-labelledby="fro-title">'
        '<div class="glow" aria-hidden="true"><i></i><i></i><i></i></div>'
        '<div class="fro-head"><div><span class="lab">Next '
        f'{weeks} gameweeks, every club</span>'
        '<h2 class="disp" id="fro-title">Best fixture runs</h2></div>'
        f'<div class="frotabs" role="tablist" aria-label="Fixture rating">{tabs}</div></div>'
        f'{parts}</section>'
    )
