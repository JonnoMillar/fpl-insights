"""Cards for the Mini-league tab: standings, ownership, template and rivals."""

import math

import analysis
import components
import fplapi
import transfers
from analysis import f
from cards_common import e, meter, script_json


def donut(pct, label, center, sub, tone="var(--accent)"):
    """A single part-of-whole figure.

    Doughnuts are poor at comparing magnitudes, which is why nothing else in
    this page uses one. They are fine for exactly this: one share, read on its
    own, with the number printed in the middle so the angle is never the only
    way to read it."""
    r = 34
    circ = 2 * math.pi * r
    dash = max(0.0, min(1.0, pct / 100.0)) * circ
    return (
        f'<svg class="donut" viewBox="0 0 90 90" role="img" '
        f'aria-label="{e(label)}">'
        f'<circle class="dtrack" cx="45" cy="45" r="{r}"/>'
        f'<circle class="dval" cx="45" cy="45" r="{r}" stroke="{tone}" '
        f'stroke-dasharray="{dash:.1f} {circ - dash:.1f}" '
        f'transform="rotate(-90 45 45)"/>'
        f'<text class="dnum" x="45" y="{43 if sub else 49}" text-anchor="middle">{e(center)}</text>'
        f'<text class="dsub" x="45" y="57" text-anchor="middle">{e(sub)}</text>'
        "</svg>"
    )


def template_xi(own, by_name, ctx):
    """The most-started legal eleven in the mini-league.

    Not simply the eleven most-owned players: that could be six defenders and
    no keeper. It is also not raw squad ownership, which was the actual bug
    here - a cheap enabler bought purely to free up budget and left on the
    bench everywhere ends up "owned" by half the league without ever being
    part of anyone's eleven. Ranking by how often a player is actually
    started fixes that without a hand-picked price cutoff to call something
    an "enabler". Every legal shape is tried - one keeper, three to five
    defenders, two to five midfielders, one to three forwards, eleven in all -
    and the one with the most total starts wins, which is what "the
    template" actually means. Ties go to the pricier player: when two
    players are started equally often, the more expensive one is the one
    actually earning that XI slot rather than sitting in it as a value pick."""
    n = len(by_name)
    if not own or not n:
        return None
    pools = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for pid, rec in own.items():
        el = ctx.players.get(pid)
        if not el:
            continue
        pools[ctx.pos(el)].append((len(rec["starters"]), el, rec))
    for key in pools:
        pools[key].sort(key=lambda x: (-x[0], -x[1]["now_cost"], -x[1]["total_points"]))

    best, best_total = None, -1
    for d in range(3, 6):
        for m in range(2, 6):
            f_ = 11 - 1 - d - m
            if not 1 <= f_ <= 3:
                continue
            picks = {"GKP": pools["GKP"][:1], "DEF": pools["DEF"][:d],
                     "MID": pools["MID"][:m], "FWD": pools["FWD"][:f_]}
            if any(len(v) < need for v, need in
                   ((picks["GKP"], 1), (picks["DEF"], d),
                    (picks["MID"], m), (picks["FWD"], f_))):
                continue
            total = sum(x[0] for group in picks.values() for x in group)
            if total > best_total:
                best_total, best = total, (picks, f"{d}-{m}-{f_}")
    if not best:
        return None
    picks, shape = best
    return {"picks": picks, "shape": shape, "managers": n}


