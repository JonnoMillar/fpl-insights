"""The transfer plan card: moves by gameweek, and the squad each week.

Rendered from planner.describe's plain data. Every state a colour might
carry is also written out - IN, C, V, the chip name - so nothing on it
depends on telling two hues apart.
"""

import components
from cards_common import hook, icon
from components import e

CHIP_LABEL = {"bboost": "Bench Boost", "3xc": "Triple Captain"}
CHIP_ICON = {"bboost": "bench-boost", "3xc": "triple-captain"}
CHIP_SHORT = {"bboost": "BB", "3xc": "TC"}
POS_ORDER = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _fx(fx):
    if not fx:
        return "blank"
    return f"{fx['opp']} ({'H' if fx['home'] else 'A'})"


def _week_summary(w):
    """"2 transfers · 1 free · 4-point hit" or "Roll"."""
    n = len(w["moves"])
    if not n:
        return (f"Roll · {w['ft_before']}→{w['ft_after']} FT"
                if w["ft_before"] < w["ft_after"] else
                f"Roll · {w['ft_before']} FT, at the cap")
    free = min(n, w["ft_before"])
    parts = [_plural(n, "transfer"), f"{free} free"]
    if w["hits"]:
        parts.append(f"{w['hits'] * 4}-point hit")
    return " · ".join(parts)


POS_WORD = {"GKP": "goalkeeper", "DEF": "defence", "MID": "midfield", "FWD": "attack"}


def _kit_key(el, ctx, shirts, badges):
    """(css class, image uri) for a player's shirt, else his club crest."""
    keeper = ctx.pos(el) == "GKP"
    if shirts.get((el["team"], keeper)):
        return f"plan-kit-{el['team']}-{int(keeper)}", shirts[(el["team"], keeper)]
    if badges.get(el["team"]):
        return f"plan-crest-{el['team']}", badges[el["team"]]
    return None, None


def _player_card(pid, w, ctx, shirts, badges):
    el = ctx.players[pid]
    pos = ctx.pos(el)
    team = ctx.team_name(el["team"])
    # Eight weeks of fifteen shirts is 120 images of a dozen distinct kits;
    # each is drawn from one stylesheet rule rather than repeated inline,
    # which kept about 0.7 MB of duplicate data out of the page.
    cls, _uri = _kit_key(el, ctx, shirts, badges)
    crest = (f'<span class="plan-kit {cls}"></span>' if cls
             else f'<span class="letters">{e(team)}</span>')
    arm = ""
    if pid == w["captain"]:
        arm = '<span class="arm" title="Captain">C</span>'
    elif pid == w["vice"]:
        arm = '<span class="arm plan-vice" title="Vice-captain">V</span>'
    new = pid in w["new"]
    tag = '<span class="plan-in-tag">IN</span>' if new else ""
    pts = w["player_points"].get(pid, 0.0)
    fx = _fx(w["fixtures"].get(pid))
    label = (f"{el['web_name']}, {pos}, {team}: {fx}, {pts:.1f} projected"
             + (", captain" if pid == w["captain"] else "")
             + (", vice-captain" if pid == w["vice"] else "")
             + (", signed this week" if new else ""))
    return (
        f'<div class="pl pk plan-pl{" plan-new" if new else ""}" title="{e(label)}" '
        f'{hook(pid, label)}>{arm}{tag}'
        f'<div class="crest">{crest}</div>'
        f'<div class="nm">{e(el["web_name"])}</div>'
        f'<div class="plan-fx">{e(fx)}</div>'
        f'<div class="plan-pts tnum">{pts:.1f}</div></div>'
    )


