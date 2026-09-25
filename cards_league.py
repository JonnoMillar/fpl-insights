"""Cards for the Mini-league tab: standings, ownership, template and rivals."""

import json
import math

import analysis
import components
import fplapi
import transfers
from analysis import f
from cards_common import TONE_COLOR, e, meter


def findings_cards(finds):
    cards = []
    for fnd in finds:
        tone = TONE_COLOR.get(fnd["tone"], "var(--p60)")
        items = []
        for raw in fnd["items"]:
            # Findings read "Player - what happened". Splitting on that first
            # dash lets the name lead in bold and the evidence sit under it,
            # which is the difference between a wall of prose and a list you
            # can actually scan.
            lead, sep, detail = raw.partition(" - ")
            if sep and len(lead) < 40:
                items.append(
                    f'<li><span class="lead">{e(lead)}</span>'
                    f'<span class="det">{e(detail)}</span></li>'
                )
            else:
                items.append(f'<li><span class="det">{e(raw)}</span></li>')
        items = "".join(items)
        note = f'<p class="note">{e(fnd["note"])}</p>' if fnd["note"] else ""
        cards.append(
            f'<div class="find" style="--tone:{tone}">'
            f"<h3>{e(fnd['title'])}</h3>{note}<ul>{items}</ul></div>"
        )
    return f'<div class="finds">{"".join(cards)}</div>'


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
        f'<text class="dnum" x="45" y="43" text-anchor="middle">{e(center)}</text>'
        f'<text class="dsub" x="45" y="57" text-anchor="middle">{e(sub)}</text>'
        "</svg>"
    )


def ownership_carousel(own, by_name, ctx, my_name):
    """Mini-league ownership, one doughnut per player, arrows to move.

    Deliberately not auto-advancing: a slideshow that moves on its own hides
    most of the data behind waiting and takes the reading pace out of your
    hands. The track scrolls, snaps, and answers to the arrow keys."""
    n = len(by_name)
    if not own or not n:
        return ""
    rows = sorted(own.items(), key=lambda kv: -len(kv[1]["owners"]))
    # Two owners out of eight, or nothing. Below that the card stops being
    # ownership analysis and becomes a dump of every squad in the league: at
    # GW3 roughly thirty of the fifty cards were single-owner punts, each
    # rendered at the same size and weight as the player all eight hold, and
    # the shape you actually came here to read - who has converged on what -
    # was buried under them. Whoever only one manager owns is his business.
    floor = 2 if n > 4 else 1
    shown = [(pid, rec) for pid, rec in rows if len(rec["owners"]) >= floor]
    hidden_n = len(rows) - len(shown)
    cards = []
    for pid, rec in shown:
        el = ctx.players.get(pid)
        if not el:
            continue
        owners = len(rec["owners"])
        pct = 100.0 * owners / n
        mine = my_name in rec["owners"]
        tone = "var(--accent)" if mine else "var(--p60)"
        caps = len(rec["captains"])
        note = f"{caps} captained him" if caps else "&nbsp;"
        aria = f"{el['web_name']} owned by {owners} of {n} managers"
        own_flag = '<p class="oyou">You own him</p>' if mine else ""
        cards.append(
            f'<li class="ocard{" mine" if mine else ""}">'
            f"{donut(pct, aria, f'{owners}/{n}', f'{pct:.0f}%', tone)}"
            f'<p class="oname">{e(el["web_name"])}</p>'
            f'<p class="oteam">{e(ctx.team_name(el["team"]))} &middot; {el["total_points"]} pts</p>'
            f'<p class="onote">{note}</p>'
            f"{own_flag}"
            "</li>"
        )
    tail = (f' Owned by only one manager: {hidden_n} more, not shown.'
            if hidden_n else "")
    return (
        '<section class="card">'
        f'<div class="card-head"><h2>Who owns whom{components.info_btn()}</h2>'
        f'<span class="subvis">Share of the {n} managers in <b>this league</b> '
        f'holding each player &mdash; not global FPL ownership.{tail}</span>'
        f'<span class="sub" hidden>Share of the {n} managers in this league holding each '
        f"player, most-owned first. Players only one manager owns are left "
        f"out: at this league size they are punts, not a shared position.</span>"
        '<span class="carnav">'
        '<button class="arrow" data-dir="-1" aria-label="Scroll left">&#8249;</button>'
        '<button class="arrow" data-dir="1" aria-label="Scroll right">&#8250;</button>'
        "</span></div>"
        f'<div class="card-body"><ul class="carousel" tabindex="0" '
        f'aria-label="Ownership by player">{"".join(cards)}</ul></div>'
        "</section>"
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
        f'<span class="subvis">Only <b>{majority} of 11</b> are held by more '
        f'than half the league. This is always a full eleven, so the thin '
        f'slots are the top of a scattered position, not a consensus.</span>'
        f'<span class="sub" hidden>The most-started legal eleven across {n} managers, '
        f'in a {tpl["shape"]}. You have {owned_by_you} of them &mdash; the rest '
        "is where your rank moves.</span></div>"
        f'<div class="pitch tplpitch">{components.PITCH_MARKS}'
        f'{"".join(rows)}</div></section>'
    )


