"""Cards for the Planning tab: chips, transfers, captaincy, prices and elite ownership."""

import json

import components
import ticker
import transfers
from analysis import f
from cards_common import e, pos_fixture_pill


def price_row(r):
    """One player's progress toward a price change.

    The bar is |percent| capped at 100, so a full bar means the change is due
    at the next recalculation. Direction is carried by an explicit arrow and
    the sign, not by the bar colour alone."""
    rising = r["pct"] > 0
    # The delta chip carries the direction, so the arrow glyph that used to
    # sit here is gone: one component says "this moved, this way, by this
    # much" everywhere on the page rather than each card inventing its own.
    tone = "var(--good)" if rising else "var(--bad)"
    width = min(100.0, abs(r["pct"]))
    tags = []
    if r["imminent"]:
        tags.append('<span class="tag tag-now">due now</span>')
    if r["owned_by_you"]:
        tags.append('<span class="tag tag-mine">yours</span>')
    net = r["net_transfers"]
    return (
        f'<li class="pw">'
        f'<span class="pw-top">'
        f'<span class="pw-name">{e(r["name"])}'
        f'<span class="pw-meta">{e(r["pos"])} &middot; {e(r["team"])} &middot; '
        f'{r["price"]:.1f}m</span></span>'
        f'<span class="delta {"delta-up" if rising else "delta-down"}">'
        f'{abs(r["pct"]):.0f}%</span>'
        f"</span>"
        f'<span class="pw-bar"><span class="pw-fill" '
        f'style="width:{width:.1f}%;background:{tone}"></span></span>'
        # Two percentages side by side used to say nothing about which was
        # which: 99% next to "+106%" reads as a contradiction until you know
        # the first is where he is now and the second is where he is forecast
        # to be in two days, both on a scale that fires at 100.
        f'<span class="pw-foot">forecast {r["projected"]:+.0f}% in two days '
        f'&middot; net transfers {net:+,} {"".join(tags)}</span>'
        f"</li>"
    )


def price_watch_card(pw):
    if not pw["risers"] and not pw["fallers"]:
        return ""
    risers = "".join(price_row(r) for r in pw["risers"])
    fallers = "".join(price_row(r) for r in pw["fallers"])
    urgent = []
    if pw["your_fallers"]:
        names = ", ".join(r["name"] for r in pw["your_fallers"][:4])
        urgent.append(
            f"<b>{e(names)}</b> in your squad {'are' if len(pw['your_fallers']) > 1 else 'is'} "
            f"losing value. Selling after the drop costs you the difference."
        )
    if pw["rising_not_owned"]:
        soon = [r for r in pw["rising_not_owned"] if r["imminent"]][:4]
        if soon:
            names = ", ".join(r["name"] for r in soon)
            urgent.append(
                f"<b>{e(names)}</b> {'are' if len(soon) > 1 else 'is'} due to rise and "
                f"you do not own {'them' if len(soon) > 1 else 'him'}. Buying now saves the rise."
            )
    banner = (
        f'<div class="pw-alert">{"<br>".join(urgent)}</div>' if urgent else ""
    )
    return (
        '<section class="card">'
        f'<div class="card-head"><h2>Price watch{components.info_btn()}</h2>'
        '<span class="subvis">Both figures are progress towards a price '
        'change, which fires at <b>100%</b>: the big number is where he is '
        'now, the small one is where FPL forecast him in two days. Net '
        'transfers are raw, so a widely-owned player needs far more of them '
        'to move the same distance.</span>'
        '<span class="sub" hidden>A change fires at 100%. Prices update once a day, so this '
        "is only worth anything before it happens. Progress is relative to a "
        "player's own ownership, which is why a small net-transfer figure can "
        "sit above a large one.</span></div>"
        f'<div class="card-body">{banner}'
        '<div class="pw-cols">'
        f'<div><h3 class="pw-h">Rising</h3><ul class="pw-list pw-scroll">{risers}</ul></div>'
        f'<div><h3 class="pw-h">Falling</h3><ul class="pw-list pw-scroll">{fallers}</ul></div>'
        "</div></div></section>"
    )


