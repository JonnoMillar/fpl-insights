#!/usr/bin/env python3
"""
Chart-ish building blocks for the dashboard.

Each of these exists because a table was the wrong shape for the question:

* `ep_column` - the terms of expected points really are parts of one total,
  which is the one situation a stacked bar is right for. One row per man in
  the starting eleven, in the order they stand on the pitch, so each bar can
  be read level with its own card.
* `sparkline` - shape of a run of gameweeks, at a glance.

Kept apart from dashboard.py so the page assembly stays readable.
"""

import html

from cards_common import icon


def e(x):
    return html.escape(str(x), quote=True)


# Segment colours for expected points, in the order a manager thinks of a
# score. Seven parts cannot be told apart by lightness alone, so every bar
# that uses them also prints an itemised, signed list in words; the colours
# only make the parts visible. Appearance points are a pale grey on purpose:
# turning up is the unremarkable part of a score. gc and cards are
# deductions and never draw as a positive segment.
EP_PARTS = (
    ("goals", "Goals", "#16001a"),
    ("assists", "Assists", "#7b2f86"),
    ("defence", "Clean sheet", "#00ff87"),
    ("saves", "Saves", "#1b5ce0"),
    ("appearance", "Appearance", "#d3cdd6"),
    ("defcon", "DefCon", "#ffb000"),
    ("bonus", "Bonus", "#8e8494"),
    ("gc", "Goals conceded", "#1b5ce0"),
    ("cards", "Cards", "#16001a"),
)


def ep_column(eps, order):
    """Expected points for the starting eleven, one row per pitch card.

    `order` is the player ids in the order they stand on the pitch, and the
    rows are emitted in exactly that order rather than ranked - the whole
    point of this layout is that row N sits level with card N, so the bar
    is read as belonging to the man beside it. Sorting by size would break
    that correspondence and turn it back into the ranked list it replaced.

    The eleven are scaled against the biggest of the eleven, so the widths
    compare like with like across one gameweek's team."""
    if not eps:
        return ""
    by_id = {r.element["id"]: (r, ep) for r, ep in eps}
    picked = [by_id[pid] for pid in order if pid in by_id]
    if not picked:
        return ""
    top = max(ep["total"] for _r, ep in picked) or 1.0
    total = sum(ep["total"] for _r, ep in picked)

    rows = []
    for i, (r, ep) in enumerate(picked):
        segs = "".join(
            '<span class="seg" style="width:{:.2f}%;background:{}" '
            'title="{} {:.2f}"></span>'.format(
                ep.get(key, 0.0) / top * 100, colour, e(label), ep.get(key, 0.0))
            for key, label, colour in EP_PARTS
            if ep.get(key, 0.0) > 0.01
        )
        # The name is carried but hidden while the two columns sit side by
        # side, where the card level with the row already says who this is.
        # Stacked on a narrow screen there is no card beside it, and eleven
        # anonymous bars are not worth showing - so it reappears there.
        rows.append(
            '<li class="epcr" style="--i:{i}">'
            '<span class="epcname">{name}</span>'
            '<span class="epbar">{segs}</span>'
            '<span class="eptot tnum">{total:.1f}</span></li>'.format(
                i=i, name=e(r.name), segs=segs, total=ep["total"])
        )
    legend = "".join(
        '<span class="epkey"><i style="background:{}"></i>{}</span>'.format(c, e(l))
        for _k, l, c in EP_PARTS
    )
    return (
        '<div class="epside" aria-hidden="true">'
        '<div class="epside-head"><span class="epside-k">Projected</span>'
        '<b class="tnum">{total:.1f}</b><span class="epside-u">pts, this XI</span>'
        "</div>"
        '<ul class="epclist">{rows}</ul>'
        '<p class="eplegend">{legend}</p></div>'.format(
            total=total, rows="".join(rows), legend=legend)
    )


def info_btn():
    """The "i" that reveals a card's explanatory line on click.

    Every card head used to print its grey explanation in full, permanently,
    which is a sentence of small print nobody asked to read before they'd
    even looked at the numbers. Hiding it behind one click keeps the title
    doing the work at a glance; the JS toggle lives once in JS, keyed off
    this class, rather than per-card."""
    return ('<button class="infobtn" type="button" aria-label="More information" '
            'aria-expanded="false">' + icon("information") + '</button>')