def differential_watchlist(own, ctx, proj, market, baselines, next_gw, squad_ids,
                           limit=6):
    """Players performing well that nobody in this league owns - not you,
    not any rival.

    Scored with transfers.case_score, the same several-week, form-and-
    underlying-numbers logic the Planning tab's transfer suggestions use -
    "performing well" means the same thing here as everywhere else that
    phrase appears on this page, not a separate reading of the numbers."""
    if not own:
        return []
    priors = transfers.positional_priors(ctx)
    owned_ids = set(own.keys()) | set(squad_ids)
    rows = []
    for el in ctx.players.values():
        pid = el["id"]
        if pid in owned_ids or not transfers._eligible(el, ctx):
            continue
        s = transfers.case_score(el, ctx, proj, next_gw, market, baselines, priors)
        if not s or s["total"] <= 0:
            continue
        rows.append({
            "id": pid, "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "price": el["now_cost"] / 10.0,
            "ep": s["total"], "opponent": s["opponent"], "home": s["home"],
            "owned_pct": f(el.get("selected_by_percent")),
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


def differential_watchlist_card(rows, photos, weeks):
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
            f'<div><dt>Owned, all FPL</dt><dd>{r["owned_pct"]:.0f}%</dd></div>'
            f"</dl></div></li>"
        )
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Differential watchlist{components.info_btn()}</h2>'
        '<span class="subvis">Nobody in <b>your league</b> owns these. The '
        'ownership figure beside each one is across <b>all of FPL</b>, which '
        'is what decides whether he is actually a differential.</span>'
        '<span class="sub" hidden>Nobody in this league owns these - scored the '
        f'same way as every transfer suggestion on the Planning tab, over the '
        f'next {weeks} gameweeks. Capped at two per club so one kind fixture '
        f'cannot fill the list with the same bet.</span></div>'
        f'<div class="card-body"><ul class="dflist">{"".join(cards)}</ul></div>'
        "</section>"
    )