def _pitch_html(w, ctx, shirts, badges):
    rows = {1: [], 2: [], 3: [], 4: []}
    for pid in w["xi"]:
        rows[POS_ORDER[ctx.pos(ctx.players[pid])]].append(pid)
    out = ['<div class="pitch plan-pitch">' + components.PITCH_MARKS]
    for k in (1, 2, 3, 4):
        if rows[k]:
            out.append('<div class="row">' + "".join(
                _player_card(p, w, ctx, shirts, badges) for p in rows[k]) + "</div>")
    out.append("</div>")
    bench_label = "Bench (Bench Boost: all four score)" if w["chip"] == "bboost" else "Bench, in sub order"
    out.append(f'<div class="benchstrip"><div class="lbl">{bench_label}</div><div class="row">'
               + "".join(_player_card(p, w, ctx, shirts, badges) for p in w["bench"])
               + "</div></div>")
    return "".join(out)


def _move_tags(m, w):
    """Why this move, in this week, as short tags: a restructure, a hit
    worth taking, or a signing who waits out a bad run first."""
    tags = []
    if m["out_cheap"] != m["in_cheap"]:
        partner = next((x for x in w["moves"] if x is not m
                        and x["out_cheap"] != x["in_cheap"]
                        and x["out_cheap"] != m["out_cheap"]), None)
        if partner and m["out_cheap"]:
            tags.append(f"cheap slot to {POS_WORD[partner['pos']]}")
        elif partner:
            tags.append("takes the cheap slot")
        elif m["in_cheap"]:
            tags.append("frees money")
    if m.get("urgent") == "out":
        tags.append("hit: ruled out")
    elif m.get("urgent") == "in":
        tags.append("hit: top-5 xGI/90")
    if m["waited"]:
        wt = m["waited"]
        weeks = (f"GW{wt['from_gw']}" if wt["from_gw"] == wt["to_gw"]
                 else f"GW{wt['from_gw']}–{wt['to_gw']}")
        tags.append(f"waits out {weeks}")
    return tags


def _figs(el, ctx):
    """Form and one chance rate for the position: the figures behind a move."""
    attack = ctx.pos(el) in ("MID", "FWD")
    key = "expected_goal_involvements_per_90" if attack else "expected_goals_conceded_per_90"
    rate = el.get(key)
    return el.get("form"), ("xGI/90" if attack else "xGC/90"), rate


def _crest_for(short, ctx, badges):
    """The crest for a club named by its short name, as fixtures carry it."""
    teams = getattr(ctx, "teams", {}) or {}
    tid = next((t for t, row in teams.items() if row.get("short_name") == short), None)
    return badges.get(tid) if tid is not None else None


def _move_html(m, w, ctx, photos, badges):
    """One planned move on the transfer card: the old player greyed out on
    the left, the new one standing on the panel's edge, and a night strip of
    figures - his opponent's crest, form and chance rate against the man he
    replaces. No per-player points: the week's one gain is in the stage head,
    because two legs of one move are not worth their own separate gains."""
    out_el, in_el = ctx.players[m["out"]], ctx.players[m["in"]]
    out_img = (f'<img class="cut move-old" src="{photos[m["out"]]}" '
               f'{hook(m["out"], out_el["web_name"])}>' if photos.get(m["out"]) else "")
    in_img = (f'<img class="cut move-new" src="{photos[m["in"]]}" '
              f'{hook(m["in"], in_el["web_name"])}>' if photos.get(m["in"]) else "")
    def crest(pid):
        fx = w["fixtures"].get(pid)
        uri = _crest_for(fx["opp"], ctx, badges) if fx else None
        where = e(_fx(fx))
        return (f'<img src="{uri}" alt="{where}" title="{where}">' if uri
                else f'<span>{where}</span>')

    (o_form, label, o_rate), (i_form, _l, i_rate) = _figs(out_el, ctx), _figs(in_el, ctx)

    def num(v, fmt):
        return "&ndash;" if v is None else fmt.format(float(v))

    # The same strip of figures as the Squad tab's move cards.
    figs = "".join(
        f'<div><dt>{lab}</dt><dd><span class="was">{a}</span><b>{b}</b></dd></div>'
        # The plan carries fixtures only for players in that week's squad, so
        # the man sold has no "next" to show; the signing's opponent stands alone.
        for lab, a, b in (("Next", "", crest(m["in"])),
                          ("Form", num(o_form, "{:.1f}"), num(i_form, "{:.1f}")),
                          (label, num(o_rate, "{:.2f}"), num(i_rate, "{:.2f}"))))
    money = m["sell"] - m["price"]
    meta = [e(m["in_club"]), f'{m["price"]:.1f}m',
            "free swap" if abs(money) < 0.05 else f"bank {money:+.1f}m"]
    meta += [e(t) for t in _move_tags(m, w)]
    return (
        '<li class="move-slot plan-move">'
        f'{out_img}<span class="move-arrow">{icon("next")}</span>{in_img}'
        f'<div class="move-names"><span class="move-out">{e(out_el["web_name"])} out</span>'
        f'<span class="move-in disp">{e(in_el["web_name"])}</span>'
        f'<span>{" &middot; ".join(meta)}</span></div>'
        f'<div class="move-figs"><dl class="tnum">{figs}</dl></div></li>'
    )