def template_pitch(tpl, ctx, shirts, my_name, known_ids=frozenset()):
    """The template eleven, laid out on a pitch.

    `known_ids` are the ids the player dialog has a payload for (the
    manager's own squad) - most of a league template is other managers'
    picks, so only those cards get the clickable attributes."""
    if not tpl:
        return ""
    n = tpl["managers"]
    rows = []
    for key in ("GKP", "DEF", "MID", "FWD"):
        cards = []
        for count, el, rec in tpl["picks"][key]:
            shirt = shirts.get((el["team"], key == "GKP"))
            crest = (
                f'<img class="kit" src="{shirt}" alt="{e(ctx.team_name(el["team"]))}">'
                if shirt else f'<span class="letters">{e(ctx.team_name(el["team"]))}</span>'
            )
            mine = my_name in rec["starters"]
            pct = 100.0 * count / n
            clickable = (
                f'data-player="{el["id"]}" role="button" tabindex="0" '
                if el["id"] in known_ids else ""
            )
            cards.append(
                f'<div class="pl{" tpl-mine" if mine else ""}" '
                f'{clickable}'
                f'title="{e(el["web_name"])} - started by {count} of {n}'
                f'{" including you" if mine else ", not by you"}">'
                f'<div class="crest">{crest}</div>'
                f'<div class="nm">{e(el["web_name"])}</div>'
                f'<div class="sc tnum"><div class="p">{count}/{n}</div>'
                f'<div class="x">{pct:.0f}%</div></div></div>'
            )
        if cards:
            rows.append(f'<div class="row">{"".join(cards)}</div>')
    owned_by_you = sum(
        1 for group in tpl["picks"].values() for _c, _el, rec in group
        if my_name in rec["starters"]
    )
    # How much of this eleven is actually a consensus. It is the most-started
    # legal XI, so it always fills all eleven slots - including, early in a
    # season, positions where three of eight managers is the top of the pile.
    # A 38% pick is not a template pick, and printing it beside a 100% one
    # with no distinction is how "the template" comes to mean nothing.
    majority = sum(
        1 for group in tpl["picks"].values() for count, _el, _rec in group
        if count * 2 > n
    )
    return (
        f'<section class="card"><div class="card-head"><h2>League template{components.info_btn()}</h2>'
        f'<span class="subvis"><b>{majority} of 11</b> held by over half</span>'
        f'<span class="sub" hidden>The most-started legal eleven across {n} managers, '
        f'in a {tpl["shape"]}. You have {owned_by_you} of them &mdash; the rest '
        "is where your rank moves.</span></div>"
        f'<div class="pitch tplpitch">{components.PITCH_MARKS}'
        f'{"".join(rows)}</div></section>'
    )


# A watchlist or differential is a player few FPL managers hold. The league
# is eight people: "nobody here owns him" says more about who they happen to
# have picked than about how rare he is.
DIFFERENTIAL_COUNT = 3
WATCH_MAX_OWNED_PCT = 10.0


def differential_watchlist(own, ctx, proj, market, baselines, next_gw, squad_ids,
                           limit=6):
    """Players performing well that few FPL managers own (under
    WATCH_MAX_OWNED_PCT), and that are not already in your squad. Rivals may
    hold them; that is shown, not filtered on.

    Scored with transfers.case_score, the same several-week, form-and-
    underlying-numbers logic the Planning tab's transfer suggestions use -
    "performing well" means the same thing here as everywhere else that
    phrase appears on this page, not a separate reading of the numbers."""
    if not own:
        return []
    priors = transfers.positional_priors(ctx)
    rows = []
    for el in ctx.players.values():
        pid = el["id"]
        if (pid in squad_ids or not transfers._eligible(el, ctx)
                or f(el.get("selected_by_percent")) >= WATCH_MAX_OWNED_PCT):
            continue
        s = transfers.case_score(el, ctx, proj, next_gw, market, baselines, priors)
        if not s or s["total"] <= 0:
            continue
        rows.append({
            "id": pid, "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "price": el["now_cost"] / 10.0,
            "ep": s["total"], "opponent": s["opponent"], "home": s["home"],
            "owned_pct": f(el.get("selected_by_percent")),
            "league": len(own[pid]["owners"]) if pid in own else 0,
            "duties": components.duty_badges(el),
        })
    rows.sort(key=lambda r: -r["ep"])
    # At most two from one club. Unfiltered, a good fixture swept the list:
    # four of six were the same Arsenal defence with the same opponent, which
    # is one bet written out four times, not six options. A watchlist whose
    # rows all win or all lose together is worse than a shorter one.
    out, per_club = [], {}
    for r in rows:
        if per_club.get(r["club"], 0) >= 2:
            continue
        per_club[r["club"]] = per_club.get(r["club"], 0) + 1
        out.append(r)
        if len(out) >= limit:
            break
    return out


