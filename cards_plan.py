"""The transfer plan card: moves by gameweek, and the squad each week.

Rendered from planner.describe's plain data. Every state a colour might
carry is also written out - IN, C, V, the chip name - so nothing on it
depends on telling two hues apart.
"""

import components
from components import e

CHIP_LABEL = {"bboost": "Bench Boost", "3xc": "Triple Captain"}
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
        return (f"Roll · {_plural(w['ft_after'], 'free transfer')} next week"
                if w["ft_before"] < 5 else
                "Roll · already at the five-transfer cap")
    free = min(n, w["ft_before"])
    parts = [_plural(n, "transfer"), f"{free} free"]
    if w["hits"]:
        parts.append(f"{w['hits'] * 4}-point hit")
    return " · ".join(parts)


POS_WORD = {"GKP": "goalkeeper", "DEF": "defence", "MID": "midfield", "FWD": "attack"}


def _move_html(m, ctx, week_moves=()):
    out_el, in_el = ctx.players[m["out"]], ctx.players[m["in"]]
    money = m["sell"] - m["price"]
    money_txt = ("no cost" if abs(money) < 0.05 else
                 f"bank {'+' if money > 0 else '−'}{abs(money):.1f}m")
    notes = []
    if m["out_cheap"] != m["in_cheap"]:
        partner = next((x for x in week_moves if x is not m
                        and x["out_cheap"] != x["in_cheap"]
                        and x["out_cheap"] != m["out_cheap"]), None)
        if partner and m["out_cheap"]:
            notes.append(f"restructure with {e(partner['out_name'])} → "
                         f"{e(partner['in_name'])}: the cheap slot moves from "
                         f"{POS_WORD[m['pos']]} to {POS_WORD[partner['pos']]}, "
                         f"which pays for {e(m['in_name'])}")
        elif partner:
            notes.append(f"{e(m['in_name'])} takes the cheap slot, paying for "
                         f"{e(partner['in_name'])}")
        elif m["in_cheap"]:
            notes.append("a cheaper player who frees money")
    if m["waited"]:
        wt = m["waited"]
        weeks = (f"GW{wt['from_gw']}" if wt["from_gw"] == wt["to_gw"]
                 else f"GW{wt['from_gw']}–{wt['to_gw']}")
        fixtures = ", ".join(_fx(fx) for fx in wt["fixtures"])
        notes.append(f"waits out {weeks} ({e(fixtures)}), where he projects "
                     f"{wt['loss']:.1f} fewer than {e(out_el['web_name'])}")
    note = f'<p class="plan-note">{"; ".join(notes)}.</p>' if notes else ""
    return (
        '<li class="plan-move">'
        f'<span class="plan-out"><s>{e(out_el["web_name"])}</s> <small>{e(m["out_club"])} '
        f'{m["sell"]:.1f}m</small></span>'
        f'<span class="plan-arrow" aria-label="replaced by">→</span>'
        f'<span class="plan-in">{e(in_el["web_name"])} <small>{e(m["in_club"])} '
        f'{m["price"]:.1f}m</small></span>'
        f'<span class="plan-money">{money_txt}</span>'
        f'{note}</li>'
    )


def _week_html(w, ctx):
    chip = (f'<span class="plan-chip">{e(CHIP_LABEL[w["chip"]])}</span>'
            if w["chip"] else "")
    moves = "".join(_move_html(m, ctx, w["moves"]) for m in w["moves"])
    gain = ""
    if w["moves"] and w["gain"] is not None:
        gain = (f'<p class="plan-gain"><b class="tnum">{w["gain"]:+.1f}</b> projected '
                f'points from these moves to the end of the plan'
                f'{", after the hit" if w["hits"] else ""}.</p>')
    body = (f'<ul class="plan-moves">{moves}</ul>{gain}' if moves else "")
    return (
        f'<li class="plan-week" id="plan-gw-{w["gw"]}" tabindex="-1" data-plan-gw="{w["gw"]}">'
        f'<div class="plan-week-head"><b>GW{w["gw"]}</b>'
        f'<span>{_week_summary(w)}</span>{chip}'
        f'<span class="plan-bank tnum">{w["bank"]:.1f}m in the bank</span>'
        f'<button type="button" class="plan-view" data-show-gw="{w["gw"]}">GW{w["gw"]} squad</button></div>'
        f'{body}</li>'
    )


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
        f'aria-label="{e(label)}">{arm}{tag}'
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


def _panel_html(w, ctx, shirts, badges, first):
    d, m, f = w["formation"]
    ins = [ctx.players[x["in"]]["web_name"] for x in w["moves"]]
    outs = [ctx.players[x["out"]]["web_name"] for x in w["moves"]]
    changes = (f'<p class="plan-changes"><b>In:</b> {e(", ".join(ins))} &middot; '
               f'<b>Out:</b> {e(", ".join(outs))}</p>' if ins else
               '<p class="plan-changes">No transfers this week.</p>')
    chip = f" &middot; {e(CHIP_LABEL[w['chip']])}" if w["chip"] else ""
    return (
        f'<div class="plan-panel" id="plan-pitch-{w["gw"]}"{"" if first else " hidden"}>'
        f'<p class="plan-panel-head"><b>GW{w["gw"]}</b> &middot; '
        f'<span class="tnum">{w["points"]:.1f}</span> projected &middot; {d}-{m}-{f}{chip}</p>'
        f'{changes}{_pitch_html(w, ctx, shirts, badges)}</div>'
    )