def scatter(points):
    """Value scatter with switchable axes.

    Drawn in the browser rather than baked into the SVG here: the point of
    swapping axes is to re-scale to whatever pair you choose, and that means
    the ticks, the domain and every position have to be recomputed. Emitting
    the data once and letting a few lines of JavaScript lay it out is far less
    code than generating every combination server-side.

    Your squad is separated from the market by size, a surface-coloured ring
    and a label, not by hue alone - the two mark colours clear CVD separation
    for protanopia but sit in the 6-8 band for tritanopia, where colour needs
    a second channel behind it."""
    if not points:
        return ""
    data = [
        {
            "n": p["name"], "t": p["team"], "p": p["pos"], "mine": p["mine"],
            "price": round(p["price"], 1),
            "xgi90": round(p["xgi90"], 3),
            "points": p["points"],
            "owned": round(p["owned"], 1),
            "minutes": p["minutes"],
            "ppm": round(p["points"] / p["price"], 2) if p["price"] else 0,
        }
        for p in points
    ]
    axes = (
        ("xgi90", "xGI per 90"),
        ("points", "Total points"),
        ("price", "Price (£m)"),
        ("owned", "Ownership %"),
        ("ppm", "Points per £m"),
        ("minutes", "Minutes"),
    )
    opts = lambda sel: "".join(
        f'<option value="{k}"{" selected" if k == sel else ""}>{e(label)}</option>'
        for k, label in axes
    )
    return (
        '<section class="card">'
        f'<div class="card-head"><h2>Value scatter{components.info_btn()}</h2>'
        '<span class="sub" hidden>Pick any two measures. Hover or click a dot to see the '
        "player. Your squad and the biggest outliers are always labelled.</span></div>"
        '<div class="card-body">'
        '<div class="chartfilter" role="group" aria-label="Chart controls">'
        '<label class="axpick">Y <select class="axis" data-axis="y">'
        f"{opts('xgi90')}</select></label>"
        '<label class="axpick">X <select class="axis" data-axis="x">'
        f"{opts('price')}</select></label>"
        '<span class="spacer"></span>'
        '<div class="tabbar" role="group" aria-label="Position">'
        '<button class="chip" data-pos="ALL" aria-pressed="true">All</button>'
        '<button class="chip" data-pos="DEF" aria-pressed="false">Defenders</button>'
        '<button class="chip" data-pos="MID" aria-pressed="false">Midfielders</button>'
        '<button class="chip" data-pos="FWD" aria-pressed="false">Forwards</button>'
        "</div></div>"
        '<div class="scroll"><svg class="scatter" viewBox="0 0 1040 520" '
        'role="img" aria-label="Scatter plot of player metrics"></svg></div>'
        '<p class="readout" aria-live="polite">Hover or click any dot to identify the player.</p>'
        '<p class="legend"><span class="key mkt"></span>Every player with 60+ minutes'
        '<span class="key mine"></span>Your squad'
        '<span class="key outlier"></span>Furthest from the norm</p>'
        f'<script type="application/json" class="scatter-data">{json.dumps(data)}</script>'
        "</div></section>"
    )


def elite_card(res, ctx):
    """What proven managers own, against what everyone owns."""
    if not res:
        return ""
    if res.get("insufficient"):
        return (
            '<section class="card">'
            f'<div class="card-head"><h2>What proven managers own{components.info_btn()}</h2></div>'
            '<div class="card-body"><p class="tnote">Elite ownership needs '
            "~10 gameweeks before the top of the table means anything - too "
            "few managers with a proven top-100k season are in the current "
            "top ranks yet.</p></div></section>"
        )
    caveat = (
        f" Read from {res['managers']} proven managers, so each figure "
        f"carries about &plusmn;{res['moe']:.1f} points at 95% confidence."
    )

    def table(rows, cols_note):
        body = []
        for r in rows:
            cls = ' class="me"' if r["mine"] else ""
            edge_tone = "var(--success)" if r["edge"] > 0 else "var(--error)"
            body.append(
                f"<tr{cls}><td><b>{e(r['name'])}</b></td>"
                f"<td>{e(r['pos'])}</td><td>{e(r['team'])}</td>"
                f'<td class="num">{r["price"]:.1f}</td>'
                f'<td class="num" data-v="{r["elite"]}">{r["elite"]:.0f}%</td>'
                f'<td class="num" data-v="{r["overall"]}">{r["overall"]:.0f}%</td>'
                f'<td class="num" data-v="{r["edge"]}" style="color:{edge_tone}">'
                f'<b>{r["edge"]:+.0f}</b></td></tr>'
            )
        return (
            f'<p class="tnote">{cols_note}</p>'
            '<div class="scroll"><table data-sortable><thead><tr>'
            '<th scope="col" class="sortable">Player</th>'
            '<th scope="col">Pos</th><th scope="col">Club</th>'
            '<th scope="col" class="num sortable">Price</th>'
            '<th scope="col" class="num sortable">Elite</th>'
            '<th scope="col" class="num sortable">Everyone</th>'
            '<th scope="col" class="num sortable">Edge</th>'
            f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        )

    parts = [table(res["most_owned"], "Most owned by proven managers.")]
    if res["elite_edge"]:
        parts.append(table(
            res["elite_edge"],
            "Owned far more by proven managers than by the crowd - and you do not own them.",
        ))
    if res["against"]:
        parts.append(table(
            res["against"],
            "You own these; proven managers largely do not.",
        ))
    return (
        '<section class="card">'
        f'<div class="card-head"><h2>What proven managers own{components.info_btn()}</h2>'
        f'<span class="sub" hidden>{e(res["label"])}, read from the global FPL league at '
        f"gameweek {res['event']}.{caveat}</span></div>"
        f'<div class="card-body">{"".join(parts)}</div></section>'
    )