def differential_watchlist_card(rows, photos, weeks, managers=0):
    """The Your differentials card, run the other direction and forward-
    looking: not what you already hold that's rare, but what's rare and
    still worth going and getting."""
    if not rows:
        return ""
    cards = []
    for r in rows:
        el_photo = photos.get(r["id"])
        face = (
            f'<img class="df-photo" src="{el_photo}" alt="" width="84" height="106">'
            if el_photo else f'<div class="df-photo df-blank">{e(r["name"][:1])}</div>'
        )
        fixture = f'{"vs" if r["home"] else "at"} {e(r["opponent"])}'
        cards.append(
            f'<li class="df-card"><div class="df-frame">{face}{r["duties"]}</div>'
            f'<div class="df-body"><p class="df-name">{e(r["name"])}</p>'
            f'<p class="df-meta">{e(r["pos"])} &middot; '
            f'{e(r["club"])} &middot; {r["price"]:.1f}m</p>'
            f'<dl class="df-stats">'
            f'<div><dt>{weeks}-week</dt><dd>{r["ep"]:.1f}</dd></div>'
            f'<div><dt>Next</dt><dd>{fixture}</dd></div>'
            f'<div><dt>Owned, all FPL</dt><dd>{r["owned_pct"]:.1f}%</dd></div>'
            f'<div><dt>League</dt><dd>{r["league"]}/{managers}</dd></div>'
            f"</dl></div></li>"
        )
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Differential watchlist{components.info_btn()}</h2>'
        '<span class="sub" hidden>Under '
        f'{WATCH_MAX_OWNED_PCT:.0f}% owned across FPL, scored the same way as '
        f'every transfer suggestion on the Planning tab, over the next {weeks} '
        f'gameweeks. At most two per club.</span></div>'
        f'<div class="card-body"><ul class="dflist">{"".join(cards)}</ul></div>'
        "</section>"
    )


def your_differentials(own, ctx, my_name, limit=DIFFERENTIAL_COUNT):
    """The `limit` players in your squad the fewest FPL managers own.

    Ranked by overall ownership (selected_by_percent), not by whether the rest
    of the league holds him: a minimum-price enabler nobody else in an
    eight-team league happens to carry is not a differential, so anyone priced
    as one (transfers.is_cheap, the planner's definition) is skipped."""
    if not own or not my_name:
        return []
    caps = transfers.price_caps(ctx)
    rows = []
    for pid, rec in own.items():
        el = ctx.players.get(pid)
        if (my_name not in rec["owners"] or not el
                or transfers.is_cheap(el["now_cost"] / 10.0, ctx.pos(el), caps)):
            continue
        rows.append((f(el.get("selected_by_percent")), -el["total_points"],
                     pid, len(rec["owners"])))
    rows.sort()
    return [(pid, owners) for _pct, _pts, pid, owners in rows[:limit]]


