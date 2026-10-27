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


def _move_html(m, w, end_gw, ctx, photos, shirts):
    """One planned move, drawn with the suggested-transfer card: two faces,
    the money on the arrow, and each player's own projection from this week
    to the end of the plan. The XI effect is the week's, in its header -
    two moves in one week are not separable."""
    out_el, in_el = ctx.players[m["out"]], ctx.players[m["in"]]
    week_moves = w["moves"]
    notes = []
    if m["out_cheap"] != m["in_cheap"]:
        partner = next((x for x in week_moves if x is not m
                        and x["out_cheap"] != x["in_cheap"]
                        and x["out_cheap"] != m["out_cheap"]), None)
        if partner and m["out_cheap"]:
            notes.append(f"Restructure with {partner['out_name']} → "
                         f"{partner['in_name']}: the cheap slot moves from "
                         f"{POS_WORD[m['pos']]} to {POS_WORD[partner['pos']]}, "
                         f"which pays for {m['in_name']}")
        elif partner:
            notes.append(f"{m['in_name']} takes the cheap slot, paying for "
                         f"{partner['in_name']}")
        elif m["in_cheap"]:
            notes.append("A cheaper player who frees money")
    if m.get("urgent") == "out":
        notes.append(f"Worth the hit: {out_el['web_name']} is ruled out")
    elif m.get("urgent") == "in":
        notes.append(f"Worth the hit: {in_el['web_name']} is top five in his "
                     f"position on xGI per 90 with a fair fixture next")
    if m["waited"]:
        wt = m["waited"]
        weeks = (f"GW{wt['from_gw']}" if wt["from_gw"] == wt["to_gw"]
                 else f"GW{wt['from_gw']}–{wt['to_gw']}")
        fixtures = ", ".join(_fx(fx) for fx in wt["fixtures"])
        notes.append(f"Waits out {weeks} ({fixtures}), where he projects "
                     f"{wt['loss']:.1f} fewer than {out_el['web_name']}")
    note = "".join(f'<p class="tf-timing">{e(n)}.</p>' for n in notes)
    keeper = m["pos"] == "GKP"
    out_face = components.tf_face(
        photos.get(m["out"]), shirts.get((out_el["team"], keeper)),
        out_el["web_name"], m["out_club"], m["sell"], "tf-out")
    in_face = components.tf_face(
        photos.get(m["in"]), shirts.get((in_el["team"], keeper)),
        in_el["web_name"], m["in_club"], m["price"], "tf-in",
        duties=components.duty_badges(in_el))
    span = max(m["out_pts"], m["in_pts"]) or 1.0
    window = f"GW{w['gw']}" if w["gw"] == end_gw else f"GW{w['gw']}–{end_gw}"
    return (
        '<li class="tf-card plan-move">'
        f'{components.tf_swap(out_face, in_face, m["sell"] - m["price"])}'
        '<div class="tf-numbers">'
        f'<div class="tf-ep"><span>{m["out_pts"]:.1f}</span>'
        f'<span class="tf-track"><i style="width:{m["out_pts"] / span * 100:.0f}%"></i></span></div>'
        f'<div class="tf-span">his own<br>{window}</div>'
        f'<div class="tf-ep tf-ep-in"><span>{m["in_pts"]:.1f}</span>'
        f'<span class="tf-track"><i style="width:{m["in_pts"] / span * 100:.0f}%"></i></span></div>'
        '</div>'
        f'<p class="tf-foot">{e(_fx(w["fixtures"].get(m["in"])))} in GW{w["gw"]}</p>'
        f'{note}</li>'
    )