def leader_groups(ctx, squad_ids, depth=4, min_minutes=45):
    """Top few players on each measure, mixing FPL's numbers with Opta's.

    Expected goals conceded is the odd one out and is ranked ascending: for a
    defence, less is the achievement."""
    pool = [
        el for el in ctx.players.values()
        if el.get("minutes", 0) >= min_minutes
    ]
    mine = set(squad_ids)

    def _rank(key, fmt, ascending, opta, positions):
        rows = []
        for el in pool:
            if positions and ctx.pos(el) not in positions:
                continue
            raw = (el.get("_pulse") or {}).get(key) if opta else el.get(key)
            value = f(raw)
            if raw is None or (not opta and value == 0 and not ascending):
                continue
            if opta and not raw:
                continue
            rows.append((value, el))
        rows.sort(key=lambda x: (x[0] if ascending else -x[0]))
        return [
            (el["web_name"], ctx.team_name(el["team"]), fmt.format(v),
             el["id"] in mine)
            for v, el in rows[:depth]
        ]

    def build(title, note, icon, tone, key, fmt="{:.2f}", ascending=False,
              opta=False, positions=None):
        return {
            "title": title, "note": note, "icon": icon, "tone": tone,
            "rows": _rank(key, fmt, ascending, opta, positions),
        }

    def build_pair(title, note, icon, tone, primary_key, secondary_key):
        # One player per row, ranked on the primary measure, with a second
        # measure of the same family shown alongside rather than as a card
        # of its own - "how many big chances" and "how many chances overall"
        # are the same question asked at two thresholds, and a big chance is
        # a subset of a chance, so the pair is one player's answer, not two
        # separate leaderboards that happen to share a topic.
        # The secondary is the wider measure the primary is a subset of, so a
        # secondary below the primary is not a small number - it is a missing
        # one. Opta serves the two halves as separate paginated requests and
        # one can come back short on its own, and "3 big chances of 0 created"
        # is worse than saying nothing.
        rows = []
        for el in pool:
            ps = el.get("_pulse") or {}
            primary = ps.get(primary_key)
            if not primary:
                continue
            secondary = ps.get(secondary_key) or 0
            rows.append((primary, secondary if secondary >= primary else None, el))
        rows.sort(key=lambda x: (-x[0], -(x[1] or 0)))
        return {
            "title": title, "note": note, "icon": icon, "tone": tone,
            "pair": True,
            "rows": [
                (el["web_name"], ctx.team_name(el["team"]), primary, secondary,
                 el["id"] in mine)
                for primary, secondary, el in rows[:depth]
            ],
        }

    # Six cards used to carry six unrelated hues, which meant colour never
    # carried information across this row - a card's tone told you nothing
    # you couldn't already get from its icon. One hue per role instead: ink
    # for the four attacking measures, premium teal for the one defensive
    # card that flips the ranking (xGC), attention amber for DefCon.
    groups = [
        build("Expected goals", "xG this season", "ball", "var(--ink)",
              "expected_goals"),
        build("Expected assists", "xA this season", "key", "var(--ink)",
              "expected_assists"),
        build("Goal involvement", "xG plus xA", "spark", "var(--ink)",
              "expected_goal_involvements"),
        build_pair(
            "Big chances created",
            "The big figure is big chances - a clear opening. Beside it, "
            "every chance created, of which a big chance is a subset",
            "run", "var(--ink)", "big_chance_created", "total_att_assist",
        ),
        # Named as a season total, because Scout ranks the same idea per 90
        # and the two orders disagree. Unlabelled, a reader moving between
        # the tabs gets two different "best defence" answers and no way to
        # tell which question either was answering. A total here is the right
        # one: this list is about who has actually banked a season's solidity.
        build("Fewest goals expected against",
              "xGC totalled this season - defenders and keepers. Scout ranks "
              "the same idea per 90",
              "shield", "var(--accent-ink)", "expected_goals_conceded", ascending=True,
              positions=("GKP", "DEF")),
        build("Defensive contributions", "Tackles, recoveries and blocks banked this season",
              "shield", "var(--accent-ink)", "defensive_contribution", fmt="{:.0f}"),
    ]
    return [g for g in groups if g["rows"]]


CONFIDENCE_LABEL = {"strong": "Strong", "watch": "Worth watching",
                    "flexible": "Timing flexible"}


def _mini_shirt_card(pid, pos, team_id, team_name, name, price, ctx, badges,
                     shirts, fx_html="", incoming=False, known=True):
    """One shirt card for a compact pitch/bench view - the same `.pl`
    component the Squad tab pitch uses, but built from whatever identifies
    a player rather than requiring a full PlayerReport, since a proposed
    incoming man has no match history to build one from. `incoming` adds a
    distinct outline and an IN tag, for a squad view that mixes players
    actually owned with ones only being suggested. `known` is False when
    the player dialog has no payload for this id (a suggested player who
    is not in the manager's own squad) - those cards render without the
    clickable attributes rather than opening a dialog that silently does
    nothing."""
    shirt = shirts.get((team_id, pos == "GKP"))
    uri = shirt or badges.get(team_id)
    crest = (
        f'<img class="kit" src="{uri}" alt="{e(team_name)}">' if shirt
        else f'<img class="crestimg" src="{uri}" alt="{e(team_name)}">' if uri
        else f'<span class="letters">{e(team_name)}</span>'
    )
    tag = ('<span class="pl-in-tag" title="Suggested incoming">IN</span>'
           if incoming else "")
    cls = "pl pk pl-incoming" if incoming else "pl pk"
    title = f"{name} - {pos}, {team_name}, {price:.1f}m"
    fx = f'<div class="pk-fx">{fx_html}</div>' if fx_html else ""
    clickable = f'data-player="{pid}" role="button" tabindex="0" ' if known else ""
    return (
        f'<div class="{cls}" {clickable}title="{e(title)}">'
        f'{tag}<div class="crest">{crest}</div>'
        f'<div class="nm">{e(name)}</div>{fx}</div>'
    )


