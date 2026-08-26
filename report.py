#!/usr/bin/env python3
"""
Text rendering for the squad and mini-league reports.

Kept separate from analysis.py so the numbers can be reused (a notebook, a
push notification, a CSV) without dragging the formatting along.
"""

import analysis
from analysis import f, per90


def rule(char="-", width=100):
    return char * width


def header(title, width=100):
    return f"\n{title}\n{rule('=', width)}"


def fmt_row(cols, widths, aligns=None):
    aligns = aligns or ["<"] * len(cols)
    return "  ".join(
        f"{str(c)[:w]:{a}{w}}" for c, w, a in zip(cols, widths, aligns)
    )


# --- squad ----------------------------------------------------------------

SQUAD_COLS = ["POS", "PLAYER", "TM", "PRICE", "OWN%", "MIN", "PTS",
              "xG", "xA", "xGI", "xGI/90", "DC/90", "NEXT 3"]
SQUAD_W = [3, 16, 4, 5, 5, 4, 4, 5, 5, 5, 6, 5, 24]
SQUAD_A = ["<", "<", "<", ">", ">", ">", ">", ">", ">", ">", ">", ">", "<"]


def squad_table(reports, ctx, title, captain_id=None, vice_id=None):
    out = [header(title)]
    out.append(fmt_row(SQUAD_COLS, SQUAD_W, SQUAD_A))
    out.append(rule())
    for r in reports:
        el = r.element
        suffix = " (C)" if el["id"] == captain_id else (" (v)" if el["id"] == vice_id else "")
        out.append(
            fmt_row(
                [
                    r.pos,
                    r.name + suffix,
                    r.team,
                    f"{r.price:.1f}",
                    f"{r.owned:.0f}",
                    r.minutes,
                    r.points,
                    f"{r.xg:.2f}",
                    f"{r.xa:.2f}",
                    f"{r.xgi:.2f}",
                    f"{r.xgi90:.2f}" if r.minutes else "-",
                    f"{r.defcon90:.1f}" if r.minutes and r.pos != "GKP" else "-",
                    ctx.fixture_str(el["team"], 3),
                ],
                SQUAD_W,
                SQUAD_A,
            )
        )
    return "\n".join(out)


def match_log(r, limit=6):
    """The per-match xG/xA rows - the thing FPL's own UI will not show you."""
    rows = sorted(r.history, key=lambda x: x["round"], reverse=True)[:limit]
    if not rows:
        return f"  {r.name}: no matches played yet this season"
    out = [f"  {r.name} ({r.pos}, {r.team})"]
    out.append(
        "    "
        + fmt_row(
            ["GW", "OPP", "H/A", "MIN", "G", "A", "xG", "xA", "xGI", "DC", "BPS", "PTS"],
            [3, 4, 3, 4, 2, 2, 5, 5, 5, 3, 4, 4],
            ["<", "<", "<", ">", ">", ">", ">", ">", ">", ">", ">", ">"],
        )
    )
    for h in reversed(rows):
        out.append(
            "    "
            + fmt_row(
                [
                    h["round"],
                    _opp_name(h),
                    "H" if h["was_home"] else "A",
                    h["minutes"],
                    h["goals_scored"],
                    h["assists"],
                    f"{f(h['expected_goals']):.2f}",
                    f"{f(h['expected_assists']):.2f}",
                    f"{f(h['expected_goal_involvements']):.2f}",
                    h.get("defensive_contribution", 0),
                    h["bps"],
                    h["total_points"],
                ],
                [3, 4, 3, 4, 2, 2, 5, 5, 5, 3, 4, 4],
                ["<", "<", "<", ">", ">", ">", ">", ">", ">", ">", ">", ">"],
            )
        )
    return "\n".join(out)


_OPP_CACHE = {}


def _opp_name(h):
    return _OPP_CACHE.get(h["opponent_team"], str(h["opponent_team"]))


def set_opponent_names(ctx):
    _OPP_CACHE.clear()
    for tid, t in ctx.teams.items():
        _OPP_CACHE[tid] = t["short_name"]