def _week_html(w, end_gw, ctx, photos, shirts, first_gw, show_bank=True):
    chip = (f'<span class="plan-chip">{e(CHIP_LABEL[w["chip"]])}</span>'
            if w["chip"] else "")
    gain = ""
    if w["moves"] and w["gain"] is not None:
        # The range is in the card title; only a week that starts later than
        # the plan does says its own.
        window = (f"xP to GW{end_gw}" if w["gw"] == first_gw else
                  f"xP, GW{w['gw']}" if w["gw"] == end_gw else f"xP, GW{w['gw']}–{end_gw}")
        gain = (f'<span class="plan-gain"><b class="tnum">{w["gain"]:+.1f}</b> '
                f'{window}{", after the hit" if w["hits"] else ""}</span>')
    bank = f"{w['bank']:.1f}m in the bank" if show_bank else ""
    moves = "".join(_move_html(m, w, end_gw, ctx, photos, shirts) for m in w["moves"])
    body = f'<ul class="tflist plan-moves">{moves}</ul>' if moves else ""
    return (
        f'<li class="plan-week{" plan-roll" if not moves else ""}" id="plan-gw-{w["gw"]}" '
        f'tabindex="-1" data-plan-gw="{w["gw"]}">'
        f'<div class="plan-week-head"><b>GW{w["gw"]}</b>'
        f'<span>{_week_summary(w)}</span>{chip}{gain}'
        f'<span class="plan-bank tnum">{bank}</span>'
        f'<button type="button" class="plan-view" data-show-gw="{w["gw"]}">View squad</button></div>'
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
    changes = "" if w["moves"] else '<p class="plan-changes">No transfers this week.</p>'
    chip = f" &middot; {e(CHIP_LABEL[w['chip']])}" if w["chip"] else ""
    return (
        f'<div class="plan-panel" id="plan-pitch-{w["gw"]}"{"" if first else " hidden"}>'
        f'<p class="plan-panel-head"><span class="tnum">{w["points"]:.1f}</span> xP '
        f'&middot; {d}-{m}-{f}{chip}</p>'
        f'{changes}{_pitch_html(w, ctx, shirts, badges)}</div>'
    )


def plan_card(plan, ctx, shirts, badges, photos=None):
    photos = photos or {}
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
    enablers = plan["enablers"]
    structure = ""
    if enablers:
        names = ", ".join(x["name"] for x in enablers)
        structure = f'<p class="plan-structure">Cheap slots kept: {e(names)}.</p>'
    # Held chips are the chip planner's to report; here only a chip the plan
    # actually plays, or the failure to verify chip history.
    chips = [f"{CHIP_LABEL[w['chip']]} in GW{w['gw']}" for w in weeks if w["chip"]]
    chip_line = ""
    if plan["chips_modelled"]:
        if chips:
            chip_line = f'<p class="plan-chips">{e("; ".join(chips) + ".")}</p>'
    else:
        chip_line = ('<p class="plan-chips">Chip history could not be verified, so no '
                     'chip is planned.</p>')

    end = plan["end_gw"]
    first_gw = weeks[0]["gw"]
    # A roll week that leaves the bank where the week before did has nothing new to say about it.
    quiet = {w["gw"] for prev, w in zip(weeks, weeks[1:])
             if not w["moves"] and w["bank"] == prev["bank"]}

    def render(w):
        return _week_html(w, end, ctx, photos, shirts, first_gw, w["gw"] not in quiet)

    visible = "".join(render(w) for w in weeks[:show])
    later = weeks[show:]
    later_html = ""
    if later:
        planned = sum(len(w["moves"]) for w in later)
        later_html = (
            f'<details class="plan-later"><summary>Later gameweeks, GW{later[0]["gw"]}–'
            f'{later[-1]["gw"]} ({_plural(planned, "planned move")})</summary>'
            f'<ol class="plan-weeks">{"".join(render(w) for w in later)}</ol></details>')

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
            f"roll, or make one or two moves a week. "
            f"Beyond next week's predicted line-up, a player's chance of starting follows "
            f"his last three matches, drifting a quarter of the way back toward his "
            f"season-long rate each week. Uses the transfer model's "
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