def _fixture_pill_for(team_name, pos, proj, market, next_gw):
    rows = ticker._rows_for(team_name, proj, market, next_gw, 1)
    if not rows:
        return ""
    r = rows[0]
    return pos_fixture_pill(pos, r["opp"], r["home"], r["cs"], r["xg"])


def _report_row(r):
    return (r.element["id"], r.pos, r.element["team"], r.team, r.name, r.price)


def _pool_row(p, ctx):
    el = ctx.players[p["id"]]
    return (p["id"], p["pos"], el["team"], p["club"], el["web_name"], p["price"])


def mini_pitch(xi_rows, bench_rows, ctx, badges, shirts, incoming_ids=frozenset(),
               known_ids=None):
    """A much smaller version of the Squad tab pitch - shirts and names
    only, no stats footer - for a before/after comparison where two full
    squads need to sit side by side without either one dominating the
    card. Starting XI grouped by position on the pitch, bench below in its
    own strip, the same split the real FPL app shows - not all fifteen
    lumped into position rows with no start/bench distinction. `xi_rows`
    and `bench_rows` are each a list of (id, pos, club_id, club_name, name,
    price) tuples, the common shape _report_row and _pool_row reduce a
    PlayerReport or a squadbuilder pool entry to, so this does not need to
    care which kind of squad it was given. Bench cards run cheapest to
    priciest left to right, matching how the Wildcard bench itself is now
    chosen (see squadbuilder.best_squad)."""
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    by_pos = {1: [], 2: [], 3: [], 4: []}
    for row in xi_rows:
        by_pos[order.get(row[1], 4)].append(row)
    out = ['<div class="pitch mini">' + components.PITCH_MARKS]
    for k in (1, 2, 3, 4):
        if not by_pos[k]:
            continue
        cards = "".join(
            _mini_shirt_card(pid, pos, team_id, team_name, name, price,
                             ctx, badges, shirts, incoming=pid in incoming_ids,
                             known=known_ids is None or pid in known_ids)
            for pid, pos, team_id, team_name, name, price in by_pos[k]
        )
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    bench_cards = "".join(
        _mini_shirt_card(pid, pos, team_id, team_name, name, price,
                         ctx, badges, shirts, incoming=pid in incoming_ids,
                         known=known_ids is None or pid in known_ids)
        for pid, pos, team_id, team_name, name, price
        in sorted(bench_rows, key=lambda row: row[5])
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{bench_cards}</div></div>'
    )
    return "".join(out)


def wildcard_section(wc, xi_reports, bench_reports, ctx, badges, shirts):
    """The proposed full-squad rebuild as two small pitches, not a table of
    price deltas - "would I actually want this squad" is a look-at-the-
    shirts question. Now above, Proposed below, with a distinct outline
    and an IN tag on whichever names in the proposed squad are not already
    owned - the eye only needs to find the outlined shirts to see what a
    Wildcard here would actually change, rather than reading fifteen rows
    of a table to work it out."""
    if not wc or not wc.get("ideal_xi"):
        return ""
    before_xi = [_report_row(r) for r in xi_reports]
    before_bench = [_report_row(r) for r in bench_reports]
    after_xi = [_pool_row(p, ctx) for p in wc["ideal_xi"]]
    after_bench = [_pool_row(p, ctx) for p in wc["ideal_bench"]]
    incoming_ids = wc.get("incoming_ids") or set()
    after_known_ids = {row[0] for row in after_xi + after_bench} - incoming_ids
    start, weeks = wc["gw_window"]
    stats_html = components.wc_stats_block(wc.get("before"), wc.get("after"))
    return (
        '<details class="card collapsible swapcard"><summary class="card-head">'
        f'<h2>Wildcard rebuild{components.info_btn()}</h2>'
        f'<span class="sub" hidden>The full squad this would become, scored '
        f'across GW{start}-{start + weeks - 1}. Outlined shirts with an IN '
        f'tag are not already owned.</span></summary>'
        f'<div class="card-body">{stats_html}'
        '<div class="wcpitches">'
        f'<div class="wcpitch"><h4>Now</h4>'
        f'{mini_pitch(before_xi, before_bench, ctx, badges, shirts)}</div>'
        f'<div class="wcpitch"><h4>Proposed</h4>'
        f'{mini_pitch(after_xi, after_bench, ctx, badges, shirts, incoming_ids, after_known_ids)}</div>'
        "</div></div></details>"
    )