# --- findings -------------------------------------------------------------

def findings(reports, ctx):
    """Render the shared structured findings as text."""
    blocks = []
    for fnd in analysis.build_findings(reports, ctx):
        head = fnd["title"].upper()
        if fnd["note"]:
            head += f"  ({fnd['note']})"
        body = "\n".join(f"    {item}" for item in fnd["items"])
        blocks.append(f"{head}\n{body}")
    return "\n\n".join(blocks)


def captain_check(xi, captain_id):
    """Did the armband go on the best underlying option in the XI?

    Judged on expected involvement per 90, not on points scored - grading a
    captaincy call by its outcome just rewards luck after the fact."""
    if not captain_id:
        return ""
    cap = next((r for r in xi if r.element["id"] == captain_id), None)
    if not cap:
        return ""
    ranked = sorted(
        (r for r in xi if r.minutes), key=lambda r: -r.xgi90
    )
    if not ranked:
        return ""
    best = ranked[0]
    lines = [header("CAPTAINCY")]
    place = next((i for i, r in enumerate(ranked, 1) if r.element["id"] == captain_id), None)
    lines.append(
        f"  Captain: {cap.name} - xGI/90 {cap.xgi90:.2f}, "
        f"ranked {place} of {len(ranked)} in your XI"
    )
    if best.element["id"] != captain_id:
        lines.append(
            f"  Highest underlying in the XI: {best.name} ({best.xgi90:.2f}/90)"
        )
    lines.append(
        f"  Captain returned {cap.points} pts this season "
        f"(doubled where the armband applied)."
    )
    return "\n".join(lines)


def bench_check(picks, ctx):
    """Points left on the bench, and by whom - the cheapest recurring loss in
    FPL and one you can only see after the fact."""
    eh = picks.get("entry_history", {})
    on_bench = eh.get("points_on_bench")
    if not on_bench:
        return ""
    lines = [header("BENCH")]
    lines.append(f"  {on_bench} points left on the bench this gameweek.")
    bench = [p for p in picks["picks"] if p["position"] > 11]
    xi = [p for p in picks["picks"] if p["position"] <= 11]

    def pts(p):
        el = ctx.players.get(p["element"], {})
        return el.get("event_points", 0)

    for p in sorted(bench, key=lambda p: -pts(p)):
        el = ctx.players.get(p["element"], {})
        if pts(p) <= 0:
            continue
        beaten = [q for q in xi if pts(q) < pts(p)
                  and q["element_type"] == p["element_type"]]
        note = ""
        if beaten:
            names = ", ".join(ctx.players[q["element"]]["web_name"] for q in beaten[:3])
            note = f"  - outscored {names}"
        lines.append(f"    {el.get('web_name', '?'):16s} {pts(p)} pts{note}")
    return "\n".join(lines)


# --- mini-league ----------------------------------------------------------

def standings_table(rows, squads, ctx, me=None):
    out = [header("MINI-LEAGUE STANDINGS")]
    cols = ["#", "TEAM", "MANAGER", "GW", "TOTAL", "CHIP", "BENCH", "HITS", "XI xGI"]
    w = [3, 24, 20, 4, 6, 7, 6, 5, 7]
    a = ["<", "<", "<", ">", ">", "<", ">", ">", ">"]
    out.append(fmt_row(cols, w, a))
    out.append(rule())
    for r in rows:
        picks = squads.get(r["entry"])
        chip = bench = hits = ""
        xgi = ""
        if picks:
            chip = picks.get("active_chip") or "-"
            eh = picks.get("entry_history", {})
            bench = eh.get("points_on_bench", "")
            hits = eh.get("event_transfers_cost", "")
            xgi = f"{analysis.squad_underlying(picks, ctx)['xgi']:.1f}"
        marker = " <" if me and r["entry"] == me else ""
        out.append(
            fmt_row(
                [
                    r["rank"],
                    r["entry_name"] + marker,
                    r["player_name"],
                    r["event_total"],
                    r["total"],
                    chip,
                    bench,
                    hits,
                    xgi,
                ],
                w,
                a,
            )
        )
    out.append(
        "\n  XI xGI = season expected goal involvements of the 11 that started. "
        "\n  High score + low xGI means the points came from somewhere that will not repeat."
    )
    return "\n".join(out)


def ownership_report(own, squads, ctx, my_entry_name):
    n = len(squads)
    out = [header("WHO OWNS WHAT")]

    def name_of(pid):
        el = ctx.players.get(pid)
        return f"{el['web_name']} ({ctx.team_name(el['team'])})" if el else str(pid)

    mine = {pid for pid, r in own.items() if my_entry_name in r["owners"]}

    # template: owned by most of the league
    template = sorted(
        (p for p, r in own.items() if len(r["owners"]) >= max(2, n * 0.5)),
        key=lambda p: -len(own[p]["owners"]),
    )
    if template:
        out.append(f"\nLEAGUE TEMPLATE (owned by at least half of {n} managers)")
        for pid in template:
            held = "you own" if pid in mine else "YOU DO NOT OWN"
            out.append(
                f"    {name_of(pid):28s} {len(own[pid]['owners'])}/{n} managers"
                f"   [{held}]"
            )

    # my differentials
    diffs = sorted(
        (p for p in mine if len(own[p]["owners"]) == 1),
        key=lambda p: -f(ctx.players[p]["expected_goal_involvements"]),
    )
    if diffs:
        out.append("\nYOUR DIFFERENTIALS (nobody else in the league owns them)")
        for pid in diffs:
            el = ctx.players[pid]
            out.append(
                f"    {name_of(pid):28s} {el['total_points']:>3} pts, "
                f"xGI {f(el['expected_goal_involvements']):.2f}, "
                f"{f(el['selected_by_percent']):.0f}% owned overall"
            )

    # what the league has that you don't
    gaps = sorted(
        (p for p, r in own.items() if p not in mine and len(r["owners"]) >= max(2, n * 0.4)),
        key=lambda p: -ctx.players[p]["total_points"] if p in ctx.players else 0,
    )
    if gaps:
        out.append("\nTHE LEAGUE HAS THESE AND YOU DO NOT")
        for pid in gaps:
            el = ctx.players[pid]
            out.append(
                f"    {name_of(pid):28s} {len(own[pid]['owners'])}/{n} own, "
                f"{el['total_points']:>3} pts, xGI {f(el['expected_goal_involvements']):.2f}"
            )

    # captaincy
    caps = {}
    for pid, r in own.items():
        for c in r["captains"]:
            caps.setdefault(pid, []).append(c)
    if caps:
        out.append("\nCAPTAIN PICKS")
        for pid, who in sorted(caps.items(), key=lambda kv: -len(kv[1])):
            el = ctx.players[pid]
            out.append(
                f"    {name_of(pid):28s} {len(who)}/{n}: {', '.join(who)}"
                f"   ({el['event_points']} pts this GW)"
            )
    return "\n".join(out)


def chips_report(histories, ctx):
    """Chips are the biggest single swing in a mini-league and they are
    public. Knowing a rival has already burned a Bench Boost is worth more
    than knowing his score."""
    out = [header("CHIPS USED")]
    all_chips = ["wildcard", "freehit", "bboost", "3xc"]
    cols = ["MANAGER"] + [c.upper() for c in all_chips]
    w = [24, 14, 14, 14, 14]
    out.append(fmt_row(cols, w))
    out.append(rule())
    for name, h in histories.items():
        used = {}
        for c in h.get("chips", []):
            used.setdefault(c["name"], []).append(str(c["event"]))
        out.append(
            fmt_row(
                [name] + [
                    ("GW" + ",".join(used[c])) if c in used else "-"
                    for c in all_chips
                ],
                w,
            )
        )
    out.append(
        "\n  Two of each chip exist per season (one usable GW1-19, one GW20-38)."
    )
    return "\n".join(out)