def _tile_html(w, n, photos):
    """One week's tile: who comes in, the chip, or a roll."""
    moves = w["moves"]
    if w["chip"]:
        visual = f'<span class="coin coin-{w["chip"]}">{icon(CHIP_ICON[w["chip"]])}</span>'
        caption = CHIP_LABEL[w["chip"]]
    elif moves:
        faces = []
        for m in moves[:2]:
            if photos.get(m["in"]):
                faces.append(f'<img class="face" src="{photos[m["in"]]}" alt="">')
            else:
                faces.append(f'<span class="face face-blank">{e(m["in_name"][:1])}</span>')
        visual = f'<span class="faces">{"".join(faces)}</span>'
        caption = moves[0]["in_name"] if len(moves) == 1 else f"{len(moves)} in"
    else:
        visual = f'<span class="coin coin-roll">{icon("roll-transfer")}</span>'
        caption = "Roll"
    hit = f' <span class="wk-hit">−{w["hits"] * 4}</span>' if w["hits"] else ""
    selected = "true" if n == 0 else "false"
    label = f"GW{w['gw']}" if w["gw"] == w.get("to_gw", w["gw"]) else f"GW{w['gw']}–{w['to_gw']}"
    return (
        f'<button class="wk" type="button" role="tab" aria-selected="{selected}" '
        f'data-panel="plan-gw-{w["gw"]}"><span class="lab">{label}</span>{visual}'
        f'<b>{e(caption)}{hit}</b></button>'
    )


NUMBER_WORD = {1: "ONE", 2: "TWO", 3: "THREE"}


def _bench_slot(pid, w, ctx, photos, badges, big=False):
    el = ctx.players[pid]
    fx = w["fixtures"].get(pid)
    crest = _crest_for(fx["opp"], ctx, badges) if fx else None
    img = (f'<img class="cut" src="{photos[pid]}" {hook(pid, el["web_name"])}>'
           if photos.get(pid) else "")
    where = e(_fx(fx))
    crest_html = f'<img src="{crest}" alt="{where}" title="{where}">' if crest else f'<span>{where}</span>'
    pts = w["player_points"].get(pid, 0.0)
    return (f'<li class="bench-slot{" bench-big" if big else ""}">{img}'
            f'<div class="bench-cap"><b>{e(el["web_name"])}</b>'
            f'<span class="tnum">{pts:.1f}</span>{crest_html}</div></li>')


