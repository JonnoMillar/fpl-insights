"""Cards for the Squad tab: the pitch views, squad table, team news and player dialog."""

import math

import analysis
import components
import ticker
from analysis import f
from cards_common import e, icon, meter


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
              next_gw, played=True, ep=None, incoming=False):
    """A next-week player card with fixture, projected points and IN badge."""
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
    fx_html = ""
    if fx_rows and fx_rows[0]["opp"] is not None:
        fixture = fx_rows[0]
        defensive = r.pos in ("GKP", "DEF")
        label = "CS" if defensive else "Team xG"
        value = f"{fixture['cs']:.0f}%" if defensive else f"{fixture['xg']:.2f}"
        description = "Team clean-sheet chance" if defensive else "Expected team goals"
        venue = "H" if fixture["home"] else "A"
        fx_html = (f'<span class="pk-opponent">{e(fixture["opp"])} <small>({venue})</small></span>'
                   f'<span class="pk-market" title="{description}"><span>{label}</span> <b>{value}</b></span>')
    has_fixture = any(fx.get("event") == next_gw and el["team"] in (fx["team_h"], fx["team_a"])
                      for fx in ctx.fixtures)
    if not has_fixture or not fx_rows or fx_rows[0]["opp"] is None:
        fx_html = '<span class="fxpill">Unavailable</span>' if has_fixture else '<span class="fxpill">Blank</span>'

    xp = f'{ep["total"]:.1f}' if ep else "—"
    snippet = f'<div class="pk-xp tnum" title="Projected points before captain or chip multipliers">{xp}<small>xP</small></div>'
    cls = "pl pk" + (" is-incoming" if incoming else "")
    badge = '<span class="incoming-badge" aria-hidden="true">IN</span>' if incoming else ""
    if incoming:
        title += " - suggested incoming transfer"
    return (
        f'<div class="{cls}" title="{e(title)}" data-player="{el["id"]}" '
        f'role="button" tabindex="0" aria-label="{e(title)}">{arm}{badge}'
        f'<div class="crest">{crest}</div>'
        f'<div class="nm">{e(r.name)}</div>'
        f'<div class="pk-fx">{fx_html}</div>'
        f"{snippet}</div>"
    )


def pick_team_pitch(xi, bench, ctx, badges, shirts, captain_id, vice_id,
                    proj, market, next_gw, eps=None, incoming_ids=()):
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
    by_id = {r.element["id"]: ep for r, ep in eps or []}
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
                     market, next_gw, ep=by_id.get(r.element["id"]),
                     incoming=r.element["id"] in incoming_ids)
            for r in rows[k]
        )
        pitch_order.extend(r.element["id"] for r in rows[k])
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    cards = "".join(
        pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj, market,
                 next_gw, ep=by_id.get(r.element["id"]),
                 incoming=r.element["id"] in incoming_ids)
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
    ("Starting", "", True),
]


def squad_table(reports, ctx, captain_id, vice_id, eps_by_id=None):
    """Your fifteen side by side. Fixtures are not repeated here: the
    fixture-run band covers clubs, and the player profile each name opens
    covers one player's next six."""
    head = "".join(
        f'<th scope="col" class="{cls}{" sortable" if sortable else ""}">{e(label)}</th>'
        for label, cls, sortable in SQUAD_HEAD
    )
    maxx = max([r.xgi90 for r in reports] + [0.01])
    eps_by_id = eps_by_id or {}
    body = []
    for r in reports:
        el = r.element
        flag, news = r.availability
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
            f'<td data-v="{sort_key}">{pred_cell}</td></tr>'
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


def lineup_card(reports, ctx, xi_ids=None):
    """Who is predicted to start, as a donut and then an exception list.

    Fifteen rows saying "predicted to start" is fifteen rows of nothing:
    the information is entirely in the handful who are not, and in how many
    that is. So the count leads with a donut, and only the men who need a
    decision are named. Their fixtures are in the player profile, which a
    name opens, rather than repeated here.

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
    views = [
        ("squad", "Full squad", reports),
        ("xi", "Starting XI", [r for r in reports if r.element["id"] in xi_ids]),
        ("bench", "Bench", [r for r in reports if r.element["id"] not in xi_ids]),
    ]

    def block(rows, cls, label):
        if not rows:
            return ""
        # Availability news rides with the name: the injury, suspension or
        # doubt is why he is out, and the old Availability card said only that.
        items = "".join(
            f'<li><button type="button" class="lc-name rowlink" data-player="{r.element["id"]}">'
            f'{e(r.name)}</button><span class="lc-club">{e(r.team)}</span>'
            + (f'<span class="lc-flag">{e(r.availability[0])}</span>' if r.availability[0] else "")
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
        # The named share is purple, or brand green for a clean sweep; the
        # unknown and left-out arcs are amber and night, so each state also
        # differs in lightness, and the count is printed beside the ring.
        tone = "var(--green)" if starting == total and total else "var(--purple)"
        if not total:
            body = '<p class="lc-clear">Nobody in this group.</p>'
        elif not out and not unknown:
            body = '<p class="lc-clear">All named</p>'
        else:
            body = (block(out, "lc-out", "Not predicted")
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
            aria, "", "",
        ) if total else ""
        panels.append(
            f'<div class="lcpanel" data-lcview="{key}" data-lclabel="{e(label)}"'
            f'{" hidden" if i else ""}>'
            f'<div class="lcstat" style="--lc-tone:{tone}">'
            f"{ring}"
            f'<div class="lcread">'
            f'<p class="lcfig"><b>{starting}</b><span>of {total}</span></p>'
            f'<p class="lccap">predicted to start</p>'
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
        f'<div class="find gapcard lccard"><h3>{icon("available")}Predicted line-ups'
        f'{components.info_btn()}</h3>'
        f'<p class="note" hidden>Fantasy Football Scout\'s predicted elevens. '
        f'They are re-tuned after each press conference, so they sharpen '
        f'closer to the deadline.</p>'
        f'{nav}{"".join(panels)}</div>'
    )


def team_news(reports, ctx, xi_ids=None):
    """The Squad tab's one findings card: who may not play this week.

    Everything the old findings column also carried - returns, chances,
    goals against xG, DefCon, set pieces, price moves, last season - is a
    column of the squad table or a figure in the player profile, so it
    lives there once instead of twice."""
    lu = lineup_card(reports, ctx, xi_ids)
    return f'<div class="finds finds-one">{lu}</div>' if lu else ""


WARN_SVG = ('<svg class="ic" viewBox="0 0 16 16" aria-hidden="true">'
            '<path d="M8 2.6 15 14H1Z" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linejoin="round"/>'
            '<path d="M8 6.6v3.2" stroke="currentColor" stroke-width="1.7" '
            'stroke-linecap="round"/><circle cx="8" cy="11.9" r="1" '
            'fill="currentColor"/></svg>')
