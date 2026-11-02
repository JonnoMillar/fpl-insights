"""
The League tab's "Your season" chapter: a night band of season figures, the
best and worst transfer as cut-out cards, the other moves as a table, and the
weeks the armband cost most. Input is season.review(); nothing is fetched.
"""

from cards_common import e, icon
import components
from season import FORM_WEEKS

CHIP_NAMES = {"3xc": "Triple Captain", "bboost": "Bench Boost",
              "freehit": "Free Hit", "wildcard": "Wildcard"}
CHIP_ICONS = {"3xc": "triple-captain", "bboost": "bench-boost",
              "freehit": "free-hit", "wildcard": "wildcard"}


def signed(n):
    """+5, −3 (a real minus sign), 0."""
    return f"+{n}" if n > 0 else f"−{-n}" if n < 0 else "0"


def _form(v):
    return "–" if v is None else f"{v:.1f}"


def _face(p, cls=""):
    if not p.get("photo"):
        return f'<span class="face sr-face {cls}" aria-hidden="true"></span>'
    return f'<img class="face sr-face {cls}" src="{p["photo"]}" alt="" loading="lazy">'


def _hero(row, players, best):
    pin, pout = players[row["in"]], players[row["out"]]
    cut = (f'<img class="cut sr-cut" src="{pin["photo"]}" alt="" loading="lazy">'
           if pin.get("photo") else "")
    hit = f'<div><dt>Hit</dt><dd>−{row["hit"]}</dd></div>' if row["hit"] else ""
    return (
        f'<article class="sr-hero {"sr-best" if best else "sr-worst"}">{cut}'
        f'<span class="lab">{"Best" if best else "Worst"} move · GW{row["gw"]}</span>'
        f'<h3 class="disp">{e(pin["name"])}</h3>'
        f'<span class="sr-for">{_face(pout, "sr-out")}for {e(pout["name"])}</span>'
        f'<span class="sr-net"><b class="big tnum">{signed(row["net"])}</b>'
        f'<span>pts over {row["weeks"]} GW{"s" if row["weeks"] != 1 else ""}</span></span>'
        f'<dl class="sr-figs">'
        f'<div><dt>{e(pin["name"])}</dt><dd>{row["pts_in"]}</dd></div>'
        f'<div><dt>{e(pout["name"])}</dt><dd>{row["pts_out"]}</dd></div>{hit}'
        f'<div><dt>Form</dt><dd>{_form(row["form_before"])} → {_form(row["form_after"])}</dd></div>'
        f'</dl></article>')


def _move_row(row, players):
    pin, pout = players[row["in"]], players[row["out"]]
    hit = f' <span class="sr-hit">−{row["hit"]}</span>' if row["hit"] else ""
    tone = "up" if row["net"] > 0 else "down" if row["net"] < 0 else "flat"
    return (
        f'<tr><td><span class="sr-pair">{_face(pout, "sr-out")}{_face(pin)}'
        f'<span class="sr-names"><b>{e(pin["name"])}</b><span>for {e(pout["name"])} · GW{row["gw"]}</span></span></span></td>'
        f'<td class="tnum">{row["pts_in"]}–{row["pts_out"]}{hit}</td>'
        f'<td class="tnum">{_form(row["form_before"])} → <b>{_form(row["form_after"])}</b></td>'
        f'<td><span class="delta delta-{tone}">{signed(row["net"])}</span></td></tr>')


def _tile(label, big, note, ico):
    return (f'<li class="glass sr-tile">{icon(ico, "sr-ico")}<span class="lab">{e(label)}</span>'
            f'<b class="big tnum">{big}</b><span class="sr-note">{note}</span></li>')


def season_section(review):
    if not review:
        return ""
    players, ledger, caps = review["players"], review["ledger"], review["captaincy"]
    net = sum(r["net"] for r in ledger)
    lost = sum(r["lost"] for r in caps)
    best_weeks = sum(1 for r in caps if r["lost"] == 0)
    gains = [c for c in review["chips"] if c["gain"] is not None]
    chips_note = " · ".join(f'{CHIP_NAMES.get(c["name"], c["name"])} GW{c["gw"]}'
                            for c in review["chips"]) or "none played"
    chip_ico = CHIP_ICONS.get(review["chips"][0]["name"], "wildcard") if review["chips"] else "wildcard"
    tiles = "".join([
        _tile("Transfers", signed(net), f'{len(ledger)} moves · {review["hits"]} pts in hits', "transfers"),
        _tile("Armband", signed(-lost), f"best pick {best_weeks} of {len(caps)} weeks", "captain"),
        _tile("Bench", review["bench"], "pts left on it", "bench-boost"),
        _tile("Chips", signed(sum(c["gain"] for c in gains)) if gains else "–", e(chips_note), chip_ico),
    ])
    band = (
        f'<section class="night-band sr-band" aria-label="Season figures">'
        f'<div class="glow" aria-hidden="true"><i></i><i></i><i></i></div>'
        f'<span class="lab">To GW{review["upto"]}</span>'
        f'<ul class="sr-tiles">{tiles}</ul></section>')

    moves = ""
    if ledger:
        ranked = sorted(ledger, key=lambda r: (-r["net"], r["gw"]))
        heroes = [_hero(ranked[0], players, True)]
        if len(ranked) > 1 and ranked[-1]["net"] < ranked[0]["net"]:
            heroes.append(_hero(ranked[-1], players, False))
        rest = ranked[1:-1] if len(heroes) == 2 else ranked[1:]
        table = ""
        if rest:
            # Past six, the next best and worst three stay out; the rest wait
            # behind a disclosure so the table does not grow all season.
            shown, more = (rest, []) if len(rest) <= 6 else (rest[:3] + rest[-3:], rest[3:-3])
            body = "".join(_move_row(r, players) for r in shown)
            extra = (f'<details class="sr-more"><summary>All {len(ranked)} moves</summary>'
                     f'<table class="sr-table"><tbody>{"".join(_move_row(r, players) for r in more)}</tbody></table></details>'
                     if more else "")
            table = (
                f'<section class="card sr-list">'
                f'<div class="card-head"><h2>Other moves{components.info_btn()}</h2>'
                f'<span class="sub" hidden>Points scored by the signing against the player sold, '
                f'over every finished gameweek the signing stayed in your squad, less any hit. '
                f'Raw points: captaincy and the bench are ignored. Form is points per gameweek in the '
                f'{FORM_WEEKS} gameweeks before the move, then per gameweek since.</span></div>'
                f'<div class="scroll"><table class="sr-table"><thead><tr><th>Move</th><th>Pts</th>'
                f'<th>Form</th><th>Net</th></tr></thead><tbody>{body}</tbody></table></div>{extra}</section>')
        moves = f'<div class="sr-heroes">{"".join(heroes)}</div>{table}'

    misses = sorted((r for r in caps if r["lost"] > 0), key=lambda r: (-r["lost"], r["gw"]))[:3]
    armband = ""
    if misses:
        rows = "".join(
            f'<li><span class="sr-gw">GW{r["gw"]}</span>'
            f'<span class="sr-pick">{_face(players[r["captain"]])}<span><b>{e(players[r["captain"]]["name"])}</b>'
            f'<span class="tnum">{r["cap_pts"]} pts{" · ×3" if r["mult"] == 3 else ""}</span></span></span>'
            f'<span class="sr-vs">v</span>'
            f'<span class="sr-pick">{_face(players[r["best"]])}<span><b>{e(players[r["best"]]["name"])}</b>'
            f'<span class="tnum">{r["best_pts"]} pts</span></span></span>'
            f'<span class="delta delta-down">{signed(-r["lost"])}</span></li>'
            for r in misses)
        armband = (
            f'<section class="card sr-caps">'
            f'<div class="card-head"><h2>Armband misses{components.info_btn()}</h2>'
            f'<span class="sub" hidden>The weeks your captain scored least against the best scorer in '
            f'your starting XI. The figure is the points the armband would have added, doubled or '
            f'tripled as it was that week. The vice counts when the captain did not play.</span></div>'
            f'<ul class="sr-misses">{rows}</ul></section>')

    return (f'<div class="chapter"><h2>Your season</h2></div>{band}{moves}{armband}')
