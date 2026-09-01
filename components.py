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


def e(x):
    return html.escape(str(x), quote=True)


# Segment colours for expected points, validated for colour-vision
# deficiency rather than chosen by eye: worst adjacent pair is dE 12.0 for
# deuteranopia and 9.4 for tritanopia, both clear of the 8 target. The grey
# for appearance points fails a chroma floor on purpose - turning up is the
# unremarkable part of a score and should read that way. Cyan and amber sit
# under 3:1 against white, so every segment also carries a tooltip, a legend
# entry and a printed number in the player view.
EP_PARTS = (
    ("goals", "Goals", "#953bff"),
    ("assists", "Assists", "#00b3d6"),
    ("defence", "Clean sheet", "#00a35c"),
    ("appearance", "Appearance", "#87668a"),
    ("defcon", "DefCon", "#e07b00"),
    ("bonus", "Bonus", "#d81b8c"),
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
        rows.append(
            '<li class="epcr" style="--i:{i}">'
            '<span class="epbar">{segs}</span>'
            '<span class="eptot tnum">{total:.1f}</span></li>'.format(
                i=i, segs=segs, total=ep["total"])
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


def gap_chart(rows, title, note, left_label, right_label):
    """A dumbbell chart: two dots joined by a line, one row per player.

    `rows` is [(name, actual, expected)]. The line between the dots is the
    thing being measured, so it carries the colour: green where the player is
    under-performing his chances (they are arriving, the finishing will come),
    amber where he is over-performing them."""
    if not rows:
        return ""
    top = max(max(a, b) for _n, a, b in rows) or 1.0
    items = []
    for name, actual, expected in rows:
        x1, x2 = actual / top * 100, expected / top * 100
        lo, hi = min(x1, x2), max(x1, x2)
        colour = "var(--success)" if actual < expected else "var(--warn)"
        items.append(
            '<li class="gap"><span class="gapname">{}</span>'
            '<span class="gaptrack">'
            '<span class="gapline" style="left:{:.1f}%;width:{:.1f}%;background:{}"></span>'
            '<span class="gapdot d-a" style="left:{:.1f}%" title="{} {:g}"></span>'
            '<span class="gapdot d-x" style="left:{:.1f}%" title="{} {:.2f}"></span>'
            "</span>"
            '<span class="gapnum tnum">{:g} v {:.2f}</span></li>'.format(
                e(name), lo, hi - lo, colour,
                x1, e(left_label), actual,
                x2, e(right_label), expected,
                actual, expected,
            )
        )
    return (
        '<div class="find gapcard"><h3>{}</h3><p class="note">{}</p>'
        '<ul class="gaplist">{}</ul>'
        '<p class="eplegend"><span class="epkey"><i class="k-a"></i>{}</span>'
        '<span class="epkey"><i class="k-x"></i>{}</span></p></div>'.format(
            e(title), e(note), "".join(items), e(left_label), e(right_label)
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
        # gets the highlight when it is perfect: clearing the threshold in
        # every appearance is the strongest thing this card can say.
        hit_cls = "good-pill" if apps and hits == apps else "dchits"
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
        '<div class="find gapcard"><h3>Defensive contribution</h3>'
        '<p class="note">Two points a match at the threshold. The notch is the '
        "threshold; the bar is the rate per 90.</p>"
        '<ul class="dclist">{}</ul></div>'.format("".join(items))
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
        '<div class="find gapcard"><h3>Set pieces</h3>'
        '<p class="note">Who takes them, in the order the club lists them.</p>'
        '<div class="spwrap">{}</div></div>'.format("".join(blocks))
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
        '<div class="find gapcard"><h3>Price movement</h3>'
        '<p class="note">Since the season started.</p>'
        '<div class="pmwrap">{}{}</div></div>'.format(
            block(ups, "up", "Rise"), block(downs, "down", "Fall")
        )
    )


def _face(photo, shirt, name, club, price, tone_class):
    """One side of a swap: portrait, club shirt tucked in the corner, name."""
    if photo:
        img = '<img class="tf-photo" src="{}" alt="" width="72" height="92">'.format(photo)
    else:
        img = '<div class="tf-photo tf-blank">{}</div>'.format(e(name[:1]))
    kit = ('<img class="tf-kit" src="{}" alt="" width="26" height="26">'.format(shirt)
           if shirt else "")
    return (
        '<div class="tf-face {tone}">'
        '<div class="tf-frame">{img}{kit}</div>'
        '<p class="tf-name">{name}</p>'
        '<p class="tf-meta">{club} &middot; {price:.1f}m</p>'
        "</div>"
    ).format(tone=tone_class, img=img, kit=kit, name=e(name), club=e(club),
             price=price)


def transfer_cards(rows, note):
    """Suggested swaps, drawn as transfers rather than listed as a table.

    A transfer is two faces and a price, so it is drawn as two faces and a
    price. The outgoing player is dimmed and the incoming one is not, the
    money sits on the arrow between them, and the projected gain is the one
    number given any size - everything else is there to justify it."""
    if not rows:
        return ""
    top_gain = max(r["gain"] for r in rows) or 1.0
    cards = []
    for r in rows:
        out_ep = r["out_score"]["total"]
        in_ep = r["in_score"]["total"]
        span = max(out_ep, in_ep) or 1.0
        # Shown as the effect on your bank, not the change in squad value:
        # a cheaper replacement puts money back, so it reads +0.5m.
        bank_delta = -r["spend"]
        money = "free" if abs(bank_delta) < 0.05 else "{:+.1f}m".format(bank_delta)
        money_class = "tf-free" if abs(bank_delta) < 0.05 else (
            "tf-save" if bank_delta > 0 else "tf-cost")
        elite = ""
        if r.get("elite"):
            elite = ('<span class="tf-elite">{:.0f}% of the top 100 own him</span>'
                     .format(r["elite"]["elite"]))
        fixture = "{} ({})".format(
            r["in_score"]["opponent"], "H" if r["in_score"]["home"] else "A")
        cards.append((
            '<li class="tf-card" style="--gain:{gainpct:.0f}%">'
            '<div class="tf-swap">{out}'
            '<div class="tf-mid">'
            '<span class="tf-arrow" aria-hidden="true">'
            '<svg viewBox="0 0 40 16"><path d="M0 8h32M26 2l7 6-7 6" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg></span>'
            '<span class="tf-money {mclass}">{money}</span></div>'
            "{inp}</div>"
            '<div class="tf-numbers">'
            '<div class="tf-ep"><span>{oep:.2f}</span>'
            '<span class="tf-track"><i style="width:{opct:.0f}%"></i></span></div>'
            '<div class="tf-gain">{gain:+.2f}<small>projected points</small></div>'
            '<div class="tf-ep tf-ep-in"><span>{iep:.2f}</span>'
            '<span class="tf-track"><i style="width:{ipct:.0f}%"></i></span></div>'
            "</div>"
            '<p class="tf-foot">{fixture} next &middot; {elite}</p>'
            "</li>"
        ).format(
            gainpct=r["gain"] / top_gain * 100,
            out=_face(r["out_photo"], r["out_shirt"], r["out"].name,
                      r["out"].team, r["out"].price, "tf-out"),
            inp=_face(r["in_photo"], r["in_shirt"], r["in"]["web_name"],
                      r["in_club"], r["price"], "tf-in"),
            mclass=money_class, money=money,
            oep=out_ep, opct=out_ep / span * 100,
            iep=in_ep, ipct=in_ep / span * 100,
            gain=r["gain"], fixture=e(fixture),
            elite=elite or "same position, within budget",
        ))
    return (
        '<section class="card"><div class="card-head"><h2>Suggested transfers</h2>'
        '<span class="sub">{}</span></div>'
        '<div class="card-body"><ul class="tflist">{}</ul></div></section>'.format(
            e(note), "".join(cards)
        )
    )


def _mini_face(photo, shirt, name, tone_class):
    if photo:
        img = '<img class="pr-photo" src="{}" alt="" width="44" height="56">'.format(photo)
    else:
        img = '<div class="pr-photo pr-blank">{}</div>'.format(e(name[:1]))
    kit = ('<img class="pr-kit" src="{}" alt="" width="18" height="18">'.format(shirt)
           if shirt else "")
    return ('<span class="pr-face {tone}"><span class="pr-frame">{img}{kit}</span>'
            '<span class="pr-name">{name}</span></span>').format(
        tone=tone_class, img=img, kit=kit, name=e(name))


def pairing_cards(pairings, note, hit=4):
    """Two-transfer moves, drawn as two swaps under one verdict.

    The combined gain is the headline; the figure after the hit sits beside
    it, because whether a pair is worth doing usually turns on whether you
    are paying for the second transfer. `hit` is the real cost of making two
    transfers given the free ones actually banked - it used to be hardcoded
    at four, which told a manager sitting on two free transfers that a pair
    would cost him points it would not."""
    if not pairings:
        return ""
    free = hit == 0
    cards = []
    for p in pairings:
        legs = "".join(
            '<li class="pr-leg">{out}'
            '<span class="pr-arrow" aria-hidden="true">'
            '<svg viewBox="0 0 28 12"><path d="M0 6h21M16 1.5l5 4.5-5 4.5" '
            'fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg></span>'
            '{inp}<span class="pr-gain">+{gain:.2f}</span></li>'.format(
                out=_mini_face(leg["out_photo"], leg["out_shirt"],
                               leg["out"].name, "pr-out"),
                inp=_mini_face(leg["in_photo"], leg["in_shirt"],
                               leg["in"]["web_name"], "pr-in"),
                gain=leg["gain"],
            )
            for leg in p["legs"]
        )
        after = p["gain"] - hit
        if free:
            verdict = '<span class="pr-yes">Both transfers are free</span>'
        elif after > 0:
            verdict = ('<span class="pr-yes">Still ahead after '
                       "&minus;{} </span>".format(hit))
        else:
            verdict = ('<span class="pr-no">Not worth &minus;{}</span>'
                       .format(hit))
        bank = p["bank_after"]
        cards.append(
            '<li class="pr-card">'
            '<div class="pr-head"><span class="pr-total">+{gain:.2f}'
            '<small>combined</small></span>'
            '<span class="pr-hit">{after:+.2f}<small>{hitlabel}</small></span>'
            '<span class="pr-bank">{bank:.1f}m<small>bank after</small></span></div>'
            '<ul class="pr-legs">{legs}</ul>'
            '<p class="pr-foot">{verdict}</p></li>'.format(
                gain=p["gain"], after=after, bank=bank,
                hitlabel="no hit to pay" if free else f"after &minus;{hit}",
                legs=legs, verdict=verdict,
            )
        )
    return (
        '<section class="card"><div class="card-head"><h2>Transfer pairings</h2>'
        '<span class="sub">{}</span></div>'
        '<div class="card-body"><ul class="prlist">{}</ul></div></section>'.format(
            e(note), "".join(cards)
        )
    )


POS_ORDER = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}


def swap_table(rows, title, note):
    """A whole-squad rebuild as a table: out on the left, in on the right.

    This used to reuse transfer_cards, which draws each swap as two large
    portraits. That works for the three or four suggestions in "Suggested
    transfers" and falls apart at a Wildcard's ten - and because none of
    these rows carry a photo, every one of those portraits rendered as a
    grey square containing the player's first initial, so the section read
    as a wall of enormous letters. Ten moves is a list, not a gallery: one
    row each, positions grouped, columns you can compare straight down.
    """
    if not rows:
        return ""
    rows = sorted(rows, key=lambda r: (POS_ORDER.get(r["out"].pos, 9),
                                       -r["out"].price))
    body, seen_pos = [], None
    for r in rows:
        pos = r["out"].pos
        if pos != seen_pos:
            seen_pos = pos
            body.append(
                '<tr class="sw-group"><th colspan="5" scope="colgroup">'
                '{}</th></tr>'.format(e(pos))
            )
        spend = r["spend"]
        money = "free" if abs(spend) < 0.05 else "{:+.1f}m".format(-spend)
        mcls = "sw-free" if abs(spend) < 0.05 else (
            "sw-save" if spend < 0 else "sw-cost")
        gain = r["gain"]
        gcls = "sw-up" if gain > 0 else ("sw-down" if gain < 0 else "sw-flat")
        body.append(
            '<tr>'
            '<td class="sw-out"><b>{out}</b><span>{oclub} &middot; {oprice:.1f}</span></td>'
            '<td class="sw-arrow" aria-hidden="true">&rarr;</td>'
            '<td class="sw-in"><b>{inn}</b><span>{iclub} &middot; {iprice:.1f}</span></td>'
            '<td class="num {mcls}">{money}</td>'
            '<td class="num {gcls}">{gain:+.2f}</td>'
            "</tr>".format(
                out=e(r["out"].name), oclub=e(r["out"].team),
                oprice=r["out"].price,
                inn=e(r["in"]["web_name"]), iclub=e(r["in_club"]),
                iprice=r["price"], mcls=mcls, money=money,
                gcls=gcls, gain=gain,
            )
        )
    return (
        '<details class="card collapsible swapcard"><summary class="card-head">'
        '<h2>{title}</h2><span class="sub">{note}</span></summary>'
        '<div class="scroll"><table class="swaptbl"><thead><tr>'
        '<th scope="col">Out</th><th scope="col"></th><th scope="col">In</th>'
        '<th scope="col" class="num">Bank</th>'
        '<th scope="col" class="num">Points</th></tr></thead>'
        "<tbody>{body}</tbody></table></div></details>".format(
            title=e(title), note=e(note), body="".join(body))
    )


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


def stat_leaders(groups):
    """Who leads the league on each measure, a few names deep.

    Narrow columns rather than one wide table: these are six separate
    questions, not six columns of one, and side by side they take a fraction
    of the height a table of the same content would."""
    cards = []
    for g in groups:
        if not g["rows"]:
            continue
        items = "".join(
            '<li{cls}><span class="slrank">{i}</span>'
            '<span class="slname">{name}</span>'
            '<span class="slteam">{team}</span>'
            '<span class="slval">{val}</span></li>'.format(
                cls=' class="mine"' if mine else "",
                i=i, name=e(name), team=e(team), val=e(val))
            for i, (name, team, val, mine) in enumerate(g["rows"], 1)
        )
        cards.append(
            '<li class="slcard" style="--accent:{tone}">'
            '<h4><svg viewBox="0 0 24 24" class="slicon" aria-hidden="true">{icon}</svg>'
            "{title}</h4>"
            '<p class="slnote">{note}</p>'
            '<ol class="sllist">{items}</ol></li>'.format(
                tone=g["tone"], icon=STAT_ICONS.get(g["icon"], ""),
                title=e(g["title"]), note=e(g["note"]), items=items,
            )
        )
    if not cards:
        return ""
    return (
        '<section class="card"><div class="card-head"><h2>League leaders</h2>'
        '<span class="sub">Who is topping each measure so far. Your players are '
        "marked.</span></div>"
        '<div class="card-body"><ul class="slwrap">{}</ul></div></section>'.format(
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