def differential_card(own, by_name, ctx, my_name, photos):
    """Players only you own, given room and a face.

    A one-line list in a grid cell left most of the card empty and made the
    single most interesting fact on the page look like an afterthought. With
    few enough of them, each gets a portrait and its numbers."""
    n = len(by_name)
    if not own or not my_name:
        return ""
    mine = [
        (pid, rec) for pid, rec in own.items()
        if my_name in rec["owners"] and len(rec["owners"]) == 1
    ]
    if not mine:
        return (
            f'<section class="card"><div class="card-head"><h2>Your differentials{components.info_btn()}</h2>'
            '<span class="sub" hidden>Players nobody else in the league owns.</span></div>'
            '<div class="card-body"><p class="dfempty">Every player you own is '
            "owned by somebody else in this league. You are running the template "
            "&mdash; safe from falling behind, and with nothing that can pull you "
            "clear.</p></div></section>"
        )
    mine.sort(key=lambda x: -f(ctx.players[x[0]]["expected_goal_involvements"]))
    cards = []
    for pid, _rec in mine:
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
            f'<div><dt>Points</dt><dd>{el["total_points"]}</dd></div>'
            f'<div><dt>xGI</dt><dd>{f(el["expected_goal_involvements"]):.2f}</dd></div>'
            f'<div><dt>Owned, all FPL</dt>'
            f'<dd>{f(el["selected_by_percent"]):.0f}%</dd></div>'
            f"</dl></div></li>"
        )
    return (
        f'<section class="card"><div class="card-head"><h2>Your differentials{components.info_btn()}</h2>'
        f'<span class="subvis">Nobody else in <b>your league</b> owns '
        f'{"them" if len(mine) > 1 else "him"}. The percentage is <b>all of '
        f'FPL</b> &mdash; the two answer different questions, and a man 1/8 '
        f'here can still be 20% everywhere.</span>'
        f'<span class="sub" hidden>Nobody else in this league owns '
        f'{"them" if len(mine) > 1 else "him"}. Every point '
        f'{"they score" if len(mine) > 1 else "he scores"} is a point on the '
        "whole league.</span></div>"
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
        f'<h2>Scoring against you{components.info_btn()}</h2>'
        '<span class="subvis">Points that went onto other people&rsquo;s '
        'scores and not yours. A haul <b>one</b> rival owned cost you ground '
        'on one manager; the same haul <b>most</b> of them owned cost you '
        'ground on the whole league, so the order weighs both.</span>'
        '<span class="sub" hidden>Players you did not own who returned for the '
        "rest of this league. Ranked by points scored and by how many rivals "
        "actually started him.</span></div>"
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
        need = LP_MIN_GWS - len(data["gws"])
        return (
            '<section class="card"><div class="card-head">'
            f'<h2>League position over time{components.info_btn()}</h2>'
            '<span class="sub" hidden>Every manager&rsquo;s rank in this league, '
            'gameweek by gameweek. Held back until there are enough gameweeks '
            'for the lines to mean anything.</span></div>'
            '<div class="card-body"><p class="dfempty">'
            f'{len(data["series"])} managers across {len(data["gws"])} '
            f'gameweek{"s" if len(data["gws"]) != 1 else ""} is a knot, not a '
            f'trend &mdash; every line would cross every other. This chart '
            f'appears after GW{data["gws"][0] + LP_MIN_GWS - 1} '
            f'({need} more to go).'
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
        f'<h2>League position over time{components.info_btn()}</h2>'
        '<span class="sub" hidden>Every manager\'s rank in this league, gameweek '
        'by gameweek - 1st at the top. Toggle to total points instead.</span></div>'
        '<div class="card-body">'
        '<div class="lptoggle tabbar" role="group" aria-label="Y axis">'
        '<button class="lpbtn" data-y="position" aria-pressed="true">Position</button>'
        '<button class="lpbtn" data-y="points" aria-pressed="false">Points</button>'
        "</div>"
        '<div class="scroll"><svg class="lpchart" viewBox="0 0 1040 460" '
        'role="img" aria-label="League position over time"></svg></div>'
        f'<ul class="lplegend">{legend}</ul>'
        f'<script type="application/json" class="lpchart-data">{json.dumps(data)}</script>'
        "</div></section>"
    )


CHIP_LABEL = {
    "3xc": "Triple Captain", "bboost": "Bench Boost",
    "freehit": "Free Hit", "wildcard": "Wildcard",
    "manager": "Assistant Manager",
}


def league_week_lede(rows, squads, ctx, me, gw):
    """What actually decided this week in this league, in one sentence.

    The standings hold it already - a Chip column, a Captain column - but
    as eight independent cells, and the thing that moved the table is a
    pattern across them. In GW3 five of eight managers triple-captained the
    same player: every one of them banked his score twice over, the "51
    average" the hero line measures you against is a global figure that knows
    nothing about it, and a 67 that reads as a good week was in fact a week
    you lost ground in. That is the single most useful sentence on the tab and
    nothing was saying it."""
    if not rows or not squads:
        return ""
    n = len(rows)
    my_chip = None
    chips_used = {}
    for r in rows:
        picks = squads.get(r["entry"])
        if not picks:
            continue
        chip = picks.get("active_chip")
        if me and r["entry"] == me:
            my_chip = chip
        if chip:
            chips_used.setdefault(chip, []).append(r["entry_name"])
    if not chips_used:
        return ""
    top_chip, users = max(chips_used.items(), key=lambda kv: len(kv[1]))
    label = CHIP_LABEL.get(top_chip, top_chip)
    if len(users) < 2:
        return ""
    mine_too = my_chip == top_chip
    tail = (" You played it too."
            if mine_too else
            f" You did not, so your gameweek score is being compared against "
            f"{'a field' if len(users) < n - 1 else 'a league'} that mostly "
            f"scored theirs twice.")
    return (
        f'<p class="lglede"><b>{len(users)} of {n}</b> played '
        f'<b>{e(label)}</b> in GW{gw}.{e(tail)}</p>'
    )


def league_table(rows, squads, ctx, me):
    xgis = [analysis.squad_underlying(p, ctx)["xgi"] for p in squads.values()]
    maxx = max(xgis + [0.01])
    # Whether this column separates anybody yet. Eight managers inside one
    # xGI of each other is a column of near-identical bars, and a bar chart
    # whose bars are all the same length still reads as a comparison - it just
    # quietly says nothing. Said out loud instead of implied.
    spread = (max(xgis) - min(xgis)) if len(xgis) > 1 else 0.0
    flat_xgi = bool(xgis) and spread < 0.2 * maxx
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
            f'<td><b>{e(r["entry_name"])}</b></td>'
            f'<td>{e(r["player_name"])}</td>'
            f'<td class="num" data-v="{r["event_total"]}">{r["event_total"]}{gw_tag}</td>'
            f'<td class="num"><b>{r["total"]}</b></td>'
            f"<td>{e(cap)}</td>"
            f"<td>{e(chip)}</td>"
            f'<td class="num">{bench}</td>'
            f'<td class="num">{hits}</td>'
            f'<td class="num" data-v="{xgi}">'
            f"{meter(xgi, maxx, f'{xgi:.1f} xGI')} {xgi:.1f}</td>"
            "</tr>"
        )
    note = (
        f'<p class="lgnote">XI xGI spans just {spread:.1f} across all '
        f'{len(xgis)} squads &mdash; nobody is separated by it yet. Read it '
        f'again once the season has a few more weeks in it.</p>'
        if flat_xgi else ""
    )
    return (
        note
        + '<div class="scroll"><table data-sortable><thead><tr>'
        '<th class="num sortable">#</th><th class="sortable">Team</th>'
        '<th class="sortable">Manager</th><th class="num sortable">GW</th>'
        '<th class="num sortable">Total</th><th class="sortable">Captain</th>'
        '<th class="sortable">Chip</th><th class="num sortable">Bench</th>'
        '<th class="num sortable">Hits</th><th class="num sortable">XI xGI</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def ownership_cards(own, by_name, ctx, my_name):
    n = len(by_name)

    def nm(pid):
        el = ctx.players.get(pid)
        return f"{el['web_name']} ({ctx.team_name(el['team'])})" if el else str(pid)

    mine = {p for p, r in own.items() if my_name in r["owners"]}
    blocks = []

    template = sorted(
        (p for p, r in own.items() if len(r["owners"]) >= max(2, n * 0.5)),
        key=lambda p: -len(own[p]["owners"]),
    )
    if False and template:
        items = [
            f"{nm(p)} - {len(own[p]['owners'])}/{n} managers"
            f"{'' if p in mine else '  (you do not own)'}"
            for p in template
        ]
        blocks.append(analysis._finding("t", "League template", "neutral", items,
                                        f"Owned by at least half of {n} managers."))

    diffs = sorted(
        (p for p in mine if len(own[p]["owners"]) == 1),
        key=lambda p: -f(ctx.players[p]["expected_goal_involvements"]),
    )
    if False and diffs:
        items = [
            f"{nm(p)} - {ctx.players[p]['total_points']} pts, "
            f"xGI {f(ctx.players[p]['expected_goal_involvements']):.2f}, "
            f"{f(ctx.players[p]['selected_by_percent']):.0f}% owned overall"
            for p in diffs
        ]
        blocks.append(analysis._finding("d", "Your differentials", "good", items,
                                        "Nobody else in the league owns them."))

    gaps = sorted(
        (p for p, r in own.items() if p not in mine and len(r["owners"]) >= max(2, n * 0.4)),
        key=lambda p: -ctx.players[p]["total_points"],
    )
    if gaps:
        items = [
            f"{nm(p)} - {len(own[p]['owners'])}/{n} own, "
            f"{ctx.players[p]['total_points']} pts, "
            f"xGI {f(ctx.players[p]['expected_goal_involvements']):.2f}"
            for p in gaps
        ]
        blocks.append(analysis._finding("g", "The league has these, you do not", "warn", items))

    caps = {}
    for pid, r in own.items():
        for c in r["captains"]:
            caps.setdefault(pid, []).append(c)
    if caps:
        items = [
            f"{nm(pid)} - {len(who)}/{n}: {', '.join(who)} "
            f"({ctx.players[pid]['event_points']} pts this gameweek)"
            for pid, who in sorted(caps.items(), key=lambda kv: -len(kv[1]))
        ]
        blocks.append(analysis._finding("c", "Captain picks", "info", items))

    # Same "this gameweek's decisions" moment as captain picks above, the
    # other place a decision this week actually cost points - who left the
    # most on the bench, from the entry histories already fetched for the
    # league table and chips table, so no extra requests.
    bench = sorted(
        ((name, p.get("entry_history", {}).get("points_on_bench", 0))
         for name, p in by_name.items()),
        key=lambda kv: -kv[1],
    )
    bench = [kv for kv in bench if kv[1] > 0][:5]
    if bench:
        items = [f"{name} - {pts} point{'s' if pts != 1 else ''} benched"
                 for name, pts in bench]
        blocks.append(analysis._finding("b", "Points left on the bench", "warn", items))

    return findings_cards(blocks)


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