# Hand-drawn rather than fetched: an icon font or sprite sheet would be
# another asset to embed, and these are three shapes.
ICONS = {
    "pens": (
        '<svg viewBox="0 0 24 24" aria-hidden="true" class="spicon">'
        '<path d="M3 4h18v10a9 9 0 0 1-18 0Z" fill="none" stroke="currentColor" '
        'stroke-width="1.6" stroke-linejoin="round"/>'
        '<circle cx="12" cy="9.5" r="1.5" fill="currentColor"/>'
        '<path d="M12 14.5a4 4 0 0 0 0 0" fill="none"/>'
        '<circle cx="12" cy="17" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/>'
        "</svg>"
    ),
    "fk": (
        '<svg viewBox="0 0 24 24" aria-hidden="true" class="spicon">'
        '<circle cx="5.5" cy="18" r="2.6" fill="none" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M8 16C11 9 16 6 21 5" fill="none" stroke="currentColor" '
        'stroke-width="1.6" stroke-linecap="round" stroke-dasharray="2.6 2.6"/>'
        '<path d="M14 20v-5M17 20v-5M20 20v-5" stroke="currentColor" '
        'stroke-width="1.6" stroke-linecap="round"/>'
        "</svg>"
    ),
    "corners": (
        '<svg viewBox="0 0 24 24" aria-hidden="true" class="spicon">'
        '<path d="M5 21V4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        '<path d="M5 4.5h9l-4 3.2 4 3.2H5Z" fill="currentColor" stroke="none"/>'
        '<path d="M21 21a16 16 0 0 0-16-6" fill="none" stroke="currentColor" '
        'stroke-width="1.6" stroke-linecap="round"/>'
        "</svg>"
    ),
}


def duty_badges(el):
    """Set-piece duty icons for a suggested transfer target - pens, free
    kicks, corners, only the ones he's actually on. The responsibility
    itself is worth as much as the projection when you're weighing a
    signing, and until now it only showed up on the set-piece card, not
    anywhere near the suggestion itself."""
    order_fields = (("pens", "penalties_order"), ("fk", "direct_freekicks_order"),
                    ("corners", "corners_and_indirect_freekicks_order"))
    icons = "".join(ICONS[key] for key, field in order_fields if el.get(field))
    return '<span class="duty-badges">{}</span>'.format(icons) if icons else ""


PITCH_MARKS = (
    '<div class="pmk" aria-hidden="true">'
    '<i class="pmk-half"></i><i class="pmk-circle"></i><i class="pmk-spot"></i>'
    '<i class="pmk-box pmk-t"></i><i class="pmk-box pmk-b"></i>'
    '<i class="pmk-six pmk-t"></i><i class="pmk-six pmk-b"></i>'
    '<i class="pmk-goal pmk-t"></i><i class="pmk-goal pmk-b"></i>'
    '<i class="pmk-arc pmk-arc-tl"></i><i class="pmk-arc pmk-arc-tr"></i>'
    '<i class="pmk-arc pmk-arc-bl"></i><i class="pmk-arc pmk-arc-br"></i>'
    "</div>"
)
"""The lines, as one constant every pitch on the page opens with.

Decoration in the strict sense - it carries nothing a screen reader wants,
hence aria-hidden - so it is markup rather than CSS only because a dozen
pseudo-elements are not available on one div. See the .pmk block in CSS
for why the boxes are sized the way they are."""


WC_STATS = (
    ("xp", "xP", "{:.1f}"),
    ("fixture", "Fixture rating", "{:.1f}"),
    ("xgi", "xGI", "{:.1f}"),
    ("form", "Form", "{:.1f}"),
)


def wc_stats_block(before, after):
    """Before/after across the four numbers a rebuild should actually move -
    not just "ten swaps happened" but whether the resulting XI is stronger
    on points, fixtures, underlying attacking numbers and recent form."""
    if not after:
        return ""
    rows = []
    for key, label, fmt in WC_STATS:
        a = after.get(key, 0.0)
        b = before.get(key, 0.0) if before else 0.0
        delta = a - b
        cls = "wc-up" if delta > 0.05 else ("wc-down" if delta < -0.05 else "wc-flat")
        rows.append(
            '<div class="wcstat"><span class="wcstat-k">{label}</span>'
            '<span class="wcstat-b">{bval}</span>'
            '<span class="wcstat-arrow" aria-hidden="true">&rarr;</span>'
            '<span class="wcstat-a">{aval}</span>'
            '<span class="wcstat-d {cls}">{delta}</span></div>'.format(
                label=e(label), bval=fmt.format(b), aval=fmt.format(a),
                cls=cls, delta=("{:+.1f}".format(delta) if before else "&mdash;"),
            )
        )
    return '<div class="wcstats">{}</div>'.format("".join(rows))