def differential_card(own, by_name, ctx, my_name, photos):
    """Your three least-owned non-enablers, each with a portrait and its
    numbers; league ownership is the secondary figure."""
    n = len(by_name)
    mine = your_differentials(own, ctx, my_name)
    if not mine:
        return ""
    cards = []
    for pid, owners in mine:
        el = ctx.players[pid]
        photo = photos.get(pid)
        face = (
            f'<img class="df-photo" src="{photo}" alt="" width="84" height="106">'
            if photo else f'<div class="df-photo df-blank">{e(el["web_name"][:1])}</div>'
        )
        cards.append(
            f'<li class="df-card">{face}'
            f'<div class="df-body"><p class="df-name">{e(el["web_name"])}</p>'
            f'<p class="df-meta">{e(ctx.pos(el))} &middot; '
            f'{e(ctx.team_name(el["team"]))} &middot; {el["now_cost"] / 10:.1f}m</p>'
            f'<dl class="df-stats">'
            f'<div><dt>Owned, all FPL</dt>'
            f'<dd>{f(el["selected_by_percent"]):.1f}%</dd></div>'
            f'<div><dt>League</dt><dd>{owners}/{n}</dd></div>'
            f'<div><dt>Points</dt><dd>{el["total_points"]}</dd></div>'
            f'<div><dt>xGI</dt><dd>{f(el["expected_goal_involvements"]):.2f}</dd></div>'
            f"</dl></div></li>"
        )
    return (
        '<section class="card"><div class="card-head"><h2>Your differentials</h2></div>'
        f'<div class="card-body"><ul class="dflist">{"".join(cards)}</ul></div>'
        "</section>"
    )


def rival_returns(own, by_name, ctx, my_name, squad_ids, limit=5):
    """Players who scored for the rest of this league last week, and not
    for you - ranked by the points themselves, highest first.

    An earlier version ranked by points times how many rivals started him,
    on the reasoning that a haul only costs you ground in proportion to how
    much of the league held it. In practice that produced a top-to-bottom
    order that did not read as "who hurt me" at a glance - a 6-pointer
    could outrank a 13-pointer - so the simpler, checkable number leads
    instead. How many rivals held him is still shown, just as context
    rather than the sort key."""
    if not own or not my_name:
        return []
    rows = []
    for pid, rec in own.items():
        if pid in squad_ids:
            continue
        starters = [n for n in rec["starters"] if n != my_name]
        if not starters:
            continue
        el = ctx.players.get(pid)
        if not el:
            continue
        pts = el.get("event_points") or 0
        if pts <= 0:
            continue
        caps = [n for n in rec["captains"] if n != my_name]
        rows.append({
            "id": pid, "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "points": pts,
            "starters": len(starters), "captains": len(caps),
        })
    rows.sort(key=lambda r: -r["points"])
    return rows[:limit]


def rival_returns_window(rows, ctx, my_name, squad_ids, gw, weeks=3, limit=5,
                         ttl=fplapi.DEFAULT_TTL):
    """rival_returns, summed over the last `weeks` gameweeks rather than
    the one just gone - a single bad week can be an anomaly; a player who
    keeps doing it to you over a month is a pattern.

    The current gameweek's rival squads are already fetched elsewhere in
    build(), but an earlier gameweek is a different squad for each of them
    and needs its own picks request - this refetches those specifically,
    bounded to the same rivals (`rows[:limit]`) already shown everywhere
    else on the mini-league tab, so the added cost is `weeks` extra picks
    calls per existing rival, not any new managers. Each gameweek's player
    points come from one shared event_live call covering everyone, rather
    than one request per player."""
    if not rows or not my_name:
        return []
    totals = {}
    start = max(1, gw - weeks + 1)
    for week in range(start, gw + 1):
        try:
            live = fplapi.event_live(week, ttl=ttl)
        except fplapi.FplError:
            continue
        points_by_pid = {
            e["id"]: e.get("stats", {}).get("total_points", 0)
            for e in live.get("elements", [])
        }
        by_name_week = {}
        for r in rows[:limit]:
            try:
                by_name_week[r["entry_name"]] = analysis.squad_for(r["entry"], week, ctx)
            except fplapi.FplError:
                continue
        own_week = analysis.league_ownership(by_name_week)
        for pid, rec in own_week.items():
            if pid in squad_ids:
                continue
            starters = [n for n in rec["starters"] if n != my_name]
            if not starters:
                continue
            pts = points_by_pid.get(pid, 0)
            if pts <= 0:
                continue
            caps = [n for n in rec["captains"] if n != my_name]
            agg = totals.setdefault(
                pid, {"points": 0, "weeks": 0, "starters": 0, "captains": 0})
            agg["points"] += pts
            agg["weeks"] += 1
            agg["starters"] = max(agg["starters"], len(starters))
            agg["captains"] += len(caps)

    out = []
    for pid, agg in totals.items():
        el = ctx.players.get(pid)
        if not el:
            continue
        out.append({
            "id": pid, "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "points": agg["points"],
            "starters": agg["starters"], "captains": agg["captains"],
            "weeks": agg["weeks"],
        })
    # Points scored, weighted by how much of the league actually held him.
    # A 12-pointer one rival started cost you ground on one manager; a
    # 9-pointer five of them started cost you ground on five, and in a
    # mini-league that is the larger loss. Ranked on points still - that is
    # the checkable number - but a lone punt no longer outranks a name half
    # the league had unless it genuinely out-scored it by enough.
    out.sort(key=lambda r: (-(r["points"] * (1 + r["starters"])), -r["points"]))
    return out[:limit]


