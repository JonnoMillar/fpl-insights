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

# Five light steps. Deliberately pale: the number carries the value, the fill
# only has to make a pattern visible down a column.
# Five solid bands rather than a wash. Distinct blocks make a run of good or
# bad fixtures obvious at a glance down a column, and the rating is printed in
# every cell so the colour is never the only thing carrying the value. Red
# through neutral to green is diverging with a genuine middle, which is what
# "difficulty" is.
# Rose through a warm neutral to teal. Deliberately not the red-amber-green
# traffic light: those three are so overused they stop being read, and the
# warm neutral in the middle sits far better against the purple the rest of
# the page is built from. The rating is printed in every cell, so the colour
# only has to make a run of good or bad fixtures visible down a column.
SCALE = [
    (2.0, "#a4133c", "#ffffff"),
    (4.0, "#f4845f", "#40190e"),
    (6.0, "#eae7ec", "#37003c"),
    (8.0, "#7ac9a0", "#0d3b26"),
    (10.1, "#17876a", "#ffffff"),
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


def rating_pill(opp, home, score):
    """A fixture chip using the same rating and ramp as the ticker, so a
    fixture looks the same wherever it appears."""
    cls, style = _cell_style(score)
    label = opp.upper() if home else opp.lower()
    return (
        '<span class="rpill {cls}" style="{style}" '
        'title="{opp} {venue} - rating {score:.1f} of 10">'
        "{label}<b>{score:.1f}</b></span>".format(
            cls=cls, style=style, opp=e(opp),
            venue="at home" if home else "away",
            score=score, label=e(label))
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
                '<span class="fxc-score">{score:.1f}</span></td>'.format(
                    cls=cls, style=style, gw=c["gw"],
                    venue="home" if c["home"] else "away", opp=e(c["opp"]),
                    score=c["score"], xg=c["xg"], cs=c["cs"], src=c["source"],
                    label=e(label), mark=mark,
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
            '<span class="fxavg {acls}" style="{astyle}">{avg:.1f}</span></td>'
            '{chips}</tr>'.format(
                club=e(club), own_n=own_n, own=own_cell, acls=acls, astyle=astyle,
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
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Fixture outlook{components.info_btn()}</h2>'
        '<span class="sub" hidden>Every club in the league, rated out of ten '
        "for how good the fixture is to own a player for - "
        "<b>higher is better</b>, the opposite way round to FPL's 1-5 "
        "difficulty. Expected goals and clean-sheet odds combined, weighted "
        "toward attack. A dot means the market priced it. Games sets how "
        "many of the next fixtures the Rating column averages; Target "
        f"fixtures dims everything below {TARGET_RATING:g} so the genuinely "
        f"good ones stand out. {FIXTURE_PAGE_SIZE} clubs at a time - cycle "
        "through with the arrows, or sort a column to re-rank all twenty - "
        "click Owned to bring your own squad's clubs to the top.</span>"
        f'{controls}</div>'
        f'{nav}'
        f'<table data-sortable data-paged class="fxtable" '
        f'data-games="{FIXTURE_GAMES_DEFAULT}" data-target="{TARGET_RATING}">'
        '<thead><tr><th scope="col" class="sortable">Club</th>'
        '<th scope="col" class="num sortable" title="How many of your 15 '
        'play for this club">Owned</th>'
        '<th scope="col" class="num sortable" title="Mean rating over the '
        'games selected - higher is better">Rating</th>'
        f"{heads}</tr></thead><tbody>"
        f"{''.join(r[2] for r in rows)}</tbody></table></section>"
    )


def fixture_run_summary(reports, ctx, proj, market, next_gw, weeks=6, n=3):
    """The best and worst fixture runs in the whole league, not just yours.

    Two rankings, not one, because they answer different questions. Our own
    model bakes each club's attacking and defensive quality into the rating
    above - which means a genuinely weak side always reads as having a bad
    run, even against the division's softest opponents, because the model
    correctly expects them to struggle regardless of who they're facing.
    FPL's own 1-5 difficulty is scored from the opponent alone, so it can
    and does disagree. Showing only the model's answer would quietly bake
    in "bad teams have bad fixtures" as if it were a fact about the
    schedule rather than a fact about the team."""
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

    def rowline(tid, club, val, tone, fmt):
        count = owned.get(tid, 0)
        mine = ""
        if count:
            dots = '<span class="fro-dot"></span>' * count
            mine = (f'<span class="fro-mine"><span class="fro-dots">{dots}'
                    f'</span>{count} owned</span>')
        return (f'<li class="fro-row fro-{tone}"><span class="fro-club">'
                f"{e(club)}</span><span class=\"fro-val\">{fmt(val)}</span>"
                f"{mine}</li>")

    def block(rows, title, note, kindest_first, fmt):
        if not rows:
            return ""
        ranked = sorted(rows, key=lambda x: x[2], reverse=kindest_first)
        best, worst = ranked[:n], ranked[-n:][::-1]
        # Best and worst used to differ only by a near-white background
        # tint, which read as barely different at a glance, especially
        # side by side. A labelled header plus a solid colour edge on each
        # row make the two columns unmistakable without needing to read
        # every number first.
        return (
            f'<div class="frogroup"><h4>{e(title)}</h4>'
            f'<p class="fronote">{e(note)}</p><div class="frocols">'
            '<div class="frocol fro-col-good"><h5>Best</h5><ul class="frolist">'
            + "".join(rowline(t, c, v, "good", fmt) for t, c, v in best)
            + '</ul></div><div class="frocol fro-col-bad"><h5>Worst</h5>'
            '<ul class="frolist">'
            + "".join(rowline(t, c, v, "bad", fmt) for t, c, v in worst)
            + "</ul></div></div></div>"
        )

    parts = (
        block(model_rows, "Expected output",
              "Attack and defence combined, out of ten, in absolute terms - "
              "a genuinely strong side reads as a good run here even against "
              "tough opponents. Higher is better.",
              True, lambda v: f"{v:.1f}")
        + block(fdr_rows, "FPL's own difficulty",
                "FPL's 1-5 rating, unadjusted for either side's own quality "
                "- lower is easier.", False, lambda v: f"{v:.1f}")
    )
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Best and worst fixture runs{components.info_btn()}</h2>'
        f'<span class="sub" hidden>Next {weeks} gameweeks, every club in the '
        'league - not just yours. "Owned" counts how many of your 15 play '
        'for that club.</span></div>'
        f'<div class="card-body frowrap">{parts}</div></section>'
    )


def odds_insights(fixtures, reports, ctx, proj, next_gw):
    """What the market means for this squad.

    A grid of prices is the raw material, not the answer - reading it and
    working out what it implies for your eleven is the job, so this does that
    job instead of printing the prices. Every line names the players affected
    and the number behind it."""
    if not fixtures:
        return ""
    # Pinnacle price several rounds at once - three were live the day this
    # guard was added - and this used to let each club's *last* listed
    # fixture win, which is the furthest one away. That silently reported
    # next-next-gameweek odds under this gameweek's heading: Chelsea's line
    # came from a fixture nine days out.
    #
    # Taking the soonest instead is nearly right but not right: while a round
    # is still finishing, a club's soonest match is last week's, so a heading
    # naming this gameweek would carry a row from the previous one. Pin each
    # club to the fixture FPL itself lists for `next_gw` and accept the
    # priced match only when the opponent agrees.
    want = {}
    for fx in ctx.fixtures:
        if fx.get("event") != next_gw:
            continue
        h, a = ctx.team_name(fx["team_h"]), ctx.team_name(fx["team_a"])
        want[h] = (a, True)
        want[a] = (h, False)

    by_club = {}
    for fx in sorted(fixtures, key=lambda f: f.get("kickoff") or ""):
        for club, opp, home in ((fx["home"], fx["away"], True),
                                (fx["away"], fx["home"], False)):
            if club in by_club:
                continue
            expect = want.get(club)
            if expect and (expect[0] != opp or expect[1] != home):
                continue  # a different round's fixture for this club
            by_club[club] = (fx, home)

    def side(fx, home, key):
        return fx[("home_" if home else "away_") + key]

    rows = []
    for r in reports:
        entry = by_club.get(r.team)
        if not entry:
            continue
        fx, home = entry
        win = (fx.get("win") or {}).get("home" if home else "away", 0)
        rows.append({
            "r": r, "fx": fx, "home": home,
            "xg": side(fx, home, "xg"), "cs": side(fx, home, "cs"),
            "opp": fx["away"] if home else fx["home"],
            "win": win, "total": fx["total"],
        })
    if not rows:
        return ""

    items = []

    attackers = [x for x in rows if x["r"].pos in ("MID", "FWD")]
    if attackers:
        b = max(attackers, key=lambda x: x["xg"])
        # Named after the fixture, not the one player who happened to have
        # the top individual xG - Busiest fixture below names everyone
        # involved, and this read as contradicting it whenever two of your
        # attackers shared the same match: Semenyo alone here, Semenyo and
        # Haaland both there, for the identical Man City v Bournemouth game.
        mates = sorted({x["r"].name for x in attackers if x["fx"] is b["fx"]})
        items.append({
            "tone": "good", "icon": "spark", "label": "Best attacking fixture",
            "value": "{:.2f}".format(b["xg"]), "unit": "goals priced",
            "who": ", ".join(mates[:3]),
            "detail": "{} v {} &middot; {:.0f}% to win".format(
                b["r"].team, b["opp"], b["win"]),
        })

    backs = [x for x in rows if x["r"].pos in ("GKP", "DEF")]
    if backs:
        b = max(backs, key=lambda x: x["cs"])
        mates = [x["r"].name for x in backs if x["r"].team == b["r"].team]
        items.append({
            "tone": "good", "icon": "shield", "label": "Likeliest clean sheet",
            "value": "{:.0f}%".format(b["cs"]), "unit": (
                "quoted" if b["fx"].get("cs_source") == "quoted" else "derived"),
            "who": ", ".join(sorted(mates)[:3]),
            "detail": "{} v {}".format(b["r"].team, b["opp"]),
        })
        w = min(backs, key=lambda x: x["cs"])
        if w["cs"] < 20:
            items.append({
                "tone": "bad", "icon": "shield", "label": "Least likely clean sheet",
                "value": "{:.0f}%".format(w["cs"]), "unit": "clean sheet",
                "who": w["r"].name,
                "detail": "{} v {}".format(w["r"].team, w["opp"]),
            })

    busiest = max(rows, key=lambda x: x["total"])
    involved = sorted({x["r"].name for x in rows if x["fx"] is busiest["fx"]})
    items.append({
        "tone": "info", "icon": "ball", "label": "Busiest fixture",
        "value": "{:.2f}".format(busiest["total"]), "unit": "goals expected",
        "who": ", ".join(involved[:3]),
        "detail": "{} v {}".format(busiest["fx"]["home"], busiest["fx"]["away"]),
    })

    gaps = []
    for x in rows:
        model = proj.get((x["r"].team, next_gw))
        if model:
            gaps.append((abs(x["cs"] - float(model.get("cs") or 0)), x, model))
    if gaps:
        mag, x, model = max(gaps, key=lambda g: g[0])
        if mag >= 6:
            items.append({
                "tone": "info", "icon": "key", "label": "Market v model",
                "value": "{:+.0f}".format(x["cs"] - float(model.get("cs") or 0)),
                "unit": "points apart on CS",
                "who": x["r"].team,
                "detail": "market {:.0f}% &middot; model {:.0f}%".format(
                    x["cs"], float(model.get("cs") or 0)),
            })

    if not items:
        return ""
    cards = "".join(
        '<li class="oi oi-{tone}">'
        '<svg viewBox="0 0 24 24" class="oi-icon" aria-hidden="true">{icon}</svg>'
        '<p class="oi-label">{label}</p>'
        '<p class="oi-value">{value}<small>{unit}</small></p>'
        '<p class="oi-who">{who}</p>'
        '<p class="oi-detail">{detail}</p></li>'.format(
            tone=it["tone"], icon=ICON_PATHS.get(it["icon"], ""),
            label=e(it["label"]), value=e(it["value"]), unit=e(it["unit"]),
            who=e(it["who"]), detail=it["detail"])
        for it in items
    )
    return (
        '<section class="card"><div class="card-head">'
        f"<h2>What the odds mean for gameweek {next_gw}{components.info_btn()}</h2>"
        '<span class="sub" hidden>Pinnacle, margin removed, applied to your squad. '
        "Each club's next match only.</span></div>"
        f'<div class="card-body"><ul class="oilist">{cards}</ul></div></section>'
    )


ICON_PATHS = {
    "spark": '<path d="M4 17l5-6 4 3 6-8" fill="none" stroke="currentColor" '
             'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
    "shield": '<path d="M12 3 20 6v6c0 4-3.4 7.4-8 9-4.6-1.6-8-5-8-9V6Z" fill="none" '
              'stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    "ball": '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" '
            'stroke-width="1.7"/><path d="M12 7.2l3.6 2.6-1.4 4.2H9.8L8.4 9.8Z" '
            'fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linejoin="round"/>',
    "run": '<circle cx="14" cy="5" r="2" fill="currentColor"/>'
           '<path d="M13 9l-4 3 2 4-3 4M13 9l4 2 2 4" fill="none" '
           'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
           'stroke-linejoin="round"/>',
    "key": '<path d="M4 12h9M13 8l4 4-4 4" fill="none" stroke="currentColor" '
           'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
           '<circle cx="19" cy="12" r="2" fill="currentColor"/>',
}


def _bar(parts):
    """A single stacked probability bar, used for win / draw / loss."""
    segs = "".join(
        '<span class="mb-seg" style="width:{:.1f}%;background:{}" title="{} {:.0f}%">'
        "</span>".format(pct, colour, e(label), pct)
        for label, pct, colour in parts if pct > 0.5
    )
    return '<span class="mbar">{}</span>'.format(segs)


def market_card(market, ctx, reports, fixtures=None):
    """The coming round, as the market sees it.

    One card per fixture your players are involved in, rather than a table:
    each fixture is a small story - who is favoured, how many goals, who is
    likely to keep it out - and a row of numbers tells it badly."""
    if not fixtures:
        return ""
    mine = {r.team for r in reports}
    cards = []
    for fx in fixtures:
        if fx["home"] not in mine and fx["away"] not in mine:
            continue
        win = fx.get("win") or {}
        bar = _bar([
            ("Home win", win.get("home", 0), "#953bff"),
            ("Draw", win.get("draw", 0), "#c3b2c4"),
            ("Away win", win.get("away", 0), "#00b3d6"),
        ]) if win else ""
        btts = (
            '<div class="mstat"><dt>Both score</dt><dd>{:.0f}%</dd></div>'.format(fx["btts"])
            if fx.get("btts") else ""
        )
        quoted = fx.get("cs_source") == "quoted"
        cards.append(
            '<li class="mcard">'
            '<div class="mteams"><span class="mt {hcls}">{home}</span>'
            '<span class="mvs">v</span>'
            '<span class="mt {acls}">{away}</span>'
            '<span class="mtotal">{total:.2f}<small>goals</small></span></div>'
            "{bar}"
            '<div class="mkeys"><span>{hw:.0f}%</span><span>{dw:.0f}%</span>'
            '<span>{aw:.0f}%</span></div>'
            '<dl class="mstats">'
            '<div class="mstat"><dt>{home} xG</dt><dd>{hxg:.2f}</dd></div>'
            '<div class="mstat"><dt>{away} xG</dt><dd>{axg:.2f}</dd></div>'
            '<div class="mstat"><dt>{home} CS</dt><dd>{hcs:.0f}%</dd></div>'
            '<div class="mstat"><dt>{away} CS</dt><dd>{acs:.0f}%</dd></div>'
            "{btts}</dl>"
            '<p class="mfoot">{note}</p></li>'.format(
                home=e(fx["home"]), away=e(fx["away"]),
                hcls="mine" if fx["home"] in mine else "",
                acls="mine" if fx["away"] in mine else "",
                total=fx["total"], bar=bar,
                hw=win.get("home", 0), dw=win.get("draw", 0), aw=win.get("away", 0),
                hxg=fx["home_xg"], axg=fx["away_xg"],
                hcs=fx["home_cs"], acs=fx["away_cs"], btts=btts,
                note=("Clean sheets quoted directly by the market."
                      if quoted else
                      "Clean sheets derived from the goals line, not quoted."),
            )
        )
    if not cards:
        return ""
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>The coming round, priced{components.info_btn()}</h2>'
        '<span class="sub" hidden>Pinnacle, with the bookmaker margin removed. Only the '
        "fixtures your players are in.</span></div>"
        '<div class="card-body"><ul class="mlist">{}</ul></div></section>'.format(
            "".join(cards)
        )
    )