def bench_boost_pitch(bb, bench_reports, ctx, badges, shirts, proj, market,
                      next_gw):
    """The four names actually proposed for the bench on Bench Boost week,
    laid out as the same bench strip the Squad tab pitch already draws -
    not a table of price deltas, since "is this a bench worth boosting" is
    a look-at-the-shirts-and-fixtures question, not a spreadsheet one. A
    suggested incoming swap replaces the outgoing man's slot outright, so
    this shows the bench as it WOULD be, not the one sitting there today -
    with a distinct outline and an IN tag on whichever slots changed, so a
    glance tells you which of the four are new."""
    if not bb:
        return ""
    out_by_id = {t["out"].element["id"]: t
                for t in (bb.get("transfers") or [])}
    cards = []
    for r in bench_reports:
        t = out_by_id.get(r.element["id"])
        if t:
            el = t["in"]
            team_name = ctx.team_name(el["team"])
            cards.append(_mini_shirt_card(
                el["id"], ctx.pos(el), el["team"], team_name,
                el["web_name"], el["now_cost"] / 10.0, ctx, badges, shirts,
                fx_html=_fixture_pill_for(team_name, ctx.pos(el), proj,
                                          market, next_gw),
                incoming=True, known=False))
        else:
            cards.append(_mini_shirt_card(
                r.element["id"], r.pos, r.element["team"], r.team, r.name,
                r.price, ctx, badges, shirts,
                fx_html=_fixture_pill_for(r.team, r.pos, proj, market, next_gw),
                incoming=False))
    note = ("Moves that would improve that specific week, not this one."
           if bb["transfers"] else
           "Your bench as it stands - nothing here is worth changing "
           "for that week.")
    return (
        '<details class="card collapsible swapcard"><summary class="card-head">'
        f'<h2>Bench Boost rebuild, GW{bb["gw"]}{components.info_btn()}</h2>'
        f'<span class="sub" hidden>{e(note)}</span></summary>'
        f'<div class="card-body"><div class="benchstrip bbpitch">'
        f'<div class="row">{"".join(cards)}</div></div></div></details>'
    )


def _cp_card(label, used_gw, body_html, level=None):
    if used_gw:
        return (
            f'<div class="cp used"><p class="cp-label">{e(label)}</p>'
            f'<p class="cp-used-tag">Already used, GW{used_gw}</p></div>'
        )
    tone = f" cp-{level}" if level else ""
    return (f'<div class="cp{tone}"><p class="cp-label">{e(label)}</p>'
            f'{body_html}</div>')


def chip_planner_card(fh, tc, bb, wc, used, xi, bench, ctx, badges, shirts,
                      proj, market, next_gw):
    """The four chip recommendations, one card each - target gameweek,
    the number behind it, and a plain-language confidence read."""
    if not (fh or tc or bb or wc):
        return ""

    def conf_pill(level):
        return (f'<span class="cp-conf cp-conf-{level}">'
               f'{e(CONFIDENCE_LABEL.get(level, level))}</span>')

    def week_strip(series, best_gw, unit):
        """Every week in the chip window as one small bar each.

        A chip card that names a single gameweek cannot say whether that week
        is a spike worth holding for or the flat top of a run where any week
        would do - and those call for opposite decisions. The strip is the
        cheapest thing that answers it: if one bar towers, wait for it; if
        they are level, play it whenever it suits you.
        """
        if not series or len(series) < 2:
            return ""
        top = max(v for _g, v in series) or 1.0
        low = min(v for _g, v in series)
        bars = "".join(
            '<span class="cpw{sel}" style="--h:{h:.0f}%" '
            'title="GW{gw}: {v:.1f} {unit}"><i></i><em>{gw}</em></span>'.format(
                sel=" cpw-on" if gw == best_gw else "",
                h=max(6.0, v / top * 100), gw=gw, v=v, unit=e(unit))
            for gw, v in series
        )
        flat = (top - low) < 0.12 * top
        read = ("every week in the window is within a point or two of this "
                "one - timing is yours"
                if flat else
                "clearly the best week in the window")
        return (f'<div class="cpweeks" aria-hidden="true">{bars}</div>'
                f'<p class="cpweeks-read">{read}</p>')

    cards = []

    if fh:
        pt = fh["points_team"]
        body = (
            f'<p class="cp-gw">GW{fh["gw"]}</p>'
            f'<p class="cp-reason">Best possible XI projects {pt["ideal_value"]:.1f} pts '
            f'against your XI\'s {pt["ours_value"]:.1f} that week - a gap of '
            f'{fh["gap"]:.1f}.</p>'
            f'{week_strip(fh.get("series"), fh["gw"], "pt gap")}'
            f'{conf_pill(fh["confidence"])}'
        )
        cards.append(_cp_card("Free Hit", used.get("freehit"), body,
                              fh["confidence"]))

    if tc:
        body = (
            f'<p class="cp-gw">GW{tc["gw"]}</p>'
            f'<p class="cp-reason">Captain {e(tc["player"].name)} for '
            f'{tc["ep"]:.1f} pts ({tc["ep"] * 2:.1f} with the armband, '
            f'{tc["ep"]:.1f} more than a normal captaincy).</p>'
            f'{week_strip(tc.get("series"), tc["gw"], "pts")}'
            f'{conf_pill(tc["confidence"])}'
        )
        cards.append(_cp_card("Triple Captain", used.get("3xc"), body,
                              tc["confidence"]))

    if bb:
        body = (
            f'<p class="cp-gw">GW{bb["gw"]}</p>'
            f'<p class="cp-reason">Bench projects {bb["ep"]:.1f} pts that week'
            f'{" - if your bench stays as it is." if not bb["transfers"] else "."}</p>'
            f'{week_strip(bb.get("series"), bb["gw"], "pts")}'
            f'{conf_pill(bb["confidence"])}'
        )
        cards.append(_cp_card("Bench Boost", used.get("bboost"), body,
                              bb["confidence"]))

    if wc:
        start, weeks = wc["gw_window"]
        body = (
            f'<p class="cp-gw">GW{start}-{start + weeks - 1}</p>'
            f'<p class="cp-reason">{wc["gap"]:.1f} pts of upside available '
            f'over the window.</p>'
            f'{conf_pill(wc["confidence"])}'
        )
        cards.append(_cp_card("Wildcard", used.get("wildcard"), body,
                              wc["confidence"]))

    # The grid above is the compact per-chip summary only; each chip's
    # actual squad change is its own collapsed card below it - a rebuild
    # you are not doing this week does not deserve a screen of its own
    # every visit.
    extra = []
    if bb:
        extra.append(bench_boost_pitch(bb, bench, ctx, badges, shirts,
                                       proj, market, next_gw))
    if wc:
        extra.append(wildcard_section(wc, xi, bench, ctx, badges, shirts))

    return (
        f'<section class="card"><div class="card-head"><h2>Chip planner{components.info_btn()}</h2>'
        '<span class="sub" hidden>Best gameweek for each chip in the current half, '
        'scored from the same projections as the rest of the page.</span></div>'
        f'<div class="card-body"><ul class="cplist">{"".join(cards)}</ul></div></section>'
        f'{"".join(extra)}'
    )


