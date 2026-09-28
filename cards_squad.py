"""Cards for the Squad tab: the pitch views, squad table, findings and player dialog."""

import json
import math
import re

import analysis
import components
import ffs
import pulse
import ticker
from analysis import f
from cards_common import TONE_COLOR, e, meter, pos_fixture_pill


# FPL's own five-step difficulty scale, background and text, straight from
# their stylesheet. Difficulty is ordinal and diverging - kind through neutral
# to brutal - so the grey midpoint is correct rather than a gap in the
# palette. Every pill also carries the opponent and the number, which is what
# actually makes it readable: steps 2 and 3 sit at 1.35:1 and 1.2:1 against
# white, so the fill alone was never carrying the meaning.
FDR = {
    1: ("#375523", "#ffffff"),
    2: ("#01fc7a", "#37003c"),
    3: ("#e7e7e7", "#37003c"),
    4: ("#ff1751", "#000000"),
    5: ("#80072d", "#ffffff"),
}


def fdr_pill(opp, home, diff):
    bg, fg = FDR.get(diff, ("#ebe5eb", "#37003c"))
    label = opp.upper() if home else opp.lower()
    venue = "home" if home else "away"
    return (
        f'<span class="fdr" style="background:{bg};color:{fg}" '
        f'title="{e(opp)} ({venue}), difficulty {diff} of 5">'
        f"{e(label)}<b>{diff}</b></span>"
    )


SPARK_ICON = (
    '<svg viewBox="0 0 24 24" class="pk-spark" aria-hidden="true">'
    '<path d="M4 17l5-6 4 3 6-8" fill="none" stroke="currentColor" '
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def gw_points(r, gw):
    """A player's points in one gameweek. Summed rather than found, because
    a double gameweek is two rows in the same history."""
    return sum(h["total_points"] for h in r.history if h.get("round") == gw)


def player_card(r, ctx, badges, shirts, captain_id, vice_id, played=True,
                gw=None):
    el = r.element
    # FPL put a club shirt on their pitch, so this does too; the badge is the
    # fallback when a shirt image cannot be had.
    shirt = shirts.get((el["team"], r.pos == "GKP"))
    uri = shirt or badges.get(el["team"])
    crest = (
        f'<img class="{"kit" if shirt else "crestimg"}" src="{uri}" alt="{e(r.team)}">'
        if uri
        else f'<span class="letters">{e(r.team)}</span>'
    )
    arm = ""
    if el["id"] == captain_id:
        arm = '<span class="arm" title="Captain">C</span>'
    elif el["id"] == vice_id:
        arm = '<span class="arm" title="Vice-captain" style="background:var(--p20)">V</span>'
    flag, news = r.availability
    title = f"{r.name} - {r.pos}, {r.team}, {r.price:.1f}m"
    if flag:
        title += f" - {flag}. {news}"
    pred = ctx.is_predicted(el)
    pip = ""
    if pred is True:
        pip = '<span class="pip pip-in" title="Predicted to start"></span>'
        title += " - predicted to start"
    elif pred is False:
        pip = '<span class="pip pip-out" title="Not in the predicted eleven"></span>'
        title += " - NOT in the predicted eleven"
    cls = "pl" if played else "pl out"
    # Season points beside season xGI, with no sense of how many matches
    # either came from, flattered anyone who had simply played more. Points
    # per game is the fair comparison and costs one more cell; the raw
    # totals stay, since per-game alone hides who has actually been
    # available. The two gameweek figures ride along as data attributes so
    # the selector can swap them in without re-rendering the pitch.
    ppg = f(el.get("points_per_game"))
    now = gw_points(r, gw) if gw else 0
    prev = gw_points(r, gw - 1) if gw and gw > 1 else 0
    return (
        f'<div class="{cls}" title="{e(title)}" data-player="{el["id"]}" '
        f'data-pts-season="{r.points}" data-pts-now="{now}" '
        f'data-pts-prev="{prev}" data-apps="{r.appearances}" '
        f'role="button" tabindex="0" aria-label="{e(title)}">{arm}{pip}'
        f'<div class="crest">{crest}</div>'
        f'<div class="nm">{e(r.name)}</div>'
        f'<div class="sc tnum"><div class="p" title="Points">{r.points}</div>'
        f'<div class="g" title="Points per game across {r.appearances} '
        f'appearances">{ppg:.1f}</div>'
        f'<div class="x" title="Season xGI">{r.xgi:.2f}</div></div></div>'
    )


def pitch(xi, bench, ctx, badges, shirts, captain_id, vice_id, gw=None):
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    rows = {1: [], 2: [], 3: [], 4: []}
    for r in xi:
        rows[order.get(r.pos, 4)].append(r)
    # The stat selector itself lives up in the view-tab row, so this only
    # supplies the wrapper its classes are toggled on.
    out = ['<div class="ovwrap emph-p">']
    out.append('<div class="pitch">' + components.PITCH_MARKS)
    for k in (1, 2, 3, 4):
        if not rows[k]:
            continue
        cards = "".join(
            player_card(r, ctx, badges, shirts, captain_id, vice_id,
                        r.minutes > 0, gw=gw)
            for r in rows[k]
        )
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    cards = "".join(
        player_card(r, ctx, badges, shirts, captain_id, vice_id, r.minutes > 0,
                    gw=gw)
        for r in bench
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{cards}</div></div>'
    )
    out.append("</div>")   # .ovwrap
    return "".join(out)


def pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj, market,
              next_gw, played=True):
    """One card for the 'Pick team' pitch: the same shirt card as the
    overview, plus the two things worth knowing at a glance before a
    deadline - the next fixture, and a read on recent form worth the one
    line it costs."""
    el = r.element
    shirt = shirts.get((el["team"], r.pos == "GKP"))
    uri = shirt or badges.get(el["team"])
    crest = (
        f'<img class="{"kit" if shirt else "crestimg"}" src="{uri}" alt="{e(r.team)}">'
        if uri
        else f'<span class="letters">{e(r.team)}</span>'
    )
    arm = ""
    if el["id"] == captain_id:
        arm = '<span class="arm" title="Captain">C</span>'
    elif el["id"] == vice_id:
        arm = '<span class="arm" title="Vice-captain" style="background:var(--p20)">V</span>'
    flag, news = r.availability
    title = f"{r.name} - {r.pos}, {r.team}, {r.price:.1f}m"
    if flag:
        title += f" - {flag}. {news}"

    fx_rows = ticker._rows_for(r.team, proj, market, next_gw, 1)
    fx_html = (
        pos_fixture_pill(r.pos, fx_rows[0]["opp"], fx_rows[0]["home"],
                         fx_rows[0]["cs"], fx_rows[0]["xg"])
        if fx_rows else ""
    )

    form = r.recent_form()
    snippet = ""
    if form:
        icon = SPARK_ICON if form["hot"] else ""
        hot_cls = " hot" if form["hot"] else ""
        snippet = f'<div class="pk-form{hot_cls}">{icon}{e(form["text"])}</div>'

    cls = "pl pk" if played else "pl pk out"
    return (
        f'<div class="{cls}" title="{e(title)}" data-player="{el["id"]}" '
        f'role="button" tabindex="0" aria-label="{e(title)}">{arm}'
        f'<div class="crest">{crest}</div>'
        f'<div class="nm">{e(r.name)}</div>'
        f'<div class="pk-fx">{fx_html}</div>'
        f"{snippet}</div>"
    )