def _stage_html(w, n, end_gw, first_gw, ctx, photos, badges, shirts, show_bank):
    moves = w["moves"]
    chip = CHIP_LABEL.get(w["chip"]) if w["chip"] else ""
    if moves:
        title = f"{NUMBER_WORD.get(len(moves), len(moves))} IN, " + (
            f"{w['hits'] * 4}-POINT HIT" if w["hits"] else "NO HIT")
    else:
        title = "ROLL"
    if chip:
        title = chip.upper() + (f" · {title}" if moves else "")
    gain = ""
    if moves and w["gain"] is not None:
        window = (f"xP to GW{end_gw}" if w["gw"] == first_gw else
                  f"xP, GW{w['gw']}" if w["gw"] == end_gw else f"xP, GW{w['gw']}–{end_gw}")
        prep = w.get("chip_prep")
        # A move made for a chip held past the plan gains little inside it;
        # the chip's lift is its real figure, so it is shown beside the gain.
        prep_html = (f'<span class="stage-prep"><b class="tnum">{prep["gain"]:+.1f}</b> '
                     f'{e(CHIP_SHORT.get(prep["key"], prep["key"]))} prep</span>'
                     if prep else "")
        gain = (f'<span class="stage-gain"><b class="big tnum">{w["gain"]:+.1f}</b> '
                f'{window}{", after the hit" if w["hits"] else ""}</span>{prep_html}')
    if moves:
        body = ('<ul class="move-slots plan-moves">'
                + "".join(_move_html(m, w, ctx, photos, badges) for m in moves)
                + "</ul>")
    elif w["chip"] == "bboost":
        body = ('<ul class="bench-boost">'
                + "".join(_bench_slot(p, w, ctx, photos, badges) for p in w["bench"])
                + "</ul>")
    elif w["chip"] == "3xc":
        body = f'<ul class="bench-boost">{_bench_slot(w["captain"], w, ctx, photos, badges, big=True)}</ul>'
    else:
        body = (f'<div class="roll-stage"><span class="coin coin-roll coin-big">'
                f'{icon("roll-transfer")}</span></div>')
    facts = [_week_summary(w)]
    if show_bank:
        facts.append(f"{w['bank']:.1f}m in the bank")
    d, m_, f_ = w["formation"]
    # The plan shows moves and chips, not a weekly team total: the squad is
    # here to look at, with its shape, not a second xP to compare.
    squad = (f'<details class="stage-squad"><summary>Squad for GW{w["gw"]} &middot; '
             f'{d}-{m_}-{f_}</summary>'
             f'{_pitch_html(w, ctx, shirts, badges)}</details>')
    hidden = "" if n == 0 else " hidden"
    green = " stage-chip" if w["chip"] else ""
    label = f"GW{w['gw']}" if w["gw"] == w.get("to_gw", w["gw"]) else f"GW{w['gw']}–{w['to_gw']}"
    return (
        f'<div class="stage-panel{green}" id="plan-gw-{w["gw"]}" role="tabpanel" '
        f'tabindex="-1" data-plan-gw="{w["gw"]}"{hidden}>'
        f'<div class="stage-head"><h3 class="disp">{label} &middot; {e(title)}</h3>{gain}</div>'
        f'<p class="stage-facts">{" &middot; ".join(e(x) for x in facts)}</p>'
        f'{body}{squad}</div>'
    )