def _rivals_list(rows, rivals, photos, weeks_note=False):
    if not rows:
        return '<p class="lc-clear">Nobody else in the league returned against you.</p>'
    top = max(r["points"] for r in rows) or 1
    items = []
    for r in rows:
        photo = photos.get(r["id"])
        face = (
            f'<img class="rv-photo" src="{photo}" alt="" width="44" height="56">'
            if photo
            else f'<span class="rv-photo rv-blank">{e(r["name"][:1])}</span>'
        )
        bits = [e(f'started by {r["starters"]} of {rivals}')]
        if r["captains"]:
            bits.append(e(f'{r["captains"]} captained him'))
        if weeks_note:
            bits.append(e(f'returned in {r["weeks"]} of the weeks shown'))
        items.append(
            f'<li class="rv-row">{face}'
            f'<span class="rv-who"><b>{e(r["name"])}</b>'
            f'<span>{e(r["pos"])} &middot; {e(r["club"])}</span></span>'
            f'<span class="rv-pts num">{r["points"]}</span>'
            f'<span class="rv-track"><i style="width:'
            f'{r["points"] / top * 100:.0f}%"></i></span>'
            f'<span class="rv-note">{" &middot; ".join(bits)}</span></li>'
        )
    return f'<ul class="rvlist">{"".join(items)}</ul>'


def rivals_card(rows, window_rows, rivals, photos, weeks=3):
    """The counterpart to Your differentials, from the other direction.

    Not called "reverse differentials" - the thing worth naming here is the
    consequence, not the jargon. These are points that went onto other
    people's scores and not yours, which in a mini-league is the only kind
    of points that actually moves you.

    Two views, toggled rather than shown one below the other: the week
    just gone, and the last few weeks summed - a single bad week can be a
    fluke, a name that keeps showing up over a month is a pattern. Both
    rank by points scored, highest first; the bar is that same number, not
    a separate "damage" figure - the previous version ranked and drew the
    bar by points times how many rivals held him, which read as
    unpredictable (a 6-pointer could sit above a 13-pointer) rather than
    as "who hurt me"."""
    if not rows and not window_rows:
        return ""
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Scoring against you</h2>'
        '</div>'
        '<div class="card-body">'
        '<div class="rvtabs tabbar" role="tablist" aria-label="Time range">'
        '<button class="rvtab" role="tab" aria-selected="true" data-rv="now">'
        "This week</button>"
        f'<button class="rvtab" role="tab" aria-selected="false" data-rv="window">'
        f"Last {weeks} weeks</button>"
        "</div>"
        f'<div class="rvpanel" data-rv="now">{_rivals_list(rows, rivals, photos)}</div>'
        f'<div class="rvpanel" data-rv="window" hidden>'
        f'{_rivals_list(window_rows, rivals, photos, weeks_note=True)}</div>'
        "</div></section>"
    )