TICK_SVG = ('<svg class="ic" viewBox="0 0 16 16" aria-hidden="true">'
            '<path d="M3 8.5 6.4 12 13 4.6" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')

HOME_SVG = ('<svg class="venue-icon" viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 11.5 12 4l8 7.5V19a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1Z" '
            'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>')
AWAY_SVG = ('<svg class="venue-icon" viewBox="0 0 24 24" aria-hidden="true">'
            '<rect x="4" y="8" width="16" height="11" rx="2" fill="none" '
            'stroke="currentColor" stroke-width="1.7"/>'
            '<path d="M9 8V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" fill="none" '
            'stroke="currentColor" stroke-width="1.7"/></svg>')

POS_LABEL = {"GKP": "Goalkeeper", "DEF": "Defenders",
             "MID": "Midfielders", "FWD": "Forwards"}
POS_SEQ = ("GKP", "DEF", "MID", "FWD")


def best_xi_card(pt, ctx, squad_ids, next_gw):
    """The highest-projecting eleven available in the whole game for the
    coming week, against the eleven actually owned.

    Sorted into positions rather than one ranked list, because the useful
    question is not "who scores most" - it is "where is my team behind",
    and that only reads position by position. Owned players are ticked
    rather than pulled out into their own group, so the gap between the
    two teams is a count you can see rather than a number to be trusted.

    No budget cap, but the real 3-per-club squad limit still applies - the
    literal highest-scoring valid formation in the game (see
    chips.literal_best_xi), not the best one affordable at the manager's
    own squad value."""
    if not pt or not pt.get("ideal_xi"):
        return ""
    xi = pt["ideal_xi"]
    owned_n = sum(1 for p in xi if p["id"] in squad_ids)
    top = max(p["value"] for p in xi) or 1.0

    groups = []
    for pos in POS_SEQ:
        men = sorted((p for p in xi if p["pos"] == pos),
                     key=lambda p: -p["value"])
        if not men:
            continue
        rows = []
        for p in men:
            el = ctx.players.get(p["id"])
            name = el["web_name"] if el else "?"
            mine = p["id"] in squad_ids
            rows.append(
                f'<li class="bxi-row{" is-mine" if mine else ""}">'
                f'<span class="bxi-mark" aria-hidden="true">'
                f'{TICK_SVG if mine else ""}</span>'
                f'<span class="bxi-name">{e(name)}</span>'
                f'<span class="bxi-club">{e(p["club"])}</span>'
                f'<span class="bxi-bar"><i style="width:'
                f'{p["value"] / top * 100:.0f}%"></i></span>'
                f'<span class="bxi-ep num">{p["value"]:.1f}</span></li>'
            )
        groups.append(
            f'<div class="bxi-group"><h4>{e(POS_LABEL[pos])}</h4>'
            f'<ul>{"".join(rows)}</ul></div>'
        )

    gap = pt["gap"]
    # What this eleven costs. The card is unbudgeted by design - it answers
    # "where is my team behind", not "what should I buy" - but printing a
    # "gap" with no price made an unreachable number read as a target, and
    # eleven names at this quality routinely cost more than a fifteen-man
    # squad is allowed. The price is the caveat, said in money rather than in
    # a hidden note nobody opens.
    cost = sum((ctx.players[p["id"]]["now_cost"] / 10.0)
               for p in xi if p["id"] in ctx.players)
    if gap < 0.5:
        read = ("Your eleven is already within half a point of the best "
                "possible one in the game. There is nothing to chase here.")
    else:
        read = (f"Your eleven projects {pt['ours_value']:.1f}, so this one is "
                f"{gap:.1f} ahead across the "
                f"{11 - owned_n} name{'s' if 11 - owned_n != 1 else ''} you "
                f"do not own. Read it as where you are behind, not as a "
                f"target - it is picked with no budget at all.")

    return (
        '<section class="card bxicard"><div class="card-head">'
        f'<h2>Highest predicted points XI{components.info_btn()}</h2>'
        f'<span class="sub" hidden>The literal highest-scoring valid eleven in the '
        f'game for gameweek {next_gw} - no budget, but the real 3-per-club '
        f'limit and formation rules still apply. The Free Hit card is the '
        f'budgeted version of the same question.</span></div>'
        '<div class="card-body">'
        '<div class="bxi-head">'
        f'<div class="bxi-big"><span class="num">{pt["ideal_value"]:.1f}</span>'
        f'<small>projected, best XI</small></div>'
        f'<p class="bxi-own">{TICK_SVG}<b>{owned_n} of 11</b> already yours</p>'
        f'<p class="bxi-cost">Costs <b>{cost:.1f}m</b> for eleven players, '
        f'against a 100.0m budget for fifteen &mdash; not a squad you can '
        f'build</p>'
        f'<p class="bxi-read">{e(read)}</p></div>'
        f'<div class="bxi-grid">{"".join(groups)}</div>'
        "</div></section>"
    )