def plan_card(plan, ctx, shirts, badges):
    if not plan:
        return ""
    weeks = plan["weeks"]
    show = plan["show_weeks"]
    span = f"GW{plan['start_gw']}–{plan['end_gw']}"
    lede = (f"Across {span} these moves project <b class=\"tnum\">{plan['total']:.0f}</b> "
            f"points, <b class=\"tnum\">{plan['gain']:+.1f}</b> against making no "
            f"transfers, after hits. Re-planned at every update, so later weeks are a "
            f"default, not a commitment.")
    if abs(plan["gain"]) < 0.05:
        lede = (f"No move clears the margins across {span}: rolling and keeping "
                f"this squad projects <b class=\"tnum\">{plan['total']:.0f}</b> points.")
    caps = plan["caps"]
    enablers = plan["enablers"]
    structure = ""
    if enablers:
        names = ", ".join(f"{x['name']} ({x['pos']} {x['price']:.1f}m)" for x in enablers)
        structure = (
            f'<p class="plan-structure">Cheap slots kept: {e(names)}. One leaves only '
            f'for another cheap player (up to {caps["GKP"]:.1f}m keepers and defenders, '
            f'{caps["MID"]:.1f}m midfielders and forwards), or in a two-move restructure '
            f'where a cheap player arrives in another position the same week.</p>')
    chips = []
    for w in weeks:
        if w["chip"]:
            chips.append(f"{CHIP_LABEL[w['chip']]} in GW{w['gw']}")
    for c in plan["held_chips"]:
        chips.append(f"{CHIP_LABEL[c['key']]} held: best projected week GW{c['gw']} "
                     f"(+{c['gain']:.1f}), after this plan")
    chip_line = ""
    if plan["chips_modelled"]:
        chip_line = (f'<p class="plan-chips">{e("; ".join(chips) + ".") if chips else "No Bench Boost or Triple Captain available."} '
                     'Free Hit and Wildcard are not planned here: see the chip planner.</p>')
    else:
        chip_line = ('<p class="plan-chips">Chip history could not be verified, so no '
                     'chip is planned.</p>')

    visible = "".join(_week_html(w, ctx) for w in weeks[:show])
    later = weeks[show:]
    later_html = ""
    if later:
        planned = sum(len(w["moves"]) for w in later)
        later_html = (
            f'<details class="plan-later"><summary>Later gameweeks, GW{later[0]["gw"]}–'
            f'{later[-1]["gw"]} ({_plural(planned, "planned move")})</summary>'
            f'<ol class="plan-weeks">{"".join(_week_html(w, ctx) for w in later)}</ol></details>')

    tabs = "".join(
        f'<button class="plan-gwbtn" role="tab" aria-selected="{"true" if n == 0 else "false"}" '
        f'data-panel="plan-pitch-{w["gw"]}">GW{w["gw"]}'
        f'{" <small>" + CHIP_SHORT[w["chip"]] + "</small>" if w["chip"] else ""}'
        f'</button>'
        for n, w in enumerate(weeks))
    panels = "".join(_panel_html(w, ctx, shirts, badges, n == 0) for n, w in enumerate(weeks))
    kits = {}
    for w in weeks:
        for pid in w["xi"] + w["bench"]:
            cls, uri = _kit_key(ctx.players[pid], ctx, shirts, badges)
            if cls:
                kits[cls] = uri
    kit_css = "".join(f".{cls}{{background-image:url({uri})}}" for cls, uri in sorted(kits.items()))

    note = (f"Each week scores the best eleven from your fifteen, the captain twice, and the "
            f"bench by its chance of coming on (all of it on Bench Boost week). A plan may "
            f"roll, or make one or two moves a week; a hit costs 4, every move must also "
            f"clear a {plan['margin']:.0f}-point margin, and a free transfer still banked "
            f"at the end is worth {plan['ft_value']:.1f}. Later weeks count for less, "
            f"because their projections are less certain. Uses the transfer model's "
            f"projections and current prices; the first week's captain follows the "
            f"captaincy card.")
    return (
        f'<style>{kit_css}</style>'
        f'<section class="card plan-card" id="transfer-plan" tabindex="-1">'
        f'<div class="card-head"><h2>Transfer plan, {span}{components.info_btn()}</h2>'
        f'<span class="sub" hidden>{e(note)}</span></div>'
        f'<div class="card-body"><p class="plan-lede">{lede}</p>{structure}{chip_line}'
        f'<ol class="plan-weeks">{visible}</ol>{later_html}'
        f'<h3 class="plan-sub">Squad by gameweek</h3>'
        f'<div class="plan-gwtabs tabbar" role="tablist" aria-label="Gameweek">{tabs}</div>'
        f'{panels}</div></section>'
    )