STAT_ICONS = {
    "ball": '<path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4.2 3.6 2.6-1.4 4.2H9.8'
            'L8.4 9.8Z" fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linejoin="round"/>',
    "boot": '<path d="M3 15h9l4-3 5 2v4H3Z" fill="none" stroke="currentColor" '
            'stroke-width="1.5" stroke-linejoin="round"/>'
            '<path d="M6 15V8" stroke="currentColor" stroke-width="1.5" '
            'stroke-linecap="round"/>',
    "key": '<path d="M4 12h9M13 8l4 4-4 4" fill="none" stroke="currentColor" '
           'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
           '<circle cx="19" cy="12" r="2" fill="currentColor"/>',
    "shield": '<path d="M12 3 20 6v6c0 4-3.4 7.4-8 9-4.6-1.6-8-5-8-9V6Z" fill="none" '
              'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>',
    "spark": '<path d="M4 17l5-6 4 3 6-8" fill="none" stroke="currentColor" '
             'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "run": '<circle cx="14" cy="5" r="2" fill="currentColor"/>'
           '<path d="M13 9l-4 3 2 4-3 4M13 9l4 2 2 4" fill="none" '
           'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
           'stroke-linejoin="round"/>',
}


def stat_leaders(groups, title="League leaders",
                 sub="Who is topping each measure this season. Your players are marked.",
                 lede=""):
    """Who leads the league on each measure, a few names deep.

    Narrow columns rather than one wide table: these are six separate
    questions, not six columns of one, and side by side they take a fraction
    of the height a table of the same content would.

    `title`/`sub` are parameters so the Scout section can borrow the same
    grammar for its own questions rather than growing a second, nearly
    identical list component."""
    def _items(rows, pair):
        if pair:
            return "".join(
                '<li{cls}><span class="slrank">{i}</span>'
                '<span class="slname">{name}</span>'
                '<span class="slteam">{team}</span>'
                '<span class="slval"><b>{p:g}</b>{sub}</span></li>'.format(
                    cls=' class="mine"' if mine else "",
                    i=i, name=e(name), team=e(team), p=p,
                    sub=('<span class="pairsub">, {:g}</span>'.format(s)
                         if s is not None else ""))
                for i, (name, team, p, s, mine) in enumerate(rows, 1)
            )
        return "".join(
            '<li{cls}><span class="slrank">{i}</span>'
            '<span class="slname">{name}</span>'
            '<span class="slteam">{team}</span>'
            '<span class="slval">{val}</span></li>'.format(
                cls=' class="mine"' if mine else "",
                i=i, name=e(name), team=e(team), val=e(val))
            for i, (name, team, val, mine) in enumerate(rows, 1)
        )

    cards, notes = [], []
    for g in groups:
        if not g["rows"]:
            continue
        if g["note"]:
            notes.append(f'{g["title"]}: {g["note"]}')
        body = '<ol class="sllist">{}</ol>'.format(
            _items(g["rows"], g.get("pair", False)))
        cards.append(
            '<li class="slcard" style="--accent:{tone}">'
            '<h4><svg viewBox="0 0 24 24" class="slicon" aria-hidden="true">{icon}</svg>'
            "{title}</h4>"
            '{body}</li>'.format(
                tone=g["tone"], icon=STAT_ICONS.get(g["icon"], ""),
                title=e(g["title"]), body=body,
            )
        )
    if not cards:
        return ""
    return (
        '<section class="card"><div class="card-head"><h2>{}{}</h2>'
        '<span class="sub" hidden>{}</span></div>'.format(
            e(title), info_btn(), "<br>".join(e(t) for t in [lede, sub, *notes] if t))
        # Four cards in a three-wide grid is 3 + 1, with the odd one beside a
        # hole; four questions belong in a 2x2. Six stay 3x2.
        + ('<div class="card-body"><ul class="slwrap'
           + (' slwrap-4' if len(cards) == 4 else '')
           + '">{}</ul></div></section>').format("".join(cards))
    )