def pick_team_pitch(xi, bench, ctx, badges, shirts, captain_id, vice_id,
                    proj, market, next_gw, eps=None):
    """The pick-team pitch, and the expected-points column it folds out to.

    Both live in one `.pkstage` so the Predicted points toggle can move
    between them as a single layout change rather than swapping one block
    of markup for another - the eleven cards shrink into a column on the
    left and the bars extend across the space that opens on the right,
    which only reads as the same eleven if they are the same elements
    throughout.

    Keeper first, forwards last, top to bottom. That is already the order
    the pitch draws in, so the folded-out column inherits it for free, and
    `ep_column` is handed the ids in exactly that order so every bar sits
    level with its own card."""
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    rows = {1: [], 2: [], 3: [], 4: []}
    for r in xi:
        rows[order.get(r.pos, 4)].append(r)
    # The left column carries a header of its own only so the two columns
    # start at the same height - without it the eleven began level with the
    # side panel's title and every bar sat one card low.
    out = ['<div class="pkstage"><div class="pkboard">'
           '<div class="pkboard-head">Your eleven</div>'
           '<div class="pitch">' + components.PITCH_MARKS]
    pitch_order = []
    for k in (1, 2, 3, 4):
        if not rows[k]:
            continue
        cards = "".join(
            pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj,
                     market, next_gw, r.minutes > 0)
            for r in rows[k]
        )
        pitch_order.extend(r.element["id"] for r in rows[k])
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    cards = "".join(
        pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj, market,
                 next_gw, r.minutes > 0)
        for r in bench
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{cards}</div></div></div>'
    )
    out.append(components.ep_column(eps or [], pitch_order))
    out.append("</div>")
    return "".join(out)


