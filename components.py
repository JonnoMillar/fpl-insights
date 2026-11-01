#!/usr/bin/env python3
"""
Chart-ish building blocks for the dashboard.

Each of these exists because a table was the wrong shape for the question:

* `ep_column` - the terms of expected points really are parts of one total,
  which is the one situation a stacked bar is right for. One row per man in
  the starting eleven, in the order they stand on the pitch, so each bar can
  be read level with its own card.
* `gap_chart` - a dumbbell. Reading the distance between two dots beats
  reading two numbers and subtracting them in your head.
* `defcon_bars` - "how close to 10" is a bar with a line on it, not a decimal.
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


def gap_chart(rows, title, note, left_label, right_label):
    """A dumbbell chart: two dots joined by a line, one row per player.

    `rows` is [(name, actual, expected)]. The line between the dots is the
    thing being measured, so it carries the direction twice: a solid green
    line where the player is under-performing his chances (they are arriving,
    the finishing will come), a striped dark line where he is over-performing
    them. The stripes are the part a colour-blind reader relies on."""
    if not rows:
        return ""
    top = max(max(a, b) for _n, a, b in rows) or 1.0
    items = []
    for name, actual, expected in rows:
        # A dot centred with `left:X%; margin-left:-5.5px` pushes past the
        # track's own edge whenever X is near 0 or 100 - the CSS percentage
        # is relative to the track's width, but the 5.5px pullback isn't, so
        # at the extremes the dot's centre sits closer to the card's edge
        # than half its own radius. calc() keeps the centre inset by the
        # dot's radius on both ends regardless of the track's actual width.
        fa, fx = actual / top, expected / top
        lo, hi = min(fa, fx), max(fa, fx)
        tone = "gap-under" if actual < expected else "gap-over"
        items.append(
            '<li class="gap"><span class="gapname">{}</span>'
            '<span class="gaptrack">'
            '<span class="gapline {}" style="left:calc(5.5px + (100% - 11px) * {:.4f});'
            'width:calc((100% - 11px) * {:.4f})"></span>'
            '<span class="gapdot d-a" style="left:calc(5.5px + (100% - 11px) * {:.4f})" '
            'title="{} {:g}"></span>'
            '<span class="gapdot d-x" style="left:calc(5.5px + (100% - 11px) * {:.4f})" '
            'title="{} {:.2f}"></span>'
            "</span>"
            '<span class="gapnum tnum">{:g} v {:.2f}</span></li>'.format(
                e(name), tone, lo, hi - lo,
                fa, e(left_label), actual,
                fx, e(right_label), expected,
                actual, expected,
            )
        )
    # The line's colour carries the direction, so the direction belongs in
    # the visible legend rather than in a collapsed note - a single green
    # key over a list that runs both ways explains half of it and quietly
    # mislabels the rest.
    both = (any(a < x for _n, a, x in rows) and any(a > x for _n, a, x in rows))
    dirkey = (
        '<span class="epkey"><i class="k-under"></i>owed goals</span>'
        '<span class="epkey"><i class="k-over"></i>running hot</span>'
        if both else "")
    return (
        '<div class="find gapcard"><h3>' + icon("goals") + '{}{}</h3><p class="note" hidden>{}</p>'
        '<ul class="gaplist">{}</ul>'
        '<p class="eplegend"><span class="epkey"><i class="k-a"></i>{}</span>'
        '<span class="epkey"><i class="k-x"></i>{}</span>{}</p></div>'.format(
            e(title), info_btn(), e(note), "".join(items),
            e(left_label), e(right_label), dirkey
        )
    )


def defcon_bars(rows):
    """Progress toward the defensive-contribution threshold.

    `rows` is [(name, rate_per_90, threshold, hits, appearances)]. The track
    runs to 140% of the threshold so clearing it has somewhere to show."""
    if not rows:
        return ""
    scale = 1.4
    items = []
    for name, rate, threshold, hits, apps in rows:
        if not threshold:
            continue
        pct = min(100.0, rate / threshold * 100 / scale)
        over = rate >= threshold
        colour = "var(--good)" if over else "var(--warn)"
        # Hit rate is the part that decides whether the rate is real, so it
        # gets a three-way read rather than a binary one: a perfect record
        # is the strongest thing this card can say, missing every game is
        # the weakest, and a mixed record sits visibly between the two
        # rather than reading the same as zero.
        if not apps:
            hit_cls = "dchits"
        elif hits == apps:
            hit_cls = "good-pill"
        elif hits == 0:
            hit_cls = "bad-pill"
        else:
            hit_cls = "warn-pill"
        items.append(
            '<li class="dcr"><span class="dcname">{}</span>'
            '<span class="dctrack">'
            '<span class="dcfill" style="width:{:.1f}%;background:{}"></span>'
            '<span class="dcmark" style="left:{:.1f}%" title="Threshold {}"></span>'
            "</span>"
            '<span class="dcnum tnum">{:.1f} / {}</span>'
            '<span class="{}">{} of {}</span></li>'.format(
                e(name), pct, colour, 100 / scale, threshold, rate, threshold,
                hit_cls, hits, apps,
            )
        )
    if not items:
        return ""
    return (
        '<div class="find gapcard"><h3>' + icon("defence") + 'Defensive contribution{}</h3>'
        '<p class="note" hidden>Two points a match at the threshold. The notch is the '
        "threshold; the bar is the rate per 90.</p>"
        '<ul class="dclist">{}</ul></div>'.format(info_btn(), "".join(items))
    )


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


def set_piece_card(groups):
    """Set-piece duties, grouped by the duty rather than by the player.

    The question is "who takes our penalties", not "what does this player
    take", so the duty is the heading and the takers sit under it in the order
    the club has them."""
    blocks = []
    for key, title, rows in groups:
        if not rows:
            continue
        takers = "".join(
            '<li{cls}><span class="sprank">{order}</span>'
            '<span class="spname">{name}</span>'
            '<span class="spteam">{team}</span></li>'.format(
                cls=' class="first"' if order == 1 else "",
                order=order, name=e(name), team=e(team))
            for order, name, team in rows
        )
        blocks.append(
            '<div class="spgroup"><h4>{}{}</h4><ol class="splist">{}</ol></div>'.format(
                ICONS.get(key, ""), e(title), takers
            )
        )
    if not blocks:
        return ""
    return (
        '<div class="find gapcard"><h3>' + icon("free-kicks") + 'Set pieces{}</h3>'
        '<p class="note" hidden>Who takes them, in the order the club lists them.</p>'
        '<div class="spwrap">{}</div></div>'.format(info_btn(), "".join(blocks))
    )


TREND = {
    "up": (
        '<svg viewBox="0 0 24 24" class="pmicon" aria-hidden="true">'
        '<path d="M3 17.5l5.5-5.5 3.5 3.5L21 6.5" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        '<path d="M15 6.5h6v6" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "down": (
        '<svg viewBox="0 0 24 24" class="pmicon" aria-hidden="true">'
        '<path d="M3 6.5l5.5 5.5 3.5-3.5L21 17.5" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        '<path d="M15 17.5h6v-6" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
}


def price_move_card(moves):
    """Price changes since the season started, risers against fallers.

    `moves` is [(name, old_price, new_price)]. Written as a split rather than
    one list because the two directions mean opposite things - a rise you
    missed costs you money, a fall in your own squad costs you money - and a
    single column mixing them made you read every line to find out which
    kind each one was. The prices are shown as the move itself, old to new,
    since "risen 0.1m, now 5.6m" asked you to do the subtraction to find out
    what you would have paid."""
    ups = [m for m in moves if m[2] > m[1]]
    downs = [m for m in moves if m[2] < m[1]]
    if not ups and not downs:
        return ""

    def block(rows, key, title):
        if not rows:
            return ""
        items = "".join(
            '<li><span class="pmname">{name}</span>'
            '<span class="pmprice">{old:.1f}<i>&rarr;</i>{new:.1f}</span></li>'
            .format(name=e(n), old=o, new=w)
            for n, o, w in rows
        )
        return (
            '<div class="pmgroup pm-{key}"><h4>{icon}{title}</h4>'
            '<ul class="pmlist">{items}</ul></div>'.format(
                key=key, icon=TREND[key], title=e(title), items=items)
        )

    return (
        '<div class="find gapcard"><h3>' + icon("price-rise") + 'Price movement{}</h3>'
        '<p class="note" hidden>Over the last 7 days. The season-long change for '
        "any one player is on their own card, in the squad view.</p>"
        '<div class="pmwrap">{}{}</div></div>'.format(
            info_btn(), block(ups, "up", "Rise"), block(downs, "down", "Fall")
        )
    )


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

    cards = []
    for g in groups:
        if not g["rows"]:
            continue
        body = '<ol class="sllist">{}</ol>'.format(
            _items(g["rows"], g.get("pair", False)))
        cards.append(
            '<li class="slcard" style="--accent:{tone}">'
            '<h4><svg viewBox="0 0 24 24" class="slicon" aria-hidden="true">{icon}</svg>'
            "{title}</h4>"
            '{note}{body}</li>'.format(
                tone=g["tone"], icon=STAT_ICONS.get(g["icon"], ""),
                title=e(g["title"]),
                note='<p class="slnote">{}</p>'.format(e(g["note"])) if g["note"] else "",
                body=body,
            )
        )
    if not cards:
        return ""
    return (
        '<section class="card"><div class="card-head"><h2>{}{}</h2>'
        '<span class="sub" hidden>{}</span></div>'.format(
            e(title), info_btn(), e(sub))
        # Four cards in a three-wide grid is 3 + 1, with the odd one beside a
        # hole; four questions belong in a 2x2. Six stay 3x2.
        + ('<div class="card-body">{}<ul class="slwrap'
           + (' slwrap-4' if len(cards) == 4 else '')
           + '">{}</ul></div></section>').format(
            '<p class="sllede">{}</p>'.format(e(lede)) if lede else "",
            "".join(cards)
        )
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


def transfer_deck(singles, pairs, hit=4):
    """Other transfer options as a swipe deck on the green panel.

    Each option is a purple card: the outgoing player greyed, the incoming one
    standing on the photo panel's edge, the opponent's crest on a glass
    plate, then the name and one big gain. Ranked by gain, best first, pairs
    and singles together; a pair is priced after whatever hit it costs. The
    ranked list beside the deck (faces on a phone) jumps straight to any
    card. The plan above has already weighed these and chosen the week, so
    this is for browsing the alternatives, never for the headline move."""
    options = []
    for r in singles or []:
        options.append(("single", r["gain"], r))
    for p in pairs or []:
        options.append(("pair", p["gain"] - hit, p))
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
            label = ""
            title = e(in_name)
            spend = -r["spend"]
            money = "free swap" if abs(spend) < 0.05 else f"bank {spend:+.1f}m"
            meta = (f'{e(r["in_club"])} &middot; {r["price"]:.1f}m, for {e(out_name)}'
                    f'<br>{money}')
            words = (f'His <b class="tnum">{r["in_score"]["total"]:.1f}</b> against '
                     f'{e(out_name)}\'s <span class="tnum">{r["out_score"]["total"]:.1f}</span>.')
            unit = "to your XI, next<br>five weeks"
            faces = [r.get("in_photo")]
            short = in_name
            notes = [r["timing"]] if r.get("timing") else []
            if r.get("elite"):
                notes.append(f'{r["elite"]["elite"]:.0f}% of the top 100 own him.')
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
                    f'<br>{r["bank_after"]:.1f}m left in the bank')
            words = ""
            unit = ("together, next<br>five weeks" if hit == 0
                    else f"after the −{hit},<br>next five weeks")
            faces = [leg.get("in_photo") for leg in legs]
            short = " + ".join(leg["in"]["web_name"] for leg in legs)
            notes = [leg["timing"] for leg in legs if leg.get("timing")]
        note_html = "".join(f"<p>{e(n)}</p>" for n in notes[:1])
        cards.append(
            f'<article class="deck-card deck-{kind}" data-k="{k}" aria-roledescription="slide" '
            f'aria-label="{k + 1} of {len(options)}: {e(short)}">'
            f'<div class="deck-photo">{photo_out}{arrow}{photo_in}{plate}</div>'
            f'<div class="foil" aria-hidden="true"></div>'
            f'<div class="deck-body">{label}<b class="disp deck-name">{title}</b>'
            f'<span class="deck-meta">{meta}</span>'
            f'<div class="deck-words">{words}{note_html}</div>'
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
        '<p class="deck-lede">Ranked on the next five gameweeks if made now. The plan '
        'has already weighed them and picked its week.</p>'
        f'<span class="deck-pos tnum" aria-live="polite"><b>1</b> of {n}</span>'
        '<div class="deck-btns">'
        f'<button class="deck-btn" type="button" data-step="-1" aria-label="Previous option">{icon("previous")}</button>'
        f'<button class="deck-btn" type="button" data-step="1" aria-label="Next option">{icon("next")}</button>'
        '</div></div>'
        f'<div class="deck" aria-roledescription="carousel" aria-label="Other transfer options" tabindex="0">'
        f'{"".join(cards)}</div>'
        f'<ol class="deck-list">{"".join(index)}</ol></section>'
    )