def sparkline(values, width=104, height=26, tone="var(--accent)"):
    """A bare line with the last point emphasised. No axes - it is a shape,
    not a chart, and the number it belongs to is always printed beside it."""
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)
    pts = [
        (i * step, height - 2 - (v - lo) / span * (height - 6))
        for i, v in enumerate(values)
    ]
    path = " ".join(
        "{}{:.1f},{:.1f}".format("M" if i == 0 else "L", x, y)
        for i, (x, y) in enumerate(pts)
    )
    lx, ly = pts[-1]
    return (
        '<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        'aria-hidden="true"><path d="{p}" fill="none" stroke="{c}" '
        'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        '<circle cx="{x:.1f}" cy="{y:.1f}" r="2.8" fill="{c}"/></svg>'.format(
            w=width, h=height, p=path, c=tone, x=lx, y=ly
        )
    )


def _opp_plate(opp):
    if not opp:
        return ""
    crest = f'<img src="{opp["crest"]}" alt="">' if opp.get("crest") else ""
    return (f'<span class="opp-plate">{crest}{e(opp["name"])}, '
            f'{"home" if opp["home"] else "away"}</span>')


def _deck_figs(rows):
    """The why, as figures: projected points, form, a chance rate and the
    next three fixtures' mean rating (0-10, higher is better), one row per
    player."""
    labels = {f["chance_label"] for _n, _xp, f, _was in rows}
    chance = labels.pop() if len(labels) == 1 else "xGI·xGC/90"

    def num(v, fmt="{:.1f}"):
        return "&ndash;" if v is None else fmt.format(v)

    body = "".join(
        f'<tr{" class=was" if was else ""}><th scope="row">{e(name)}</th>'
        f'<td>{num(xp)}</td><td>{num(f["form"])}</td><td>{num(f["chance"], "{:.2f}")}</td>'
        f'<td>{num(f["fix"])}</td></tr>'
        for name, xp, f, was in rows)
    return ('<table class="deck-figs tnum"><thead><tr><th></th><th scope="col">xP</th>'
            f'<th scope="col">Form</th><th scope="col">{chance}</th>'
            '<th scope="col" title="Next three fixtures, out of 10, higher is better">Fix</th></tr></thead>'
            f'<tbody>{body}</tbody></table>')