SQUAD_HEAD = [
    ("Pos", "", False), ("Player", "", True), ("Club", "", True),
    ("Price", "num", True), ("Own", "num", True), ("Min", "num", True),
    ("Pts", "num", True), ("xG", "num", True), ("xA", "num", True),
    ("xGI", "num", True), ("xGI/90", "num", True), ("DC/90", "num", True),
    # The one forward-looking number in a table that was otherwise entirely
    # season-to-date. Everything else on this page decides on a projection;
    # the table where you would actually compare a projection against the
    # underlying numbers behind it did not carry one.
    ("xP", "num", True),
    ("Starting", "", True), ("Next 3", "", False),
]


def squad_table(reports, ctx, captain_id, vice_id, proj=None, market=None,
                next_gw=None, eps_by_id=None):
    head = "".join(
        f'<th scope="col" class="{cls}{" sortable" if sortable else ""}">{e(label)}</th>'
        for label, cls, sortable in SQUAD_HEAD
    )
    maxx = max([r.xgi90 for r in reports] + [0.01])
    eps_by_id = eps_by_id or {}
    baseline_xg, club_mean_cs = ticker._club_norms(ctx, proj) if proj else ({}, {})
    body = []
    for r in reports:
        el = r.element
        flag, news = r.availability
        fx = "".join(
            ticker.rating_pill(row["opp"], row["home"], row["score"])
            for row in ticker._rows_for(r.team, proj, market, next_gw, 3,
                                        baseline_xg.get(r.team), club_mean_cs.get(r.team))
        ) or "".join(
            fdr_pill(ctx.team_name(o), h, d)
            for o, h, d, _ev in ctx.next_fixtures(el["team"], 3)
        )
        suffix = " (C)" if el["id"] == captain_id else (" (V)" if el["id"] == vice_id else "")
        flag_html = f' <span class="flag" title="{e(news)}">{e(flag)}</span>' if flag else ""
        # Goalkeepers have no defensive-contribution threshold, and a rate
        # off a cameo is arithmetic, not evidence: three contributions in
        # sixteen minutes reads as 16.9 per 90 and would sort above every
        # regular starter. Below the floor the cell says so instead, and
        # carries no sort value - the minutes column is two across if you
        # want to know why.
        thin = r.minutes < analysis.DEFCON_MIN_MINUTES
        dc_cell = (
            f'<td class="num" data-v="{r.defcon90}">{r.defcon90:.1f}</td>'
            if not thin and r.pos != "GKP"
            else f'<td class="num" title="{r.minutes} minutes - too few for a '
                 f'per-90 rate">-</td>'
            if r.minutes and r.pos != "GKP"
            else '<td class="num">-</td>'
        )
        ep_row = eps_by_id.get(el["id"])
        xp_cell = (
            f'<td class="num" data-v="{ep_row["total"]}">'
            f'{ep_row["total"]:.1f}</td>'
            if ep_row else
            '<td class="num" data-v="-1" title="No fixture priced for him '
            'in this gameweek">-</td>'
        )
        pred = ctx.is_predicted(el)
        pred_txt = "yes" if pred is True else ("no" if pred is False else "unknown")
        sort_key = "" if pred_txt == "unknown" else pred_txt
        pred_cell = {
            "yes": '<span class="lu lu-in">Predicted XI</span>',
            "no": '<span class="lu lu-out">Not predicted</span>',
            "unknown": '<span class="lu lu-unk">-</span>',
        }[pred_txt]
        body.append(
            "<tr>"
            f'<td><span class="pos">{e(r.pos)}</span></td>'
            f'<td><button class="rowlink" data-player="{el["id"]}">'
            f"<b>{e(r.name)}</b></button>{suffix}{flag_html}</td>"
            f"<td>{e(r.team)}</td>"
            f'<td class="num" data-v="{r.price}">{r.price:.1f}</td>'
            f'<td class="num" data-v="{r.owned}">{r.owned:.0f}%</td>'
            f'<td class="num" data-v="{r.minutes}">{r.minutes}</td>'
            f'<td class="num" data-v="{r.points}"><b>{r.points}</b></td>'
            f'<td class="num" data-v="{r.xg}">{r.xg:.2f}</td>'
            f'<td class="num" data-v="{r.xa}">{r.xa:.2f}</td>'
            f'<td class="num" data-v="{r.xgi}">{r.xgi:.2f}</td>'
            f'<td class="num" data-v="{r.xgi90}">'
            f"{meter(r.xgi90, maxx, f'{r.xgi90:.2f} xGI per 90')} "
            f"{r.xgi90:.2f}</td>"
            f"{dc_cell}"
            f"{xp_cell}"
            f'<td data-v="{sort_key}">{pred_cell}</td>'
            f"<td>{fx}</td></tr>"
        )
    return (
        '<div class="scroll"><table data-sortable><thead><tr>'
        f"{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def split_donut(parts, label, center, sub):
    """A part-of-whole ring with more than one part.

    `parts` is [(count, css_var)] in reading order. The single-part `donut`
    above cannot say "eleven named, one unknown, one left out" - it would
    have to fold the last two together, and those two are not the same news.

    Sized off a 120-unit box rather than 90: at 90 the ring left about 50
    units of clear space for two lines of type, which is what made the old
    one feel cramped. Here the caption lives outside the ring and only the
    share sits inside it."""
    total = sum(n for n, _ in parts)
    r, gap = 46, 2.0
    circ = 2 * math.pi * r
    segs, offset = [], 0.0
    for n, tone in parts:
        if not n or not total:
            continue
        length = circ * n / total
        # A hairline gap between segments so two adjacent colours read as
        # two facts rather than one gradient. Never wider than the segment.
        draw = max(1.0, length - min(gap, length / 2))
        segs.append(
            f'<circle class="dseg" cx="60" cy="60" r="{r}" stroke="var({tone})" '
            f'stroke-dasharray="{draw:.2f} {circ - draw:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 60 60)"/>'
        )
        offset += length
    return (
        f'<svg class="lcring" viewBox="0 0 120 120" role="img" '
        f'aria-label="{e(label)}">'
        f'<circle class="dtrack" cx="60" cy="60" r="{r}"/>'
        + "".join(segs)
        # Baseline, not centre: y is where the glyphs sit, so a single line
        # centres at 60 plus roughly a third of its size.
        + f'<text class="lcring-n" x="60" y="{68 if not sub else 57}" '
        f'text-anchor="middle">{e(center)}</text>'
        + (f'<text class="lcring-s" x="60" y="74" text-anchor="middle">{e(sub)}</text>'
           if sub else "")
        + "</svg>"
    )


def _next_three(r, ctx, proj, market, next_gw, baseline_xg=None, club_mean_cs=None):
    """Three fixture pills for one player, market-rated where the odds
    priced the game and on FPL's own difficulty rating where they did not."""
    baseline_xg = baseline_xg or {}
    club_mean_cs = club_mean_cs or {}
    pills = "".join(
        ticker.rating_pill(row["opp"], row["home"], row["score"])
        for row in ticker._rows_for(r.team, proj, market, next_gw, 3,
                                    baseline_xg.get(r.team), club_mean_cs.get(r.team))
    )
    return pills or "".join(
        fdr_pill(ctx.team_name(o), h, d)
        for o, h, d, _ev in ctx.next_fixtures(r.element["team"], 3)
    )


def lineup_card(reports, ctx, proj, market, next_gw, xi_ids=None):
    """Who is predicted to start, as a donut and then an exception list.

    Fifteen rows saying "predicted to start" is fifteen rows of nothing:
    the information is entirely in the handful who are not, and in how many
    that is. So the count leads with a donut, and only the men who need a
    decision are named - each with the three fixtures that decide whether
    he is worth keeping through it.

    Three different subsets of the same squad answer three different
    questions - a gap in the bench barely matters, the same gap in the
    starting XI is the whole ballgame - so the donut switches between
    full squad, XI and bench rather than only ever answering the first one.

    Unknown is kept separate from no. Fantasy Football Scout not having
    published a side yet is a gap in the feed; being left out of a
    published side is a fact about the player."""
    if not ctx.lineups_known():
        return ""
    xi_ids = xi_ids or set()
    baseline_xg, club_mean_cs = ticker._club_norms(ctx, proj) if proj else ({}, {})
    views = [
        ("squad", "Full squad", reports),
        ("xi", "Starting XI", [r for r in reports if r.element["id"] in xi_ids]),
        ("bench", "Bench", [r for r in reports if r.element["id"] not in xi_ids]),
    ]

    def block(rows, cls, label, fixtures=True):
        if not rows:
            return ""
        items = "".join(
            f'<li><span class="lc-name">{e(r.name)}</span>'
            f'<span class="lc-club">{e(r.team)}</span>'
            + (f'<span class="lc-fx">'
               f'{_next_three(r, ctx, proj, market, next_gw, baseline_xg, club_mean_cs)}'
               f"</span>" if fixtures else "")
            + "</li>"
            for r in rows
        )
        return (f'<div class="lc-block {cls}"><h4>{WARN_SVG}{e(label)}</h4>'
                f"<ul>{items}</ul></div>")

    panels = []
    for i, (key, label, rows) in enumerate(views):
        out, unknown = [], []
        for r in rows:
            pred = ctx.is_predicted(r.element)
            if pred is False:
                out.append(r)
            elif pred is None:
                unknown.append(r)
        total = len(rows)
        starting = total - len(out) - len(unknown)
        pct = (starting / total * 100) if total else 0.0
        # A clean sweep gets the same bright accent green as the set-piece
        # card's "1" badge - the colour this page already uses to say "this
        # one's the best of its kind" - rather than the duller ink tone that
        # merely clearing 90% gets.
        tone = ("var(--accent)" if starting == total and total else
                "var(--good-ink)" if pct >= 90 else
                "var(--attention-ink)" if pct >= 60 else "var(--bad-ink)")
        if not total:
            body = '<p class="lc-clear">Nobody in this group.</p>'
        elif not out and not unknown:
            body = ('<p class="lc-clear">Every one of them is named in a '
                    'published side. Nothing to decide here.</p>')
        else:
            # No fixtures for the "out" block: he is not playing this week
            # regardless of who it is against, so a fixture rating there
            # answers a question nobody is asking. "Unknown" still gets
            # them, because there the question is live - a side has not
            # been named yet.
            body = (block(out, "lc-out", "Not predicted to start:", fixtures=False)
                    + block(unknown, "lc-unk", "No side published yet"))
        # The ring carries all three states in one shape, in the order they
        # are worth reading: named, then unknown, then left out. The count
        # is printed beside it rather than inside, so the angle is never the
        # only way to read the number and the ring has room to breathe.
        aria = (f"{starting} of {total} predicted to start"
                + (f", {len(unknown)} with no side published" if unknown else "")
                + (f", {len(out)} left out" if out else ""))
        ring = split_donut(
            [(starting, "--lc-tone"), (len(unknown), "--attention"),
             (len(out), "--bad")],
            aria, f"{pct:.0f}%", "",
        ) if total else ""
        legend = "".join(
            f'<span class="lckey"><i class="lck lck-{cls}"></i>{n} {word}</span>'
            for cls, n, word in (("unk", len(unknown), "no side yet"),
                                 ("off", len(out), "left out"))
            if n
        )
        panels.append(
            f'<div class="lcpanel" data-lcview="{key}" data-lclabel="{e(label)}"'
            f'{" hidden" if i else ""}>'
            f'<div class="lcstat" style="--lc-tone:{tone}">'
            f"{ring}"
            f'<div class="lcread">'
            f'<p class="lcfig"><b>{starting}</b><span>of {total}</span></p>'
            f'<p class="lccap">predicted to start</p>'
            + (f'<p class="lcleg">{legend}</p>' if legend else "")
            + f"</div></div>{body}</div>"
        )

    # Three named tabs rather than a label between two arrows: there are
    # only ever three, and an arrow makes you click to find out what is
    # behind it.
    nav = (
        '<div class="lcnav tabbar" role="tablist" aria-label="Squad subset">'
        + "".join(
            f'<button class="lcbtn" type="button" role="tab" '
            f'data-lcview="{key}" aria-selected="{"true" if not i else "false"}">'
            f"{e(label)}</button>"
            for i, (key, label, _rows) in enumerate(views)
        )
        + "</div>"
    )

    return (
        f'<div class="find gapcard lccard"><h3>Predicted line-ups'
        f'{components.info_btn()}</h3>'
        f'<p class="note" hidden>Fantasy Football Scout\'s predicted elevens. '
        f'They are re-tuned after each press conference, so they sharpen '
        f'closer to the deadline.</p>'
        f'{nav}{"".join(panels)}</div>'
    )


def attacking_returns_card(reports):
    """Goals and assists as one number - a "return" in the sense every FPL
    manager already means it, rather than broken back into the two halves
    that made it. A defender's return is marked: the same haul means more
    from the back, and the badge is the reward for scoring rarer points."""
    rows = [
        (r.name, r.team, r.pos, r.goals + r.assists, r.goals, r.assists)
        for r in reports if (r.goals + r.assists) > 0
    ]
    if not rows:
        return ""
    rows.sort(key=lambda x: -x[3])
    items = "".join(
        '<li class="arr{defcls}"><span class="arr-name">{name}{badge}</span>'
        '<span class="arr-club">{club}</span>'
        '<span class="arr-detail">{g:g}G {a:g}A</span>'
        '<span class="arr-total num">{total:g}</span></li>'.format(
            defcls=" arr-isdef" if pos == "DEF" else "",
            name=e(name), club=e(club),
            badge='<span class="arr-def" title="Defender">DEF</span>' if pos == "DEF" else "",
            g=g, a=a, total=total,
        )
        for name, club, pos, total, g, a in rows
    )
    return (
        f'<div class="find gapcard"><h3>Attacking returns{components.info_btn()}</h3>'
        '<p class="note" hidden>Goals and assists combined, one number per player. '
        "A defender's return is marked - the same haul is worth more from the "
        "back than from the front.</p>"
        f'<ul class="arrlist">{items}</ul></div>'
    )


def big_chances_card(reports):
    """Big chances created, with the wider chances-created figure alongside.

    A big chance is a clear opening - a subset of every chance created - so
    the two numbers belong on one row, not two cards that happen to share a
    subject. Ranked on the big-chance figure, since that is the rarer, more
    valuable half."""
    rows = []
    for r in reports:
        ps = r.element.get("_pulse") or {}
        bcc = ps.get("big_chance_created")
        if not bcc:
            continue
        rows.append((r.name, r.team, bcc, ps.get("total_att_assist") or 0))
    if not rows:
        return ""
    rows.sort(key=lambda x: (-x[2], -x[3]))
    # A big chance is a subset of every chance created, so "1 of 0" cannot be
    # true - it means the chances-created half of the Opta feed came back
    # short for that player (the two halves are separate paginated requests,
    # and one can fail on its own). Say nothing rather than say something
    # impossible.
    items = "".join(
        '<li class="arr{nod}"><span class="arr-name">{name}</span>'
        '<span class="arr-club">{club}</span>'
        '{detail}'
        '<span class="arr-total num">{bcc:g}</span></li>'.format(
            nod="" if tac >= bcc else " arr-nodetail",
            detail=('<span class="arr-detail">of {:g} created</span>'.format(tac)
                    if tac >= bcc else ""),
            name=e(name), club=e(club), bcc=bcc)
        for name, club, bcc, tac in rows
    )
    # "2, 6" was the least readable thing on the page: a slash in the heading,
    # a comma in the value, and nothing anywhere saying which number was
    # which. One headline figure with the wider one written out beside it in
    # words, the same shape as every other card in this column.
    return (
        f'<div class="find gapcard"><h3>Big chances created'
        f'{components.info_btn()}</h3>'
        '<p class="note" hidden>The big number is big chances created - a clear '
        "opening. Beside it is every chance created, of which a big chance is "
        "a subset: any pass leading to a shot.</p>"
        f'<ul class="arrlist">{items}</ul></div>'
    )


def fixture_swings_card(reports, ctx, proj, market, next_gw):
    """Clubs with a notably kind or hard run next, with the fixtures that
    make it one rather than just the average that summarises it.

    "Kind"/"hard" still comes from FPL's own 1-5 difficulty rating - a
    different, deliberately independent signal from our own model (see
    ticker.fixture_run_summary's before/after split for why both exist) -
    but the actual fixtures are drawn with our own rating and its pill,
    the same as everywhere else on the page, so a run called "kind" is a
    claim you can see rather than a number you have to take on trust."""
    kind, hard, seen = [], [], set()
    for r in reports:
        if r.team in seen:
            continue
        seen.add(r.team)
        near = ctx.fixture_score(r.element["team"], 3)
        if near is None:
            continue
        if near <= 2.4:
            kind.append((r.team, r.element["team"], near))
        elif near >= 3.6:
            hard.append((r.team, r.element["team"], near))
    if not kind and not hard:
        return ""
    kind.sort(key=lambda x: x[2])
    hard.sort(key=lambda x: -x[2])
    baseline_xg, club_mean_cs = ticker._club_norms(ctx, proj) if proj else ({}, {})

    def block(rows, cls, label):
        if not rows:
            return ""
        items = "".join(
            '<li class="fsw-row"><span class="fsw-club">{club}</span>'
            '<span class="fsw-fdr">FDR {fdr:.1f}</span>'
            '<span class="fsw-fx">{pills}</span></li>'.format(
                club=e(club), fdr=fdr,
                pills="".join(
                    ticker.rating_pill(row["opp"], row["home"], row["score"])
                    for row in ticker._rows_for(club, proj, market, next_gw, 3,
                                                baseline_xg.get(club), club_mean_cs.get(club))
                ),
            )
            for club, _tid, fdr in rows
        )
        return f'<div class="lc-block {cls}"><h4>{e(label)}</h4><ul>{items}</ul></div>'

    body = block(kind, "fsw-kind", "Kind run") + block(hard, "fsw-hard", "Hard run")
    return (
        f'<div class="find gapcard"><h3>Fixture swings{components.info_btn()}</h3>'
        '<p class="note" hidden>FPL\'s own 1-5 difficulty rating, averaged over '
        'the next 3 gameweeks - the fixtures behind a "kind" or "hard" run, '
        "not just the number that summarises it.</p>"
        f'{body}</div>'
    )


def findings_section(finds, reports, ctx, proj=None, market=None, next_gw=None,
                      weekly_price=None, xi_ids=None):
    """Findings, with the ones that have a shape drawn rather than listed.

    Three of these are genuinely numeric comparisons and were being written
    out as sentences: goals against expected goals is a gap, defensive
    contribution is a distance to a threshold, and both read better as marks
    than as prose. The rest stay as lists, because a set-piece order or an
    injury note is text and dressing it up as a chart would be decoration."""
    drawn = {"cold", "hot", "defcon", "setpieces", "sample", "price",
             "lineups", "fixtures"}

    gaps = [
        (r.name, r.goals, r.xg)
        for r in sorted(reports, key=lambda r: r.finishing)
        if abs(r.finishing) > 0.4 or r.xg >= 0.5
    ]
    dc_rows = []
    for r in reports:
        threshold = analysis.DEFCON_THRESHOLD.get(r.pos)
        # Minutes floor, not just "played at all": see DEFCON_MIN_MINUTES.
        if not threshold or r.minutes < analysis.DEFCON_MIN_MINUTES:
            continue
        if r.defcon90 >= threshold * 0.55:
            dc_rows.append(
                (r.name, r.defcon90, threshold, r.defcon_hits, r.appearances)
            )
    dc_rows.sort(key=lambda x: -x[1] / x[2])

    # Grouped by duty, because the question is "who takes our penalties".
    duties = (
        ("pens", "On pens", "penalties_order"),
        ("fk", "On free kicks", "direct_freekicks_order"),
        ("corners", "On corners", "corners_and_indirect_freekicks_order"),
    )
    groups = []
    for key, title, field in duties:
        rows = sorted(
            ((r.element.get(field), r.name, r.team)
             for r in reports if r.element.get(field)),
            key=lambda x: x[0],
        )
        groups.append((key, title, rows))

    cards = []
    lu = lineup_card(reports, ctx, proj, market, next_gw, xi_ids)
    if lu:
        cards.append(lu)
    ar = attacking_returns_card(reports)
    if ar:
        cards.append(ar)
    bc = big_chances_card(reports)
    if bc:
        cards.append(bc)
    fsw = fixture_swings_card(reports, ctx, proj, market, next_gw)
    if fsw:
        cards.append(fsw)
    if gaps:
        # Sorted so the two directions do not interleave: everyone owed goals
        # first, everyone in credit after. One green legend over a list that
        # ran both ways explained half the rows and quietly mislabelled the
        # rest.
        gaps.sort(key=lambda g: g[1] - g[2])
        cards.append(components.gap_chart(
            gaps,
            "Goals against expected goals",
            "The line is the gap. Green means the chances are arriving and "
            "the finishing has not caught up - he is owed goals. Amber means "
            "he has scored more than the chances merited, which is the half "
            "of this card that does not repeat.",
            "Scored", "Expected",
        ))
    if dc_rows:
        cards.append(components.defcon_bars(dc_rows))
    sp = components.set_piece_card(groups)
    if sp:
        cards.append(sp)

    # Old price to new, rather than the size of the change: what you would
    # have paid is the number you actually want. Scoped to the last week,
    # not the season - see _update_price_history for why that needs our own
    # snapshot rather than a field FPL's API already gives us.
    moves = []
    for r in reports:
        delta = (weekly_price or {}).get(r.element["id"], 0.0)
        if abs(delta) >= 0.1:
            moves.append((r.name, r.price - delta, r.price))
    moves.sort(key=lambda m: -(m[2] - m[1]))
    pm = components.price_move_card(moves)
    if pm:
        cards.append(pm)
    tail = []
    for fnd in finds:
        if fnd["key"] in drawn:
            continue
        if fnd["key"] in COLLAPSED:
            tail.append(collapsed_finding(fnd))
            continue
        cards.append(finding_card(fnd))
    return (f'<div class="finds">{"".join(cards)}</div>'
            f'{"".join(tail)}')


# Findings that stay shut. Worth keeping, not worth a column of the page.
COLLAPSED = {"baseline"}

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _figures(text):
    """Set the numbers inside a sentence in the mono face.

    Only digits are touched, so there is nothing here that can mangle the
    words around them. It is what makes a findings list scannable: the eye
    goes to the figures without every line having to shout in bold."""
    return _NUM_RE.sub(lambda m: f'<span class="fnum">{m.group()}</span>',
                       e(text))


def finding_card(fnd):
    tone = TONE_COLOR.get(fnd["tone"], "var(--p60)")
    items = []
    for raw in fnd["items"]:
        lead, sep, detail = raw.partition(" - ")
        # Subject as a mono tag, evidence as ordinary prose beside it. The
        # pattern this replaced set the subject in heavy bold on its own line
        # with the evidence in grey underneath, which is the house style of
        # every dashboard template there is - and it made the evidence, the
        # part actually worth reading, the quietest thing on the card.
        if sep and len(lead) < 40:
            items.append(
                f'<li class="fi"><span class="fi-sub">{e(lead)}</span>'
                f'<span class="fi-det">{_figures(detail)}</span></li>'
            )
        else:
            items.append(f'<li class="fi"><span class="fi-det">'
                         f'{_figures(raw)}</span></li>')
    note = f'<p class="note" hidden>{e(fnd["note"])}</p>' if fnd["note"] else ""
    infobtn = components.info_btn() if fnd["note"] else ""
    return (
        f'<div class="find" style="--tone:{tone}">'
        f"<h3>{e(fnd['title'])}{infobtn}</h3>{note}"
        f"<ul class=\"filist\">{''.join(items)}</ul></div>"
    )


def collapsed_finding(fnd):
    """A finding that is worth keeping but not worth showing.

    Last season's numbers are the case: fifteen full-sentence paragraphs of
    context nobody reads before a deadline, taking a whole column of the
    page to say something that only matters when you go looking for it. It
    lives at the bottom, shut, and opens when asked."""
    items = []
    for raw in fnd["items"]:
        lead, sep, detail = raw.partition(" - ")
        if sep and len(lead) < 40:
            items.append(f'<li class="fi"><span class="fi-sub">{e(lead)}</span>'
                         f'<span class="fi-det">{_figures(detail)}</span></li>')
        else:
            items.append(f'<li class="fi"><span class="fi-det">'
                         f'{_figures(raw)}</span></li>')
    note = f'<p class="note">{e(fnd["note"])}</p>' if fnd["note"] else ""
    return (
        '<details class="card collapsible lastseason">'
        f'<summary class="card-head"><h2>{e(fnd["title"])}</h2>'
        f'<span class="sub">{len(fnd["items"])} players &middot; '
        "open for the full-season comparison</span></summary>"
        f'<div class="card-body">{note}'
        f"<ul class=\"filist\">{''.join(items)}</ul></div></details>"
    )


def player_payload(r, ctx, proj, ep, next_gw, photos):
    """Everything the expanded view shows for one player, as plain data.

    Emitted once as JSON and rendered in the browser. Fifteen copies of the
    same markup would be a lot of page weight for a panel you look at one
    player at a time."""
    el = r.element
    flag, news = r.availability
    fixtures = [
        {"gw": row["gw"], "opp": row["opp"], "home": row["home"],
         "cs": round(row["cs"]), "xg": round(row["xg"], 2)}
        for row in ffs.ticker(proj, r.team, next_gw, 6)
    ]
    log = [
        {"gw": h["round"], "opp": ctx.team_name(h["opponent_team"]),
         "home": h["was_home"], "min": h["minutes"],
         "g": h["goals_scored"], "a": h["assists"],
         "xg": round(f(h["expected_goals"]), 2),
         "xa": round(f(h["expected_assists"]), 2),
         "dc": h.get("defensive_contribution", 0),
         "bps": h["bps"], "pts": h["total_points"]}
        for h in sorted(r.history, key=lambda x: x["round"])
    ]
    return {
        "id": el["id"], "name": r.name, "team": r.team, "pos": r.pos,
        "photo": photos.get(el["id"]),
        "price": r.price, "owned": r.owned,
        "priceChange": round(el.get("cost_change_start", 0) / 10.0, 1),
        "flag": flag or "", "news": news,
        "predicted": ctx.is_predicted(el),
        "minutes": r.minutes, "starts": r.starts, "apps": r.appearances,
        "goals": r.goals, "assists": r.assists, "points": r.points,
        "bonus": r.bonus,
        "xg": round(r.xg, 2), "xa": round(r.xa, 2), "xgi": round(r.xgi, 2),
        "xgi90": round(r.xgi90, 2), "defcon90": round(r.defcon90, 1),
        "defconHits": r.defcon_hits, "defcon": r.defcon,
        "threshold": analysis.DEFCON_THRESHOLD.get(r.pos, 0),
        # The drawer needs the same floor the cards use, so a cameo is not
        # quoted as a per-90 rate in one place and withheld in another.
        "defconMin": analysis.DEFCON_MIN_MINUTES,
        "setpieces": r.set_pieces(),
        "opta": el.get("_pulse") or {},
        "ep": ep,
        "fixtures": fixtures,
        "log": log,
        "last": r.last_season(),
    }
WARN_SVG = ('<svg class="ic" viewBox="0 0 16 16" aria-hidden="true">'
            '<path d="M8 2.6 15 14H1Z" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linejoin="round"/>'
            '<path d="M8 6.6v3.2" stroke="currentColor" stroke-width="1.7" '
            'stroke-linecap="round"/><circle cx="8" cy="11.9" r="1" '
            'fill="currentColor"/></svg>')


def player_dialog(payloads):
    """One dialog for every player, filled on demand from the JSON below it."""
    labels = {k: v[0] for k, v in pulse.STATS.items()}
    return (
        '<dialog class="pv" aria-label="Player detail">'
        '<button class="pv-close" aria-label="Close player detail">&times;</button>'
        '<div class="pv-body"></div></dialog>'
        f'<script type="application/json" id="player-data">'
        f"{json.dumps({'players': payloads, 'optaLabels': labels})}</script>"
    )