def league_position_series(histories, my_name):
    """Every manager's league position and total points, gameweek by
    gameweek - built entirely from the entry histories already fetched for
    the Chips used table, so this costs no extra requests.

    Position is rank by THIS LEAGUE's total points at each gameweek, not
    each manager's FPL-wide overall rank - "your position" in a
    mini-league context means position among these rivals, not among the
    ten million entries FPL actually has."""
    if not histories:
        return None
    by_gw = {}
    for name, h in histories.items():
        for row in h.get("current", []):
            by_gw.setdefault(row["event"], {})[name] = row["total_points"]
    if not by_gw:
        return None
    gws = sorted(by_gw.keys())
    points = {name: [] for name in histories}
    position = {name: [] for name in histories}
    for gw in gws:
        totals = by_gw[gw]
        ranked = sorted(totals.items(), key=lambda x: -x[1])
        rank_by_name = {name: i + 1 for i, (name, _pts) in enumerate(ranked)}
        for name in histories:
            points[name].append(totals.get(name))
            position[name].append(rank_by_name.get(name))
    series = [
        {"name": name, "mine": name == my_name,
         "points": points[name], "position": position[name]}
        for name in histories
    ]
    return {"gws": gws, "managers": len(histories), "series": series}


# Below this many gameweeks the position chart is not a chart. Eight lines
# over three points is a knot: nobody has moved far enough for a trend to
# exist, every line crosses every other, and the reader gets less out of it
# than out of the eight numbers it is drawn from. The card holds itself back
# until there is a season to plot.
LP_MIN_GWS = 5


def league_position_card(data):
    """Position and total points across the season, one line per manager -
    the line chart the league table itself can only show one frame of."""
    if not data or len(data["series"]) < 2:
        return ""
    if len(data["gws"]) < LP_MIN_GWS:
        return (
            '<section class="card"><div class="card-head">'
            '<h2>League position over time</h2></div>'
            '<div class="card-body"><p class="dfempty">'
            f'Appears after GW{data["gws"][0] + LP_MIN_GWS - 1}.'
            "</p></div></section>"
        )
    legend = "".join(
        '<li class="lpleg{mine}" data-i="{i}" tabindex="0">'
        '<span class="lpswatch" data-i="{i}"></span>{name}</li>'.format(
            mine=" lp-mine" if s["mine"] else "", i=i, name=e(s["name"]))
        for i, s in enumerate(data["series"])
    )
    return (
        '<section class="card"><div class="card-head">'
        '<h2>League position over time</h2></div>'
        '<div class="card-body">'
        '<div class="lptoggle tabbar" role="group" aria-label="Y axis">'
        '<button class="lpbtn" data-y="position" aria-pressed="true">Position</button>'
        '<button class="lpbtn" data-y="points" aria-pressed="false">Points</button>'
        "</div>"
        '<div class="scroll"><svg class="lpchart" viewBox="0 0 1040 460" '
        'role="img" aria-label="League position over time"></svg></div>'
        f'<ul class="lplegend">{legend}</ul>'
        f'<script type="application/json" class="lpchart-data">{script_json(data)}</script>'
        "</div></section>"
    )


CHIP_LABEL = {
    "3xc": "Triple Captain", "bboost": "Bench Boost",
    "freehit": "Free Hit", "wildcard": "Wildcard",
    "manager": "Assistant Manager",
}