def transfer_deck(singles, pairs, hit=4, end_gw=None, plan_moves=(), kneejerk=None):
    """Other transfer options as a swipe deck.

    Each option is a purple card: the outgoing player greyed, the incoming one
    standing on the photo panel's edge, the opponent's crest on a glass
    plate, then the name, a few figures for why and one big gain. Ranked by
    gain, best first, pairs and singles together; a pair is priced after
    whatever hit it costs. The ranked list beside the deck (faces on a phone)
    jumps straight to any card.

    Alternatives only: a move the plan already makes (`plan_moves`, a set of
    (out id, in id)) is the plan's card, not this deck's, and a pair made
    entirely of such moves goes with it. `kneejerk` ({"id", "points", "gw"})
    tags the card that signs last week's big haul you did not own."""
    plan_moves = set(plan_moves)

    def planned(out_el, in_el):
        return (out_el.element["id"], in_el["id"]) in plan_moves

    options = []
    for r in singles or []:
        if not planned(r["out"], r["in"]):
            options.append(("single", r["gain"], r))
    for p in pairs or []:
        if not all(planned(leg["out"], leg["in"]) for leg in p["legs"]):
            options.append(("pair", p["gain"] - hit, p))
    window = f"xP to GW{end_gw}" if end_gw else "xP"
    if not options:
        return ""
    options.sort(key=lambda o: -o[1])
    cards, index = [], []
    for k, (kind, gain, r) in enumerate(options):
        if kind == "single":
            out_name, in_name = r["out"].name, r["in"]["web_name"]
            photo_out = (f'<img class="cut deck-old" src="{r["out_photo"]}" alt="">'
                         if r.get("out_photo") else "")
            photo_in = (f'<img class="cut deck-new" src="{r["in_photo"]}" alt="">'
                        if r.get("in_photo") else "")
            arrow = f'<span class="deck-arrow">{icon("next")}</span>'
            plate = _opp_plate(r.get("opp"))
            duties = "".join(
                f'<span title="{e(word)}">{icon(ico)}</span>'
                for field, ico, word in (("penalties_order", "penalties", "On penalties"),
                                         ("direct_freekicks_order", "free-kicks", "On free kicks"),
                                         ("corners_and_indirect_freekicks_order", "corners", "On corners"))
                if r["in"].get(field) == 1)
            if duties:
                plate += f'<span class="deck-duties">{duties}</span>'
            label = (f'<span class="lab">Knee-jerk &middot; {kneejerk["points"]} in '
                     f'GW{kneejerk["gw"]}</span>'
                     if kneejerk and kneejerk["id"] == r["in"]["id"] else "")
            title = e(in_name)
            spend = -r["spend"]
            money = "free swap" if abs(spend) < 0.05 else f"bank {spend:+.1f}m"
            meta = f'{e(r["in_club"])} &middot; {r["price"]:.1f}m &middot; {money}'
            figs = _deck_figs([(in_name, r["in_score"]["total"], r["figs"][1], False),
                               (out_name, r["out_score"]["total"], r["figs"][0], True)])
            unit = f"to your XI,<br>{window}"
            faces = [r.get("in_photo")]
            short = in_name
        else:
            legs = r["legs"]
            photo_out = ""
            photo_in = "".join(
                f'<img class="cut deck-pair deck-pair-{n}" src="{leg["in_photo"]}" alt="">'
                for n, leg in enumerate(legs[:2]) if leg.get("in_photo"))
            arrow = ""
            old = "".join(f'<img class="face" src="{leg["out_photo"]}" alt="">'
                          for leg in legs if leg.get("out_photo"))
            plate = (f'<span class="opp-plate"><span class="faces">{old}</span>'
                     f'{"Both free" if hit == 0 else f"−{hit} hit"}</span>')
            label = f'<span class="lab">{e(r.get("tag") or "Pair")}</span>'
            title = " + ".join(e(leg["in"]["web_name"]) for leg in legs)
            meta = (f'for {" and ".join(e(leg["out"].name) for leg in legs)}'
                    f' &middot; {r["bank_after"]:.1f}m left')
            figs = _deck_figs([(leg["in"]["web_name"], leg["in_score"]["total"], leg["figs"][1], False)
                               for leg in legs])
            unit = (f"together,<br>{window}" if hit == 0
                    else f"after the −{hit},<br>{window}")
            faces = [leg.get("in_photo") for leg in legs]
            short = " + ".join(leg["in"]["web_name"] for leg in legs)
        # The shimmer sits on the card and the photo panel's ground, never
        # across the players standing in front of it.
        cards.append(
            f'<article class="deck-card deck-{kind}" data-k="{k}" aria-roledescription="slide" '
            f'aria-label="{k + 1} of {len(options)}: {e(short)}">'
            f'<div class="foil" aria-hidden="true"></div>'
            f'<div class="deck-photo"><div class="foil" aria-hidden="true"></div>'
            f'{photo_out}{arrow}{photo_in}{plate}</div>'
            f'<div class="deck-body">{label}<b class="disp deck-name">{title}</b>'
            f'<span class="deck-meta">{meta}</span>{figs}'
            f'<div class="deck-gain"><b class="big tnum">{gain:+.1f}</b><span>{unit}</span></div>'
            f'</div></article>')
        face_html = "".join(f'<img class="face" src="{ph}" alt="">' for ph in faces if ph)
        index.append(
            f'<li><button class="deck-idx" type="button" data-k="{k}" '
            f'aria-current="{"true" if k == 0 else "false"}">'
            f'<span class="faces">{face_html}</span><b>{e(short)}</b>'
            f'<span class="tnum">{gain:+.1f}</span></button></li>')
    n = len(options)
    count = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE", 6: "SIX", 7: "SEVEN",
             8: "EIGHT", 9: "NINE", 10: "TEN", 11: "ELEVEN", 12: "TWELVE"}.get(n, str(n))
    return (
        '<section class="deck-panel" id="other-transfers" aria-labelledby="deck-title">'
        '<div class="deck-intro"><span class="lab">Other transfer options</span>'
        f'<h2 class="disp" id="deck-title">{count} MORE WORTH A LOOK.</h2>'
        f'<span class="deck-pos tnum" aria-live="polite"><b>1</b> of {n}</span>'
        '<div class="deck-btns">'
        f'<button class="deck-btn" type="button" data-step="-1" aria-label="Previous option">{icon("previous")}</button>'
        f'<button class="deck-btn" type="button" data-step="1" aria-label="Next option">{icon("next")}</button>'
        '</div></div>'
        f'<div class="deck" aria-roledescription="carousel" aria-label="Other transfer options" tabindex="0">'
        f'{"".join(cards)}</div>'
        f'<ol class="deck-list">{"".join(index)}</ol></section>'
    )