def kneejerk_card(kj, gw):
    """The player who hauled last week and is not in the squad.

    Deliberately named for the impulse rather than dressed up as a
    recommendation, and deliberately loud - it is the one card on the page
    arguing with the reader rather than informing them. Last week's points
    are the single number here with no predictive weight whatsoever, so
    they are printed at full size and then immediately answered by the
    projection for the coming week and the best alternative at the same
    money. If the case survives that, it was never a knee-jerk."""
    if not kj:
        return ""
    ep = kj["ep"]
    next_gw_ep = kj["next_gw_ep"]
    rival = kj["rival"]
    funder = kj["funder"]

    funder_pair = kj.get("funder_pair")
    if ep is None:
        verdict, tone = "No fixture priced for him yet this week.", "warn"
    elif rival and rival["ep"] > ep:
        margin = rival["ep"] - ep
        # The tone follows the size of the margin. A card styled as a warning
        # to report a 0.95-point edge across five gameweeks is shouting about
        # a coin flip, and a reader who notices that once stops reading the
        # card when it has something real to say. SELL_MARGIN is the bar the
        # Buy column already holds a raw-total comparison to, so "meaningfully
        # more" means the same thing on both cards.
        decisive = margin >= transfers.SELL_MARGIN
        verdict = (f'{rival["name"]} at {rival["price"]:.1f}m projects '
                   f'{margin:+.2f} more over the next '
                   f'{transfers.TRANSFER_HORIZON_WEEKS} gameweeks for the '
                   f'same slot.'
                   + ("" if decisive else
                      " That is close enough to be noise - this is a "
                      "preference, not a case against him."))
        tone = "bad" if decisive else "warn"
    elif not funder and funder_pair:
        verdict = (
            f"One transfer will not reach him, but selling "
            f"{e(funder_pair['primary'].name)} and "
            f"{e(funder_pair['second'].name)} together would, backfilled "
            f"by {e(funder_pair['replacement']['web_name'])} at "
            f"{funder_pair['replacement']['now_cost'] / 10.0:.1f}m - see "
            f"Suggested pairs below."
        )
        tone = "warn"
    elif not funder:
        verdict = (f"You cannot reach him: nobody you own at {kj['pos']} "
                   f"frees up {kj['price']:.1f}m, even in a pair.")
        tone = "warn"
    else:
        verdict = (f"He also holds up on the projection, and selling "
                   f"{e(funder.name)} would pay for him.")
        tone = "good"

    # Named, because it is the knee-jerk target's fixture and it used to sit
    # unattributed at the end of a sentence about a different player - it read
    # as the alternative's fixture, which is the opposite of what it means.
    fixture = ""
    if kj["opponent"]:
        fixture = (f'<span class="kj-fx">{e(kj["name"])} plays '
                   f'{"vs" if kj["home"] else "at"} '
                   f'{e(kj["opponent"])}</span>')
    ep_txt = f"{next_gw_ep:.1f}" if next_gw_ep is not None else "&mdash;"
    ep5_txt = f"{ep:.1f}" if ep is not None else "&mdash;"

    return (
        f'<section class="card kjcard kj-{tone}">'
        '<div class="kj-tag">The knee-jerk</div>'
        '<div class="kj-body">'
        f'<p class="kj-lead">You did not own <b>{e(kj["name"])}</b>, and he '
        f'scored</p>'
        f'<p class="kj-score"><span class="num">{kj["points"]}</span>'
        f'<small>in gameweek {gw}</small></p>'
        '<dl class="kj-facts">'
        f'<div><dt>Price</dt><dd class="num">{kj["price"]:.1f}m</dd></div>'
        f'<div><dt>Owned</dt><dd class="num">{kj["owned"]:.1f}%</dd></div>'
        f'<div><dt>Bought this week</dt><dd class="num">{kj["bought"]:,}</dd></div>'
        f'<div><dt>Next GW</dt><dd class="num">{ep_txt}</dd></div>'
        f'<div><dt>Next {transfers.TRANSFER_HORIZON_WEEKS} GW</dt><dd class="num">{ep5_txt}</dd></div>'
        "</dl>"
        f'<p class="kj-verdict">{verdict} {fixture}</p>'
        "</div></section>"
    )


VERDICT_COLS = [
    ("buy", "Buy", "good", "Not yours, reachable, projects highest."),
    ("sell", "Sell", "bad", "A named replacement projects meaningfully more."),
    ("keep", "Keep", "accent", "Nothing above wants to move him."),
    ("avoid", "Avoid", "warn", "Being bought hard; a cheaper man projects more."),
]


def verdict_board_card(vb, next_gw):
    """Buy, Sell, Keep, Avoid as four columns with four different rules.

    See transfers.verdict_board for what each one actually means - the
    important part is that they are four questions rather than one ranking
    cut into quarters, and Avoid is the only column reading the transfer
    market rather than the model."""
    if not vb or not any(vb.get(k) for k, _l, _t, _s in VERDICT_COLS):
        return ""
    cols = []
    for key, label, tone, sub in VERDICT_COLS:
        rows = vb.get(key) or []
        if not rows:
            items = '<li class="vb-none">Nothing this week.</li>'
        else:
            items = "".join(
                f'<li><span class="vb-top"><b>{e(r["name"])}</b>'
                f'<span class="vb-ep num">{r["ep"]:.1f}</span></span>'
                f'<span class="vb-sub">{e(r["club"])} &middot; '
                f'{r["price"]:.1f}m &middot; {e(r["note"])}</span></li>'
                for r in rows
            )
        cols.append(
            f'<div class="vb-col vb-{tone}"><h4>{e(label)}</h4>'
            f'<p class="vb-rule">{e(sub)}</p><ul>{items}</ul></div>'
        )
    return (
        '<section class="card vbcard"><div class="card-head">'
        f'<h2>Buy, sell, keep, avoid{components.info_btn()}</h2>'
        f'<span class="sub" hidden>Four different questions, not one ranking split '
        f'four ways. The figure beside each name is total projected points '
        f'across the next {transfers.TRANSFER_HORIZON_WEEKS} gameweeks - not '
        f'gameweek {next_gw} alone - plus a small nudge for recent form and '
        f'underlying numbers, which is why it reads much higher than a '
        f'single week\'s score. The opponent named in each note is still '
        f'just the very next fixture, for context.</span></div>'
        f'<div class="card-body vb-grid">{"".join(cols)}</div></section>'
    )


def captaincy_card(cm):
    """The Captaincy Decision Matrix - a radar chart overlaying this
    gameweek's top expected-points XI candidates across form, fixture
    strength, goal threat, start certainty, and set-piece responsibilities,
    so the shapes can be compared directly. Home/away is a small venue icon
    by each name rather than a sixth axis - see captaincy.py for why, and
    for what each remaining axis actually measures and where the numbers
    come from."""
    if not cm:
        return ""
    # candidates are ranked by projected points, highest first - see
    # captaincy.matrix.
    top = cm["candidates"][0]
    legend = "".join(
        f'<li class="radar-leg" data-i="{i}" tabindex="0" role="button" '
        f'aria-pressed="false">'
        f'<span class="radar-swatch radar-c{i}"></span>'
        f'<span class="radar-leg-text"><span class="radar-leg-name">'
        f'{HOME_SVG if c["home"] else AWAY_SVG}{e(c["player"])}</span>'
        f'<span class="radar-leg-sub">vs {e(c["opponent"])} '
        f'({"H" if c["home"] else "A"}) &middot; {c["ep_total"]:.1f} pts proj</span></span>'
        "</li>"
        for i, c in enumerate(cm["candidates"])
    )
    data = {
        "metrics": [{"key": k, "label": lbl, "unit": u} for k, lbl, u in cm["metrics"]],
        "candidates": cm["candidates"],
    }
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Captaincy decision matrix{components.info_btn()}</h2>'
        f'<span class="sub" hidden>This gameweek\'s top armband candidates from your XI, '
        f'overlaid across five axes. Each axis is scaled to that metric\'s '
        f'own real range (0.5x-2.0x for the fixture multiplier, 0-100% for '
        f'start certainty, and so on - see captaincy.py) - not to whoever '
        f'else is shown - so the edge of the chart means the same thing '
        f'every week: genuinely one of the best fixtures or returns anyone '
        f'gets, not just the best of this shortlist. Two candidates from the '
        f'same club can also share an axis exactly (same team, same '
        f'fixture), which is a genuine tie, not missing data. Ranked by '
        f'projected points - <b>{e(top["player"])}</b> is on top this week - '
        f'the shape shows why. Click a name for the full breakdown.</span></div>'
        '<div class="card-body cap-layout">'
        f'<div class="cap-side"><ul class="radar-legend">{legend}</ul>'
        '<p class="radar-readout" aria-live="polite">Hover a shape or a dot for its value.</p></div>'
        # Padded well past CX/CY/R/TEXT_R in captaincy.js (currently
        # 210/195/130/174) on every side - a long label like "Fixture (xG
        # mult)" or a pinned callout's value line grows outward from an
        # anchor already near the edge of the plain drawing area, and gets
        # clipped against the SVG's own edge (an SVG root defaults to
        # overflow:hidden) rather than the card if there is no margin left
        # for it. Change CX/CY/R/TEXT_R together with this viewBox, not
        # separately - they size the same canvas.
        '<div class="cap-chart scroll"><svg class="radar" viewBox="-100 -10 640 400" '
        'role="img" aria-label="Captaincy decision matrix radar chart"></svg>'
        "</div>"
        f'<script type="application/json" class="captaincy-data">{json.dumps(data)}</script>'
        "</div></section>"
    )