def plan_card(plan, ctx, shirts, badges, photos=None):
    photos = photos or {}
    if not plan:
        return ""
    weeks = plan["weeks"]
    span = f"GW{plan['start_gw']}–{plan['end_gw']}"
    end = plan["end_gw"]
    first_gw = weeks[0]["gw"]
    # Consecutive roll weeks are one decision - bank the transfers - so they
    # share one tile and one stage: "GW14–17 · Roll · 1→5 FT".
    shown = []
    for w in weeks:
        prev = shown[-1] if shown else None
        if (prev and not w["moves"] and not w["chip"]
                and not prev["moves"] and not prev["chip"]):
            shown[-1] = {**prev, "to_gw": w["gw"], "ft_after": w["ft_after"],
                         "bank": w["bank"]}
        else:
            shown.append(w)
    # A roll that leaves the bank where the week before did has nothing new to say about it.
    quiet = {w["gw"] for prev, w in zip(shown, shown[1:])
             if not w["moves"] and w["bank"] == prev["bank"]}
    tiles = "".join(_tile_html(w, n, photos) for n, w in enumerate(shown))
    stages = "".join(_stage_html(w, n, end, first_gw, ctx, photos, badges, shirts,
                                 w["gw"] not in quiet)
                     for n, w in enumerate(shown))

    moved = abs(plan["gain"]) >= 0.05
    headline = f"{plan['gain']:+.1f}" if moved else f"{plan['total']:.0f}"
    headline_note = "xP v no moves, after hits" if moved else "xP; no move clears the bar"
    cheap = ""
    if plan["enablers"]:
        rows = []
        for x in plan["enablers"]:
            face = (f'<img class="face" src="{photos[x["id"]]}" {hook(x["id"], x["name"])}>'
                    if photos.get(x["id"]) else "")
            rows.append(f'<li>{face}<span><b>{e(x["name"])}</b> '
                        f'{e(x["pos"])} &middot; {x["price"]:.1f}m</span></li>')
        cheap = (f'<div class="plan-cheap"><span class="lab">Cheap slots kept</span>'
                 f'<ul>{"".join(rows)}</ul></div>')
    chips = [f"{CHIP_LABEL[w['chip']]} in GW{w['gw']}" for w in weeks if w["chip"]]
    if plan["chips_modelled"]:
        chip_line = (f'<p class="plan-chips">{e("; ".join(chips))}.</p>' if chips else "")
    else:
        chip_line = '<p class="plan-chips">Chip history unverified · no chip planned</p>'

    kits = {}
    for w in weeks:
        for pid in w["xi"] + w["bench"]:
            cls, uri = _kit_key(ctx.players[pid], ctx, shirts, badges)
            if cls:
                kits[cls] = uri
    kit_css = "".join(f".{cls}{{background-image:url({uri})}}" for cls, uri in sorted(kits.items()))

    # The one home of the plan's rules: the page's other copies of them went.
    note = (f"Each week: best XI from your 15, captain twice, bench by its chance of "
            f"coming on (all of it on Bench Boost week). Roll, or one or two moves a week. "
            f"Each move must clear {plan['margin']:g} points on top of any 4-point hit; hits "
            f"only for an urgent move this week. A banked free transfer at the end is worth "
            f"{plan['ft_value']:g}. Later weeks count for less. Cheap bench slots stay cheap "
            f"unless a two-move restructure moves them. Chips play only when their week "
            f"beats waiting by {plan['chip_margin']:g}. Re-planned at every update.")
    ft = weeks[0]["ft_before"]
    return (
        f'<style>{kit_css}</style>'
        f'<section class="plan-card" id="transfer-plan" tabindex="-1" aria-labelledby="plan-title">'
        f'<div class="plan-top card-head"><div><span class="lab">The plan &middot; {span}</span>'
        f'<h2 class="disp" id="plan-title">{_plural(len(weeks), "week").upper()}, MAPPED.'
        f'{components.info_btn()}</h2></div>'
        f'<span class="plan-ft"><b class="tnum">{ft}</b> free transfer{"" if ft == 1 else "s"}</span>'
        f'<span class="sub" hidden>{e(note)}</span></div>'
        f'<div class="plan-grid"><div class="plan-main">'
        f'<div class="wk-row" role="tablist" aria-label="Choose a gameweek">{tiles}</div>'
        f'<div class="stage">{stages}</div></div>'
        f'<aside class="plan-sum"><span class="lab">{span}</span>'
        f'<b class="big tnum">{headline}</b><span class="plan-sum-note">{headline_note}</span>'
        f'<span class="plan-total"><b class="tnum">{plan["total"]:.0f}</b> xP over the window</span>'
        f'{chip_line}{cheap}</aside></div></section>'
    )