def league_table(rows, squads, ctx, me):
    xgis = [analysis.squad_underlying(p, ctx)["xgi"] for p in squads.values()]
    maxx = max(xgis + [0.01])
    # This gameweek's high and low score, and each row's movement since last
    # week - nuggets the raw numbers already carry but the table never
    # pointed at. Skipped when everyone's level, which is common in GW1.
    gw_scores = [r["event_total"] for r in rows]
    best_gw, worst_gw = max(gw_scores), min(gw_scores)
    show_gw_tags = best_gw != worst_gw
    body = []
    for r in rows:
        picks = squads.get(r["entry"])
        chip = bench = hits = "-"
        xgi = 0.0
        cap = "-"
        if picks:
            chip = CHIP_LABEL.get(picks.get("active_chip"),
                                  picks.get("active_chip") or "-")
            eh = picks.get("entry_history", {})
            bench = eh.get("points_on_bench", 0)
            hits = eh.get("event_transfers_cost", 0)
            xgi = analysis.squad_underlying(picks, ctx)["xgi"]
            cid = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
            if cid and cid in ctx.players:
                cap = ctx.players[cid]["web_name"]
        cls = ' class="me"' if me and r["entry"] == me else ""
        move = (r["last_rank"] - r["rank"]) if r.get("last_rank") else None
        if move is None:
            move_html = ""
        elif move > 0:
            move_html = (f' <span class="delta delta-up" '
                         f'title="Up {move} since last gameweek">{move}</span>')
        elif move < 0:
            move_html = (f' <span class="delta delta-down" '
                         f'title="Down {abs(move)} since last gameweek">{abs(move)}</span>')
        else:
            move_html = (' <span class="delta delta-flat" '
                         'title="Unchanged since last gameweek">-</span>')
        gw_tag = ""
        if show_gw_tags and r["event_total"] == best_gw:
            gw_tag = ' <span class="good-pill" title="Highest score this gameweek">Top</span>'
        elif show_gw_tags and r["event_total"] == worst_gw:
            gw_tag = ' <span class="bad-pill" title="Lowest score this gameweek">Low</span>'
        body.append(
            f"<tr{cls}>"
            f'<td class="num" data-v="{r["rank"]}">{r["rank"]}{move_html}</td>'
            f'<td data-v="{e(r["entry_name"])}"><b>{e(r["entry_name"])}</b><span class="league-manager">{e(r["player_name"])}</span></td>'
            f'<td class="num"><b>{r["total"]}</b></td>'
            f'<td class="num" data-v="{r["event_total"]}">{r["event_total"]}{gw_tag}</td>'
            f"<td>{e(cap)}</td>"
            f"<td>{e(chip)}</td>"
            f'<td class="num">{bench}</td>'
            f'<td class="num">{hits}</td>'
            f'<td class="num" data-v="{xgi}">'
            f"{meter(xgi, maxx, f'{xgi:.1f} xGI')} {xgi:.1f}</td>"
            "</tr>"
        )
    return (
        '<div class="scroll"><table class="league-standings" data-sortable><thead><tr>'
        '<th class="num sortable">#</th><th class="sortable">Team</th>'
        '<th class="num sortable">Total</th><th class="num sortable">GW</th>'
        '<th class="sortable">Captain</th>'
        '<th class="sortable">Chip</th><th class="num sortable">Bench</th>'
        '<th class="num sortable">Hits</th><th class="num sortable">XI xGI</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def chips_table(histories):
    names = ["wildcard", "freehit", "bboost", "3xc"]
    label = {"wildcard": "Wildcard", "freehit": "Free Hit",
             "bboost": "Bench Boost", "3xc": "Triple Captain"}
    body = []
    for mgr, h in histories.items():
        used = {}
        for c in h.get("chips", []):
            used.setdefault(c["name"], []).append(str(c["event"]))
        cells = "".join(
            f"<td>{'GW' + ', '.join(used[c]) if c in used else '-'}</td>" for c in names
        )
        body.append(f"<tr><td><b>{e(mgr)}</b></td>{cells}</tr>")
    head = "".join(f"<th>{label[c]}</th>" for c in names)
    return (
        '<div class="scroll"><table><thead><tr><th>Manager</th>'
        f"{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )
