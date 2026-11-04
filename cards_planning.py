"""Cards for the Planning tab (chips, prices), plus the captain comparison
shown on Squad and the proven-manager ownership shown on Scout."""


import components
import ticker
from cards_common import e, icon, pos_fixture_pill, script_json


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
        f'<span class="pw-foot">forecast {r["projected"]:+.0f}% '
        f'&middot; net {net:+,} {"".join(tags)}</span>'
        f"</li>"
    )


def price_watch_card(pw):
    if not pw["risers"] and not pw["fallers"]:
        return ""
    risers = "".join(price_row(r) for r in pw["risers"])
    fallers = "".join(price_row(r) for r in pw["fallers"])
    # No banner naming your fallers: each row already carries a "yours" tag.
    return (
        '<section class="card">'
        f'<div class="card-head"><h2>Price watch{components.info_btn()}</h2>'
        '<span class="sub" hidden>Progress to a price change, which fires at '
        '100%; the small figure is the two-day forecast.</span></div>'
        f'<div class="card-body">'
        '<div class="pw-cols">'
        f'<div><h3 class="pw-h">Rising</h3><ul class="pw-list pw-scroll">{risers}</ul></div>'
        f'<div><h3 class="pw-h">Falling</h3><ul class="pw-list pw-scroll">{fallers}</ul></div>'
        "</div></div></section>"
    )


def elite_card(res, ctx):
    """What proven managers own, against what everyone owns. Shown on the
    Scout tab, and not at all until enough proven managers are in the top
    ranks: a card that only says it has nothing to show is noise."""
    if not res or res.get("insufficient"):
        return ""
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


CONFIDENCE_LABEL = {"strong": "Strong", "watch": "Worth watching",
                    "flexible": "Timing flexible"}


def _mini_shirt_card(pid, pos, team_id, team_name, name, price, ctx, badges,
                     shirts, fx_html="", incoming=False):
    """One shirt card for a compact pitch/bench view - the same `.pl`
    component the Squad tab pitch uses, but built from whatever identifies
    a player rather than requiring a full PlayerReport, since a proposed
    incoming man has no match history to build one from. `incoming` adds a
    distinct outline and an IN tag, for a squad view that mixes players
    actually owned with ones only being suggested."""
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
    return (
        f'<div class="{cls}" data-player="{pid}" role="button" tabindex="0" title="{e(title)}">'
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


def mini_pitch(xi_rows, bench_rows, ctx, badges, shirts, incoming_ids=frozenset()):
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
                             ctx, badges, shirts, incoming=pid in incoming_ids)
            for pid, pos, team_id, team_name, name, price in by_pos[k]
        )
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    bench_cards = "".join(
        _mini_shirt_card(pid, pos, team_id, team_name, name, price,
                         ctx, badges, shirts, incoming=pid in incoming_ids)
        for pid, pos, team_id, team_name, name, price
        in sorted(bench_rows, key=lambda row: row[5])
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{bench_cards}</div></div>'
    )
    return "".join(out)


def wildcard_section(wc, xi_reports, bench_reports, ctx, badges, shirts, plan_xp=None):
    """The proposed full-squad rebuild as two small pitches, not a table of
    price deltas - "would I actually want this squad" is a look-at-the-
    shirts question. Now above, Proposed below, with a distinct outline
    and an IN tag on whichever names in the proposed squad are not already
    owned - the eye only needs to find the outlined shirts to see what a
    Wildcard here would actually change, rather than reading fifteen rows
    of a table to work it out.

    `plan_xp` is (now, proposed): both squads held unchanged over the plan's
    window and scored by the plan's own scorer. When given it replaces the
    chip model's xP row, so this card and the plan above it never price the
    same window in two currencies."""
    if not wc or not wc.get("ideal_xi"):
        return ""
    before_xi = [_report_row(r) for r in xi_reports]
    before_bench = [_report_row(r) for r in bench_reports]
    after_xi = [_pool_row(p, ctx) for p in wc["ideal_xi"]]
    after_bench = [_pool_row(p, ctx) for p in wc["ideal_bench"]]
    incoming_ids = wc.get("incoming_ids") or set()
    start, weeks = wc["gw_window"]
    before, after = wc.get("before"), wc.get("after")
    if plan_xp and before and after:
        before, after = {**before, "xp": plan_xp[0]}, {**after, "xp": plan_xp[1]}
    stats_html = components.wc_stats_block(before, after)
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
        f'{mini_pitch(after_xi, after_bench, ctx, badges, shirts, incoming_ids)}</div>'
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
                                          market, bb["gw"]),
                incoming=True))
        else:
            cards.append(_mini_shirt_card(
                r.element["id"], r.pos, r.element["team"], r.team, r.name,
                r.price, ctx, badges, shirts,
                fx_html=_fixture_pill_for(r.team, r.pos, proj, market, bb["gw"]),
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
    key = {"Free Hit": "freehit", "Triple Captain": "3xc", "Bench Boost": "bboost", "Wildcard": "wildcard"}[label]
    ico = {"freehit": "free-hit", "3xc": "triple-captain", "bboost": "bench-boost", "wildcard": "wildcard"}[key]
    # The chip coin: green when the chip has a strong week, purple when it
    # is available, struck through (not just greyed) once used.
    if used_gw:
        return (
            f'<div class="cp used"><span class="chip-coin chip-used">{icon(ico)}</span>'
            f'<p class="cp-label">{e(label)}</p>'
            f'<p class="cp-used-tag">Already used, GW{used_gw}</p></div>'
        )
    tone = f" cp-{level}" if level else ""
    return (f'<div class="cp{tone}" id="chip-{key}" tabindex="-1"><span class="chip-coin">{icon(ico)}</span>'
            f'<p class="cp-label">{e(label)}</p>{body_html}</div>')


def _plan_bench_boost(plan):
    """Bench Boost as the transfer plan times it: the week it plays it, or
    the later week it holds it for. None when the plan does not model chips.

    The plan's week wins over this card's own scan of today's bench: the
    plan can swap a keeper who never plays for one who does before the week
    comes, and two different Bench Boost weeks on one page is a
    contradiction."""
    if not plan or not plan.get("chips_modelled"):
        return None
    series = [(w["gw"], w["bench_points"]) for w in plan["weeks"]]
    played = next((w for w in plan["weeks"] if w["chip"] == "bboost"), None)
    if played:
        return {"gw": played["gw"], "ep": played["bench_points"], "series": series,
                "week": played, "held": False}
    held = next((c for c in plan.get("held_chips", []) if c["key"] == "bboost"), None)
    if held:
        return {"gw": held["gw"], "ep": held["gain"], "series": series,
                "week": None, "held": True}
    return None


def _plan_bench_pitch(week, ctx, badges, shirts):
    if not week:
        return ""
    cards = []
    for pid in week["bench"]:
        el = ctx.players[pid]
        fx = week["fixtures"].get(pid)
        fx_html = (f'<span class="plan-fx">{e(fx["opp"])} ({"H" if fx["home"] else "A"})</span>'
                   if fx else '<span class="plan-fx">blank</span>')
        cards.append(_mini_shirt_card(
            pid, ctx.pos(el), el["team"], ctx.team_name(el["team"]), el["web_name"],
            el["now_cost"] / 10.0, ctx, badges, shirts, fx_html=fx_html,
            incoming=pid in week["bought"]))
    return (
        '<details class="card collapsible swapcard"><summary class="card-head">'
        f'<h2>Bench Boost bench, GW{week["gw"]}{components.info_btn()}</h2>'
        '<span class="sub" hidden>The bench the transfer plan boosts, after its '
        'moves. IN marks a player the plan signs before then.</span></summary>'
        f'<div class="card-body"><div class="benchstrip bbpitch">'
        f'<div class="row">{"".join(cards)}</div></div></div></details>'
    )


def chip_planner_card(fh, tc, bb, wc, used, xi, bench, ctx, badges, shirts,
                      proj, market, next_gw, plan=None):
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
        bars = "".join(
            '<span class="cpw{sel}" style="--h:{h:.0f}%" '
            'title="GW{gw}: {v:.1f} {unit}"><i></i><em>{gw}</em></span>'.format(
                sel=" cpw-on" if gw == best_gw else "",
                h=max(6.0, v / top * 100), gw=gw, v=v, unit=e(unit))
            for gw, v in series
        )
        return f'<div class="cpweeks" aria-hidden="true">{bars}</div>'

    cards = []

    if fh:
        pt = fh["points_team"]
        body = (
            f'<p class="cp-gw">GW{fh["gw"]}</p>'
            f'<p class="cp-reason tnum"><b>{pt["ideal_value"]:.1f}</b> v yours '
            f'{pt["ours_value"]:.1f} xP</p>'
            f'{week_strip(fh.get("series"), fh["gw"], "pt gap")}'
            f'{conf_pill(fh["confidence"])}'
        )
        cards.append(_cp_card("Free Hit", used.get("freehit"), body,
                              fh["confidence"]))

    if tc:
        body = (
            f'<p class="cp-gw">GW{tc["gw"]}</p>'
            f'<p class="cp-reason tnum">{e(tc["player"].name)} &middot; '
            f'<b>+{tc["ep"]:.1f}</b> xP</p>'
            f'{week_strip(tc.get("series"), tc["gw"], "pts")}'
            f'{conf_pill(tc["confidence"])}'
        )
        cards.append(_cp_card("Triple Captain", used.get("3xc"), body,
                              tc["confidence"]))

    plan_bb = _plan_bench_boost(plan)
    if plan_bb and plan_bb["held"]:
        body = (
            f'<p class="cp-gw">Hold: GW{plan_bb["gw"]}</p>'
            f'<p class="cp-reason tnum"><b>+{plan_bb["ep"]:.1f}</b> xP &middot; '
            f'after the plan</p>'
        )
        cards.append(_cp_card("Bench Boost", used.get("bboost"), body, None))
    elif plan_bb:
        body = (
            f'<p class="cp-gw">GW{plan_bb["gw"]}</p>'
            f'<p class="cp-reason tnum">Bench <b>{plan_bb["ep"]:.1f}</b> xP &middot; in the plan</p>'
            f'{week_strip(plan_bb["series"], plan_bb["gw"], "pts")}'
        )
        cards.append(_cp_card("Bench Boost", used.get("bboost"), body, None))
    elif bb:
        body = (
            f'<p class="cp-gw">GW{bb["gw"]}</p>'
            f'<p class="cp-reason tnum">Bench <b>{bb["ep"]:.1f}</b> xP</p>'
            f'{week_strip(bb.get("series"), bb["gw"], "pts")}'
            f'{conf_pill(bb["confidence"])}'
        )
        cards.append(_cp_card("Bench Boost", used.get("bboost"), body,
                              bb["confidence"]))

    # The Wildcard is judged against the plan, on the plan's scorer: its own
    # chip model scored the rebuild against standing still (+70 where the
    # plan already found +45 for the same weeks), so a big-looking gap could
    # be mostly what the plan's ordinary transfers were getting anyway.
    wc_xp = (plan or {}).get("compare", {}).get("wildcard")
    if wc:
        start, weeks = wc["gw_window"]
        if wc_xp is not None:
            versus = wc_xp - plan["total"]
            level = "strong" if versus >= plan["chip_margin"] else None
            body = (f'<p class="cp-gw">GW{start}-{start + weeks - 1}</p>'
                    f'<p class="cp-reason tnum"><b>{versus:+.1f}</b> xP v the plan</p>')
        else:
            level = wc["confidence"]
            body = (f'<p class="cp-gw">GW{start}-{start + weeks - 1}</p>'
                    f'<p class="cp-reason tnum"><b>+{wc["gap"]:.1f}</b> xP v no moves</p>'
                    f'{conf_pill(wc["confidence"])}')
        cards.append(_cp_card("Wildcard", used.get("wildcard"), body, level))

    # The grid above is the compact per-chip summary only; each chip's
    # actual squad change is its own collapsed card below it - a rebuild
    # you are not doing this week does not deserve a screen of its own
    # every visit.
    extra = []
    if plan_bb:
        extra.append(_plan_bench_pitch(plan_bb["week"], ctx, badges, shirts))
    elif bb:
        extra.append(bench_boost_pitch(bb, bench, ctx, badges, shirts,
                                       proj, market, next_gw))
    if wc:
        extra.append(wildcard_section(wc, xi, bench, ctx, badges, shirts,
                                      (plan["compare"].get("now"), wc_xp)
                                      if wc_xp is not None and plan["compare"].get("now") is not None
                                      else None))

    return (
        f'<section class="card" id="chip-planner" tabindex="-1"><div class="card-head"><h2>Chip planner{components.info_btn()}</h2>'
        '<span class="sub" hidden>Best gameweek for each chip in the current half, '
        'scored from the same projections as the rest of the page.</span></div>'
        f'<div class="card-body"><ul class="cplist">{"".join(cards)}</ul></div></section>'
        f'{"".join(extra)}'
    )


HOME_SVG = ('<svg class="venue-icon" viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 11.5 12 4l8 7.5V19a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1Z" '
            'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>')
AWAY_SVG = ('<svg class="venue-icon" viewBox="0 0 24 24" aria-hidden="true">'
            '<rect x="4" y="8" width="16" height="11" rx="2" fill="none" '
            'stroke="currentColor" stroke-width="1.7"/>'
            '<path d="M9 8V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" fill="none" '
            'stroke="currentColor" stroke-width="1.7"/></svg>')

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
    # Shut under the captain card on the Squad tab: the card above already
    # names the pick, so the comparison opens only when asked for.
    return (
        '<details class="card collapsible" id="captaincy"><summary class="card-head">'
        f'<h2>Captain options &middot; {len(cm["candidates"])}{components.info_btn()}</h2>'
        '<span class="sub" hidden>Each axis uses that metric\'s full range, '
        'not this shortlist\'s.</span></summary>'
        '<div class="card-body cap-layout">'
        f'<div class="cap-side"><ul class="radar-legend">{legend}</ul>'
        '<p class="radar-readout" aria-live="polite"></p></div>'
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
        f'<script type="application/json" class="captaincy-data">{script_json(data)}</script>'
        "</div></details>"
    )
