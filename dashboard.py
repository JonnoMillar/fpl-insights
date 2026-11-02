#!/usr/bin/env python3
"""
Renders the squad and mini-league reports as a single self-contained HTML page.

This module assembles the page: build() gathers the data and the cards, render()
wraps them in the shell. The cards live in one module per tab (cards_squad,
cards_planning, cards_league, cards_scout), and the styles and page script in
dashboard.css and dashboard.js.

The look is specified in docs/design.md: purple, night, green, white and a
paper ground; Noto Sans only, tabular figures everywhere; the generated icon
set as one embedded sprite; player cut-outs standing on coloured cards. Two
constraints worth keeping in mind when editing:

* Nothing means something by hue alone. A gain carries its sign or arrow, a
  state changes fill, weight or shape, and a fixture pill prints the opponent
  and the number.
* Green is a fill, never type on white: #00ff87 is about 1.3:1 there.
"""

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import analysis
import captaincy
import chips
import fplapi
import pulse
import elite
import ffs
import components
import odds
import next_action
import next_squad
import planner
import scout
import ticker
import transfers
from analysis import f
from cards_common import LOGO_SVG, e, icon
from cards_squad import (findings_section, pick_team_pitch, pitch,
    player_dialog, player_payload, squad_table)
from cards_planning import (best_xi_card, captaincy_card, chip_planner_card,
    elite_card, kneejerk_card, leader_groups, price_watch_card, scatter,
    verdict_board_card)
from cards_league import (chips_table, differential_card,
    differential_watchlist, differential_watchlist_card, league_position_card,
    league_position_series, league_table, league_week_lede, ownership_cards,
    ownership_carousel, rival_returns, rival_returns_window, rivals_card,
    template_pitch, template_xi)
from cards_scout import scout_section
from cards_plan import plan_card


CSS = (Path(__file__).with_name("dashboard.css")).read_text(encoding="utf-8")

SCATTER_JS = (Path(__file__).with_name("scatter.js")).read_text(encoding="utf-8")
PLAYERVIEW_JS = (Path(__file__).with_name("playerview.js")).read_text(encoding="utf-8")
CAPTAINCY_JS = (Path(__file__).with_name("captaincy.js")).read_text(encoding="utf-8")
LEAGUECHART_JS = (Path(__file__).with_name("leaguechart.js")).read_text(encoding="utf-8")
TICKER_JS = (Path(__file__).with_name("ticker.js")).read_text(encoding="utf-8")
SCOUT_JS = (Path(__file__).with_name("scout.js")).read_text(encoding="utf-8")
PLANVIEW_JS = (Path(__file__).with_name("planview.js")).read_text(encoding="utf-8")

JS = (Path(__file__).with_name("dashboard.js")).read_text(encoding="utf-8")

# The generated icon set, packed by scripts/pack_icons.py into one sprite and
# embedded so the page stays self-contained (CSS masks will not load a file://
# image). A missing sheet leaves the icons blank, never the page.
_ASSETS = Path(__file__).with_name("assets")
try:
    ICON_CSS = (":root{--ico-sheet:url(data:image/png;base64,"
                + base64.b64encode((_ASSETS / "icons.png").read_bytes()).decode("ascii")
                + ")}" + (_ASSETS / "icons.css").read_text(encoding="utf-8"))
except OSError:
    ICON_CSS = ""

# Inline rather than a file so the page stays self-contained: it works opened
# from disk, and the body-only artifact the live site serves carries it too.
# Link previews need an absolute image URL, so this points at the deployed
# copy of docs/og.png (Vercel serves the repo root as static files).
SITE_URL = "https://fpl-insights-jm.vercel.app"
SOCIAL_META = (
    '<meta name="description" content="Expected goals, bookmaker odds and '
    'fixture strength for a Fantasy Premier League squad, turned into '
    'captain, transfer and chip decisions.">'
    '<meta property="og:type" content="website">'
    '<meta property="og:title" content="FPL Insights">'
    '<meta property="og:description" content="The numbers behind the points: '
    'expected goals, odds and fixtures turned into FPL decisions.">'
    f'<meta property="og:image" content="{SITE_URL}/docs/og.png">'
    '<meta property="og:image:width" content="1200">'
    '<meta property="og:image:height" content="630">'
    '<meta name="twitter:card" content="summary_large_image">'
)
FAVICON = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,' + quote(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="8" fill="#00ff87"/>'
        '<g transform="translate(5 9.2) scale(.22)" fill="#37003c">'
        '<path d="M0 62V0H100V62H90V10H10V62Z"/>'
        '<path d="M16.5 40H34.5V62H16.5ZM41 32H59V62H41ZM65.5 20H83.5V62H65.5Z"/></g>'
        '</svg>') + '">'
)


def compact_rank(n):
    """Ranks run to eight figures, and no headline needs all of them."""
    n = abs(int(n))
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m".replace(".0m", "m")
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return f"{n:,}"


def next_week_line(ctx, xi, eps, next_gw):
    """The forward-looking counterpart to week_verdict, for Pick team.

    The same sentence a manager would say out loud, pointed the other way:
    what the eleven is projected to score, where most of it is expected to
    come from, and the one thing that could stop it. Anyone in the eleven
    left out of a published side is that thing, and it leads if it exists -
    a projection is worth nothing if the man carrying it is on the bench."""
    xi_ids = {r.element["id"] for r in xi}
    picked = [(r, ep) for r, ep in (eps or []) if r.element["id"] in xi_ids]
    if not picked:
        return ""
    total = sum(ep["total"] for _r, ep in picked)
    lead_r, lead_ep = max(picked, key=lambda x: x[1]["total"])
    where = "at home to" if lead_ep["home"] else "away at"
    line = (f"Gameweek {next_gw}: this eleven projects "
            f"<b>{total:.1f}</b>, the biggest single piece of it "
            f"{e(lead_r.name)} {where} {e(lead_ep['opponent'])}.")

    benched = [e(r.name) for r in xi if ctx.is_predicted(r.element) is False]
    if benched:
        who = benched[0] if len(benched) == 1 else (
            ", ".join(benched[:-1]) + " and " + benched[-1])
        verb = "is" if len(benched) == 1 else "are"
        line += (f" {who} {verb} not in a predicted eleven, so that number "
                 f"is soft until the team news lands.")
    return line


def week_verdict(ctx, gw, squad_ids, captain_id, points, average, pending):
    """One line on where the week actually stands.

    The tiles say what happened; none of them says whether it was good, and
    a score is meaningless without the average beside it. This is the
    sentence a manager would say out loud - the gap to the average, then the
    single biggest reason for it.

    Whether the round is still running changes the question entirely. With
    players left it is "what needs to happen"; once they have all played it
    is "what happened", and the most useful answer to that is nearly always
    a heavily-owned player who hauled and who you did not have."""
    ev = next((x for x in ctx.events if x["id"] == gw), None)
    if not ev or not points:
        return ""

    if pending:
        n = len(pending)
        who = ", ".join(pending[:3]) + ("&hellip;" if n > 3 else "")
        if average and points < average:
            need = average - points
            return (f"<b>{n}</b> still to play &mdash; {who}. "
                    f"You need <b>{need}</b> more to reach this week's "
                    f"<b>{average}</b> average.")
        return (f"<b>{n}</b> still to play &mdash; {who}. "
                f"You are already past the <b>{average}</b> average."
                if average else f"<b>{n}</b> still to play &mdash; {who}.")

    if not average:
        return ""
    gap = points - average
    frame = (f"<b>{points}</b> against a <b>{average}</b> average, "
             f"{'up' if gap >= 0 else 'down'} <b>{abs(gap)}</b>.")

    # The week's biggest miss: the top scorer, if enough managers owned him
    # that not owning him is a real decision rather than bad luck.
    top = (ev.get("top_element_info") or {})
    tid, tpts = top.get("id"), top.get("points")
    if tid and tid not in squad_ids and tpts:
        el = ctx.players.get(tid)
        owned = f(el.get("selected_by_percent")) if el else 0
        if el and owned >= 15:
            # The same miss means different things either side of the
            # average: below it, it is the explanation; above it, it is
            # what the week could still have been.
            tail = ("and not owning him is most of that gap"
                    if gap < 0 else
                    "and you got there without him")
            return (f"{frame} {e(el['web_name'])} scored <b>{tpts}</b> for the "
                    f"<b>{owned:.0f}%</b> who own him, {tail}.")

    # Failing that, the armband is the next biggest single swing.
    cap = ctx.players.get(captain_id)
    if cap:
        cpts = cap.get("event_points") or 0
        most = ctx.players.get(ev.get("most_captained"))
        if most and most["id"] != captain_id and (most.get("event_points") or 0) > cpts:
            return (f"{frame} {e(cap['web_name'])} returned <b>{cpts}</b> as "
                    f"captain against {e(most['web_name'])}'s "
                    f"<b>{most['event_points']}</b> for the crowd.")
        return (f"{frame} {e(cap['web_name'])} brought "
                f"<b>{cpts * 2}</b> back as captain.")
    return frame


def next_opponent(ctx, team_id, gw, badges):
    """The club's single fixture in gameweek gw: who, where, and the crest."""
    fxs = [fx for fx in ctx.fixtures
           if fx.get("event") == gw and team_id in (fx["team_h"], fx["team_a"])]
    if len(fxs) != 1:
        return None
    fx = fxs[0]
    home = fx["team_h"] == team_id
    opp = fx["team_a"] if home else fx["team_h"]
    return {"name": ctx.teams[opp]["name"], "short": ctx.team_name(opp),
            "home": home, "crest": badges.get(opp)}


# --- page -----------------------------------------------------------------

def source_notice(d):
    missing = [f"{name}: {row['detail']}" for name, row in d.get("source_health", {}).items()
               if not row["ok"]]
    if not missing:
        return ""
    return ('<p class="data-status data-warning" role="status">' + icon("doubtful")
            + '<span>Some data is unavailable. ' + e("; ".join(missing)) + '</span></p>')


def league_hero(d):
    """Where you stand in the mini-league: the place, and the two gaps that
    decide what next week can change - to the leader and to the next place."""
    rows = d.get("standings") or []
    me = next((r for r in rows if r["mine"]), None)
    if not me:
        return ""
    leader = rows[0]
    above = next((r for r in reversed(rows) if r["rank"] < me["rank"]), None)
    below = next((r for r in rows if r["rank"] > me["rank"]), None)
    n = me["rank"]
    place = f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
    tiles = []
    if leader is not me:
        tiles.append(("To the top", leader["total"] - me["total"], f"behind {leader['name']}"))
    else:
        tiles.append(("Lead", me["total"] - (below["total"] if below else me["total"]),
                      f"ahead of {below['name']}" if below else "alone at the top"))
    if above and above is not leader:
        tiles.append(("Next place up", above["total"] - me["total"], f"behind {above['name']}"))
    if below:
        tiles.append(("Cushion", me["total"] - below["total"], f"ahead of {below['name']}"))
    tile_html = "".join(
        f'<div class="stat-tile"><span class="lab">{e(k)}</span><span class="big tnum">{v}</span>'
        f'<span class="stat-note">points {e(note)}</span></div>' for k, v, note in tiles[:2])
    return (f'<section class="league-top" aria-label="Your place in the league">'
            f'<div class="league-place"><span class="lab">{e(d["league_name"])}</span>'
            f'<span class="big tnum">{place}</span><span class="stat-note">of {len(rows)}, '
            f'{me["total"]} points</span>{icon("mini-league", "league-cup")}</div>{tile_html}</section>')


def render(d, standalone=True):
    ctx = d["ctx"]
    title = d["team_name"]
    next_label = f"GW{d['next_gw']}" if d["next_gw"] <= 38 else "no upcoming gameweek"
    eh = d["entry_history"]

    week = d.get("week_projection") or {}
    projected = week.get("owned")
    preview_gain = week.get("gain")
    preview_hit = week.get("hit", 0)
    attention = d.get("attention") or []
    avg = d.get("gw_average")
    gw_pts = eh.get("points")

    def chip(move, text):
        if not move:
            return ""
        return (f'<span class="delta delta-{"up" if move > 0 else "down"}" '
                f'title="{"up" if move > 0 else "down"} {e(text)}">{e(text)}</span>')

    # Rank and league movement: positive means the rank number fell, a climb.
    rank_move = d.get("rank_move")
    rank_chip = chip(rank_move, compact_rank(rank_move) if rank_move else "")
    lg_move = d.get("league_move")
    lg_chip = chip(lg_move, (f"{abs(lg_move)} place{'s' if abs(lg_move) != 1 else ''}"
                             if lg_move else ""))
    gap = ""
    if isinstance(gw_pts, (int, float)) and avg:
        diff = gw_pts - avg
        gap = (f'<span class="delta delta-{"up" if diff >= 0 else "down"}">'
               f'{abs(diff)} {"above" if diff >= 0 else "below"}</span>')
    verdict = f'<p class="score-line">{d["verdict"]}</p>' if d.get("verdict") else ""
    my_rank, size = d.get("my_rank"), d.get("league_size")

    def ordinal(n):
        return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

    projected_html = e(f"{projected:.1f}") if projected else "&ndash;"
    projected_note = f"{e(next_label)}, with captain"
    if projected and week.get("transfers") is not None:
        projected_html = (f'<span data-lineup="owned">{projected:.1f}</span>'
                          f'<span data-lineup="transfers" hidden>{week["transfers"]:.1f}</span>')
        hit_words = f"after a {preview_hit}-point hit" if preview_hit else "with the transfers"
        projected_note = (f'<span data-lineup="owned">{e(next_label)}, with captain</span>'
                          f'<span data-lineup="transfers" hidden>{e(next_label)}, {hit_words}</span>')
    if attention:
        looks = "".join(f'<li>{icon("doubtful")}<span><b>{e(nm)}</b> {e(why)}</span></li>'
                        for nm, why in attention[:3])
        looks = (f'<div class="next-look"><span class="lab">{len(attention)} to check</span>'
                 f'<ul>{looks}</ul></div>')
    else:
        looks = (f'<div class="next-look"><span class="lab">Team news</span>'
                 f'<ul><li>{icon("available")}<span>Nobody in the eleven is flagged.</span></li></ul></div>')
    bank_note = (f"squad sells for {d['sell_value']:.1f}m" if d.get("sell_value")
                 else f"squad {eh.get('value', 0) / 10:.1f}m")
    rank_note = f"rank {d['overall_rank']:,}" if d.get("overall_rank") else "points"
    avg_note = f"<br>{avg} average" if avg else ""

    hero_html = f'''<section class="squad-top" aria-label="Weekly scorecard">
      <div class="score-card">
        <div class="glow" aria-hidden="true"><i></i><i></i></div>
        <span class="lab">Gameweek {d['gw']}</span>
        <div class="score-big"><span class="big tnum">{e(gw_pts if gw_pts is not None else "–")}</span>
          <span class="score-of">points{avg_note}</span>{gap}</div>
        {verdict}
      </div>
      <div class="stat-tile"><span class="lab">Season</span>
        <span class="big tnum">{e(eh.get("total_points", "–"))}</span>
        <span class="stat-note">{rank_note} {rank_chip}</span></div>
      <div class="stat-tile"><span class="lab">{e(d['league_name'])}</span>
        <span class="big tnum">{ordinal(my_rank) if my_rank else "–"}</span>
        <span class="stat-note">{f"of {size}" if size else ""} {lg_chip}</span></div>
      <div class="next-card">
        <div class="next-main"><span class="lab">Up next &middot; {e(next_label)}</span>
          <span class="big tnum">{projected_html}</span>
          <span class="stat-note">projected points, {projected_note}</span></div>
        {looks}
        <div class="next-bank"><span class="big tnum">{eh.get('bank', 0) / 10:.1f}m</span>
          <span class="stat-note">in the bank, {e(bank_note)}</span></div>
      </div>
    </section>'''

    action = d.get("next_action") or {}
    moves = action.get("moves", [])
    target = action.get("target")
    action_title = (f'<a data-dashboard-jump href="#{e(target)}">{e(action["label"])}</a>'
                    if target else e(action.get("label", "Advice unavailable")))

    def opp_words(opp):
        if not opp:
            return "no fixture"
        return f"{opp['name']}, {'home' if opp['home'] else 'away'}"

    slots = []
    for m in d.get("brief_moves") or []:
        out_img = (f'<img class="cut move-old" src="{m["out_photo"]}" alt="">'
                   if m.get("out_photo") else "")
        in_img = (f'<img class="cut move-new" src="{m["in_photo"]}" alt="">'
                  if m.get("in_photo") else "")
        crest = (f'<img src="{m["opp"]["crest"]}" alt="">'
                 if m.get("opp") and m["opp"].get("crest") else "")
        slots.append(
            f'<li class="move-slot">{out_img}<span class="move-arrow">{icon("next")}</span>{in_img}'
            f'<div class="move-names"><span class="move-out">{e(m["out_name"])} out</span>'
            f'<button type="button" class="player-link disp" data-player="{m["in_id"]}">'
            f'{e(m["in_name"])}</button>'
            f'<span>{e(m["in_club"])} &middot; {m["in_price"]:.1f}m</span></div>'
            f'<p class="move-caption">{crest}<span><b>v {e(opp_words(m["opp"]))}.</b> '
            f'{e(m["reason"])}</span></p></li>')
    moves_html = (f'<ul class="move-slots" aria-label="Suggested transfers">{"".join(slots)}</ul>'
                  if slots else "")
    detail = ("" if slots else
              f'<p class="move-detail">{e(action.get("detail", "Supported projections are required."))}</p>')
    gain = action.get("projected_gain")
    gain_html = (f'<span class="move-gain"><b class="big tnum">+{gain:.1f}</b>'
                 f'<span>over {action["horizon"]} gameweeks, after hits</span></span>'
                 if gain is not None else "")
    preview_note = d.get("transfer_preview_note", "Transfer preview unavailable.")
    caveat = "" if d.get("transfer_pick_pitch") else preview_note
    caveat_html = f'<p class="brief-caveat">{e(caveat)}</p>' if caveat else ""
    brief_html = f'''<section class="move-stage" aria-labelledby="decision-title">
      <div class="move-head"><div><span class="lab" id="decision-title">The next move &middot; {e(next_label)}</span>
        <h3 class="brief-action disp">{action_title}</h3></div>{gain_html}</div>
      {detail}{moves_html}
      <div class="brief-links"><a data-dashboard-jump href="#action-method">How it's chosen</a>
        <a data-dashboard-jump href="#transfer-plan">The full plan</a>
        <a data-dashboard-jump href="#chip-planner">Chips</a></div>
      {caveat_html}
    </section>'''

    captain_html = ""
    for mode in ("owned", "transfers"):
        c = (d.get("captains") or {}).get(mode)
        if not c:
            continue
        photo = f'<img class="cut" src="{c["photo"]}" alt="">' if c.get("photo") else ""
        crest = (f'<img src="{c["opp"]["crest"]}" alt="">'
                 if c.get("opp") and c["opp"].get("crest") else "")
        xp = f'{c["xp"]:.1f}' if c.get("xp") is not None else "&ndash;"
        hidden = " hidden" if mode == "transfers" else ""
        captain_html += (
            f'<section class="captain-card" data-lineup="{mode}"{hidden} aria-label="Captain">'
            f'<svg class="ring" aria-hidden="true" viewBox="0 0 200 200"><circle cx="100" cy="100" r="78"/></svg>'
            f'{photo}<span class="lab">{icon("captain")} Captain</span>'
            f'<button type="button" class="player-link disp" data-player="{c["id"]}">{e(c["name"])}</button>'
            f'<span class="cap-opp">{crest}v {e(opp_words(c["opp"]))}</span>'
            f'<span class="cap-xp"><b class="big tnum">{xp}</b><span>projected,<br>before doubling</span></span>'
            f'</section>')
    weekly_gain = ""
    if preview_gain is not None:
        gain_text = f"{preview_gain:+.1f}".replace("-", "−")
        weekly_gain = (f'<span class="preview-gain {"gain-negative" if preview_gain < 0 else "gain-positive"}">'
                       f'{e(next_label)} {gain_text} xP{" after hit" if preview_hit else ""}</span>')

    tab_buttons = "".join(
        f'<button class="tab" role="tab" aria-selected="{"true" if n == 0 else "false"}" '
        f'data-panel="{panel}">{icon(ico)}<span>{label}</span></button>'
        for n, (panel, ico, label) in enumerate((
            ("p-squad", "squad", "Squad"), ("p-market", "planning", "Planning"),
            ("p-league", "mini-league", "League"), ("p-scout", "scout", "Scout"))))
    body = f"""
<nav class="side" aria-label="Dashboard">
  <span class="brand"><span class="brand-mark">{LOGO_SVG}</span>FPL<br>Insights</span>
  <div class="tabs" role="tablist" aria-label="Dashboard sections" aria-orientation="vertical">{tab_buttons}</div>
  <span class="side-gw">GW<b class="tnum">{d['gw']}</b></span>
</nav>
<div class="main">
<header class="topbar"><div class="topbar-in">
  <span class="wordmark">{LOGO_SVG}FPL Insights</span>
  <div class="railwrap" hidden><nav class="rail" aria-label="Sections on this tab"></nav></div>
  <span class="stamp">Gameweek {d['gw']} &middot; {e(d['generated'])}</span>
</div></header>

<div class="wrap">
  <section class="product-intro" aria-labelledby="product-purpose">
    <div>
      <span class="lab">{e(d['manager'])}’s Fantasy Premier League squad</span>
      <h1 id="product-purpose" class="disp">{e(title)}</h1>
    </div>
    <div class="intro-links">
      <a href="https://github.com/JonnoMillar/fpl-insights">Source code <span aria-hidden="true">↗</span></a>
      <details class="about-methods">
        <summary>About &amp; methods</summary>
        <div class="about-copy">
          <p>Built by Jonno Millar to turn the numbers behind the points into captain, transfer and chip decisions. Explore the published squad, compare mini-league results, or use Scout to find and compare players.</p>
          <p>Player statistics come from the public Fantasy Premier League API, including Opta's expected goals and expected assists. Their sum, expected goal involvement (xGI), describes the quality of chances a player takes and creates. Fixtures, market odds and predicted line-ups inform the analysis.</p>
          <p>Projections are estimates. Snapshots refresh on a best-effort schedule.</p>
          <a href="https://github.com/JonnoMillar/fpl-insights#how-it-works">Read about the data and approach <span aria-hidden="true">↗</span></a>
        </div>
      </details>
    </div>
  </section>

  <p class="data-status" role="status" data-generated="{e(d.get('generated_iso', ''))}">{icon("information")}
    <span><span class="data-age">Snapshot: {e(d['generated'])}.</span>
    Advice uses your last published squad and bank, not changes made since. Double gameweeks are not planned.</span></p>
{source_notice(d)}
  <div class="panel" id="p-squad" role="tabpanel">
    <div class="squad-overview">
    {hero_html}
    <div class="move-row">{brief_html}<div class="captain-slot">{captain_html}</div></div>
    <section class="card squad-pitch">
      <div class="team-sheet-head"><div class="card-head"><h2>Starting XI{components.info_btn()}</h2>
        <span class="sub" hidden>Season and Last gameweek use your last published team. Next gameweek selects the best legal XI from your owned squad, then lets you preview the recommended transfers. Player xP is before captain or chip multipliers. Pitch xP uses match histories; the transfer plan uses its season-based scorer. Projected team totals include captain/chip multipliers and any transfer hit. A faded crest means no minutes in GW{d['gw']}.</span>
      </div>
      <div class="pkview tabbar" role="tablist" aria-label="Pitch view">
        <button class="pkbtn" role="tab" aria-selected="true" data-view="ov">Season</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="pk">Next gameweek</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="gw">Last gameweek</button>
      </div>
      </div>
      <div class="pitch-controls">
        <button type="button" data-pkview="pk" hidden class="lineup-toggle" role="switch" aria-checked="false" {'disabled' if not d.get('transfer_pick_pitch') else ''}><span class="lineup-switch" aria-hidden="true"><span class="lineup-thumb"></span></span><span class="toggle-label"><span>Preview transfers</span>{weekly_gain}</span></button>
        <div class="statsel" role="group" aria-label="Figure shown on the pitch">
          <button class="stbtn" data-stat="p" aria-pressed="true">points</button>
          <button class="stbtn" data-stat="g" aria-pressed="false">per game</button>
          <button class="stbtn" data-stat="x" aria-pressed="false">xGI</button>
        </div>
        <button class="epbtn" aria-label="Projected points breakdown" aria-pressed="false" hidden>Breakdown</button>
      </div>
      <div class="pitch-context" aria-live="polite">
        <p data-pkview="ov">Published squad</p>
        <p data-pkview="gw" hidden>Published squad</p>
        <div data-pkview="pk" hidden>
          <div class="lineup-summaries">
            <p data-lineup="owned">{e(d.get('owned_lineup_note', 'Suggested XI unavailable: supported projections are required.'))}</p>
            <p data-lineup="transfers" hidden>{e(d.get('transfer_lineup_note', 'Transfer preview unavailable.'))}</p>
          </div>
          <p class="mobile-exchanges">{e(" · ".join(move["out"].name + " → " + move["in"]["web_name"] for move in moves))}</p>
        </div>
      </div>
      <div class="pitch-panels">
        <div class="pkpanel" data-view="ov">{d['pitch']}</div>
        <div class="pkpanel" data-view="pk" hidden><div class="lineup-variants">
          <div data-lineup="owned">{d['pick_pitch']}</div>
          <div data-lineup="transfers" hidden>{d.get('transfer_pick_pitch', '')}</div>
        </div></div>
      </div>
    </section>
    </div>
    <details class="card collapsible">
      <summary class="card-head"><h2>Squad detail{components.info_btn()}</h2>
        <span class="sub" hidden>Click a column heading to sort. xP is projected points for {next_label} - the one forward-looking column, so you can sort the underlying numbers against what the model expects from them. Next 3 fixtures rated out of ten, higher is better; CAPITALS are home.</span>
      </summary>
      {d['squad_table']}
    </details>
    <div class="chapter"><h2>What the numbers say</h2></div>
    <section>{d['findings']}</section>
  </div>

  <div class="panel" id="p-market" role="tabpanel" hidden>
    <div class="chapter"><h2>Your moves</h2></div>
    {d.get('plan', '')}
    {d.get('deck', '')}
    {d['captaincy']}
    {d['verdicts']}

    <div class="chapter"><h2>Chips and the weeks ahead</h2></div>
    {d['chip_planner'] or '<section class="card" id="chip-planner" tabindex="-1"><div class="card-head"><h2>Chip planner unavailable</h2><span class="subvis">Supported fixture projections and recovered selling prices are required. Check the source status above.</span></div></section>'}
    {d['fixture_runs']}
    {d['ticker']}

    <div class="chapter"><h2>This week</h2></div>
    {d['market']}
    {d['best_xi']}
    {d['kneejerk']}

    <div class="chapter"><h2>The wider market</h2></div>
    {d['leaders']}
    {d['price_watch']}
    {d['scatter']}
    {d['elite']}
    <details class="card collapsible action-method" id="action-method"><summary class="card-head"><h2>How the suggested action is chosen</h2></summary>
      <div class="card-body"><p>The action is the first week of the transfer plan. The plan searches the next eight gameweeks for which moves to make and when: one or two a week, or a roll. Each move must clear a three-point margin on top of any four-point hit; hits are allowed only for an urgent move this week (a starter ruled out, or a signing in the top five for his position on xGI per 90 with a fair next fixture), a free transfer banked at the end is worth 1.5 points, and later weeks count for less because their projections are less certain. It keeps the squad's cheap bench slots: an enabler leaves only for another cheap player, or in a two-move restructure. This is a conservative heuristic, not a calibrated guarantee.</p>
      <p>Bench Boost and Triple Captain are timed inside the plan when their availability is verified, against their best later week this half, and played only when their week beats waiting by two points. Free Hit is highlighted only when its own planner has a strong next-gameweek case; Wildcard is a longer-window decision in the chip planner.</p></div>
    </details>
  </div>

  <div class="panel" id="p-league" role="tabpanel" hidden>
    {league_hero(d)}
    <section class="card">
      <div class="card-head"><h2>{e(d['league_name'])}{components.info_btn()}</h2>
        <span class="sub" hidden>XI xGI is each starter's expected goal involvement per 90, damped down
        for anyone with still little football behind them, summed across the eleven that started - not a
        season total, which measures minutes played more than quality. A big score beside a small xGI
        came from somewhere that will not repeat.</span>
      </div>
      {d['league_table']}
    </section>
    {d['position_chart']}

    <div class="chapter"><h2>What the league owns</h2></div>
    <div class="own-row">{d['template']}<div class="own-side">{d['ownership']}</div></div>
    {d['carousel']}
    {d['differentials']}
    {d['watchlist']}

    <div class="chapter"><h2>How they are playing it</h2></div>
    {d['rivals']}
    <section class="card">
      <div class="card-head"><h2>Chips used{components.info_btn()}</h2>
        <span class="sub" hidden>Two of each per season - one before GW20, one after.</span>
      </div>
      {d['chips']}
    </section>
  </div>

  <div class="panel" id="p-scout" role="tabpanel" hidden>
    {d['scout']}
  </div>


  {d['dialog']}
  <p class="foot"><a href="https://github.com/JonnoMillar/fpl-insights">source and
  phone alerts</a></p>
</div>
</div>
"""
    # Noto Sans is requested as a weight range: the CSS uses 400 to 900, and a
    # narrower request would silently synthesise the heavy weights.
    fonts = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        "family=Noto+Sans:wght@400..900&display=swap\">"
    )
    head = f"<title>FPL Insights · {e(title)}</title>{FAVICON}{SOCIAL_META}{fonts}<style>{CSS}{ICON_CSS}</style>"
    page = (
        f"{head}{body}<script>{JS}</script><script>{SCATTER_JS}</script>"
        f"<script>{PLAYERVIEW_JS}</script><script>{CAPTAINCY_JS}</script>"
        f"<script>{LEAGUECHART_JS}</script><script>{TICKER_JS}</script>"
        f"<script>{SCOUT_JS}</script><script>{PLANVIEW_JS}</script>"
    )
    if not standalone:
        return page
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{head}</head><body>{body}<script>{JS}</script>"
        f"<script>{SCATTER_JS}</script>"
        f"<script>{PLAYERVIEW_JS}</script>"
        f"<script>{CAPTAINCY_JS}</script>"
        f"<script>{LEAGUECHART_JS}</script>"
        f"<script>{TICKER_JS}</script>"
        f"<script>{SCOUT_JS}</script>"
        f"<script>{PLANVIEW_JS}</script></body></html>"
    )


PRICE_HISTORY_PATH = Path(__file__).with_name("price_history.json")
PRICE_HISTORY_DAYS = 8


def _update_price_history(ctx):
    """Record today's prices and return each player's change over the window.

    FPL's API only ever gives the change since the season started
    (cost_change_start) or since today's single recalculation
    (cost_change_event) - there is no "this week" field to read, so the
    Price movement card needs its own memory of what prices were a few days
    ago. One snapshot per calendar day, trimmed to the last
    PRICE_HISTORY_DAYS and committed to the repo alongside the built
    artifact (see build.yml), the same way the artifact itself persists
    between runs. Until this has run daily for about a week, the oldest
    snapshot for a newly-tracked player is today's, so the reported change
    is 0 - a real gap, not a bug, that closes itself within a week of
    shipping this.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        hist = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        hist = {}
    for pid, el in ctx.players.items():
        key = str(pid)
        entries = hist.get(key) or []
        if entries and entries[-1][0] == today:
            entries[-1][1] = el["now_cost"]
        else:
            entries.append([today, el["now_cost"]])
        hist[key] = entries[-PRICE_HISTORY_DAYS:]
    try:
        PRICE_HISTORY_PATH.write_text(json.dumps(hist, separators=(",", ":")),
                                       encoding="utf-8")
    except OSError as ex:
        print(f"[price history] could not save: {ex}")
    weekly = {}
    for pid, el in ctx.players.items():
        entries = hist.get(str(pid)) or []
        baseline = entries[0][1] if entries else el["now_cost"]
        weekly[pid] = (el["now_cost"] - baseline) / 10.0
    return weekly


def projections_export(ctx, proj, gw, market, baselines, eps_by_id):
    """Next gameweek's expected points for every player, as plain JSON.

    Published next to the page (projections.json) so the phone-alert bot in
    the separate fpl-lineup-alert repo can rank substitutions and captain
    picks on this model instead of points per game. Fetching the deployed
    file keeps each repo free of the other's code.

    The owned squad carries the same history-backed number the pitch shows
    (eps_by_id); everyone else gets the bootstrap-only candidate_score, the
    same split the transfer cards use. One gameweek only: "who should start
    this week" is the question, and case_score's windowed total is not it.
    """
    priors = transfers.positional_priors(ctx)
    out = {}
    for el in ctx.players.values():
        s = eps_by_id.get(el["id"]) or transfers.candidate_score(
            el, ctx, proj, gw, market, baselines, priors)
        if s:
            out[str(el["id"])] = round(s["total"], 2)
    return {
        "gw": gw,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "xp": out,
    }


def build(entry_id, league_id, ttl=fplapi.DEFAULT_TTL, gw=None, limit=25,
          elite_depth=elite.PROVEN_POOL_SIZE):
    """Gather everything the page needs."""
    ctx = analysis.Ctx.load(ttl=ttl)
    gw = gw or ctx.last_event_with_picks()
    weekly_price = _update_price_history(ctx)

    picks = analysis.squad_for(entry_id, gw, ctx)
    meta = fplapi.entry(entry_id, ttl=ttl)
    cap = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
    vice = next((p["element"] for p in picks["picks"] if p["is_vice_captain"]), None)

    xi_ids = [p["element"] for p in picks["picks"] if p["position"] <= 11]
    bench_ids = [p["element"] for p in picks["picks"] if p["position"] > 11]
    reports = {pid: analysis.build_player(ctx, pid, ttl=ttl)
               for pid in xi_ids + bench_ids}
    xi = [reports[i] for i in xi_ids]
    bench = [reports[i] for i in bench_ids]

    try:
        matched = pulse.attach(ctx, ttl=ttl)
    except fplapi.FplError as ex:
        fplapi.note("Opta stats", False, str(ex)[:120])
        matched = 0
    if matched:
        print(f"[pulse] {matched} players matched to Premier League Opta stats")

    shirts = {}
    for tid, t in ctx.teams.items():
        for keeper in (False, True):
            uri = fplapi.shirt_data_uri(t["code"], keeper=keeper)
            if uri:
                shirts[(tid, keeper)] = uri

    photos = {}
    for r in xi + bench:
        uri = fplapi.photo_data_uri(r.element)
        if uri:
            photos[r.element["id"]] = uri

    badges, big_badges = {}, {}
    for tid, t in ctx.teams.items():
        uri = fplapi.badge_data_uri(t["code"])
        if uri:
            badges[tid] = uri
            big_badges[tid] = fplapi.badge_data_uri(t["code"], size=200)

    rows, squads, by_name, histories = [], {}, {}, {}
    league_name = "Mini-league"
    if league_id:
        data = fplapi.league_standings(league_id, ttl=ttl)
        league_name = data["league"]["name"]
        rows = data["standings"]["results"][:limit]
        for r in rows:
            try:
                p = analysis.squad_for(r["entry"], gw, ctx)
            except fplapi.FplError:
                continue
            squads[r["entry"]] = p
            by_name[r["entry_name"]] = p
            try:
                histories[r["entry_name"]] = fplapi.entry_history(r["entry"], ttl=ttl)
            except fplapi.FplError:
                pass

    squad_ids = xi_ids + bench_ids
    pw = analysis.price_watch(ctx, squad_ids)
    scatter_pts = analysis.market_scatter_points(ctx, squad_ids)

    proj = ffs.projections(ttl=ttl)
    try:
        odds.build_club_lookup(ctx)
        market_fixtures = odds.league_fixtures(ttl=ttl)
        market = odds.by_club(ctx, ttl=ttl)
    except fplapi.FplError as ex:
        print(f"[odds] skipped: {ex}")
        market, market_fixtures = {}, []
    next_gw = ctx.next_event() or 39  # 39 is an ended season, never a scored fixture
    if next_gw == 39:
        proj, market, market_fixtures = {}, {}, []
    doubles = {}
    for fx in ctx.fixtures:
        if next_gw <= (fx.get("event") or 0) < min(39, next_gw + 8):
            for tid in (fx["team_h"], fx["team_a"]):
                key = (tid, fx["event"])
                doubles[key] = doubles.get(key, 0) + 1
    incomplete = False
    for (tid, event), count in doubles.items():
        if count != 1:
            continue
        fx = next(fx for fx in ctx.fixtures if fx.get("event") == event
                  and tid in (fx["team_h"], fx["team_a"]))
        home = tid == fx["team_h"]
        key = (ctx.team_name(tid), event)
        row = proj.get(key)
        opp = ctx.team_name(fx["team_a"] if home else fx["team_h"])
        if not row or row.get("opp") != opp or (row.get("ven", "H").upper() == "H") != home:
            incomplete = True
            proj.pop(key, None)
    advice_supported = bool(proj) and not incomplete and not any(n > 1 for n in doubles.values())
    fplapi.note("recommendations", advice_supported,
                "single-fixture window" if advice_supported else
                "No upcoming gameweek" if next_gw == 39 else
                "Fixture coverage incomplete; advice withheld" if incomplete and proj else
                "Double gameweeks are not modelled; advice withheld" if proj else
                "Fixture projections unavailable; advice withheld")
    baselines = analysis.team_attack_baselines(ctx)
    # One event_live call per gameweek so far, shared across every position -
    # see scout.season_live. Fails soft like the other optional sections
    # (odds, elite) rather than taking the whole page down with it. xp uses
    # transfers.candidate_score, the same bootstrap-only scorer chips.py
    # uses for market-wide candidate pools (see shared-scorer-architecture
    # memory) - priors computed once here, never inside the per-position loop.
    try:
        scout_live = scout.season_live(ctx, ctx.current_event() or 1, ttl=ttl)
        if any(m.get("multipleFixtures") for matches in scout_live.values() for m in matches):
            fplapi.note("Scout defensive hit rates", False,
                        "Double-fixture weeks excluded; season totals still include them")
        scout_priors = transfers.positional_priors(ctx)
        scout_pools = {
            pos: scout.pool(ctx, pos, scout_live, proj, next_gw=next_gw,
                            market=market, baselines=baselines, priors=scout_priors)
            for pos in scout.POSITIONS
        }
        scout_fixtures = scout.club_fixture_runs(ctx, proj, next_gw)
    except fplapi.FplError as ex:
        print(f"[scout] skipped: {ex}")
        scout_live, scout_pools, scout_fixtures = {}, {}, []
    eps = []
    for r in xi + bench:
        ep = analysis.expected_points(r, ctx, proj, next_gw,
                                      market=market, baselines=baselines)
        if ep:
            eps.append((r, ep))
    eps_by_id = {r.element["id"]: ep for r, ep in eps}
    blank_ids = {r.element["id"] for r in xi + bench if not any(
        fx.get("event") == next_gw and r.element["team"] in (fx["team_h"], fx["team_a"])
        for fx in ctx.fixtures)}
    owned_lineup = next_squad.select(xi + bench, eps_by_id, blank_ids) if advice_supported else None
    cap_matrix = captaincy.matrix(ctx, owned_lineup["xi"], eps_by_id) if owned_lineup else None

    elite_res = None
    if elite_depth:
        try:
            elite_res = elite.compare(ctx, squad_ids, depth=elite_depth, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[elite] skipped: {ex}")

    # --- the week's verdict ------------------------------------------------
    ev_now = next((x for x in ctx.events if x["id"] == gw), None)
    gw_average = (ev_now or {}).get("average_entry_score") or None
    rank_move = None
    try:
        hist = fplapi.entry_history(entry_id, ttl=ttl).get("current", [])
        by_ev = {h["event"]: h for h in hist}
        now_r = (by_ev.get(gw) or {}).get("overall_rank")
        prev_r = (by_ev.get(gw - 1) or {}).get("overall_rank")
        if now_r and prev_r:
            rank_move = prev_r - now_r   # positive is a climb
    except fplapi.FplError as ex:
        print(f"[hero] rank movement unavailable: {ex}")

    # Anyone in the XI whose club has not played this gameweek yet. Drives
    # whether the verdict looks forward or back.
    pending = []
    for r in xi:
        fx = [x for x in ctx.fixtures
              if x.get("event") == gw and r.element["team"] in (x["team_h"], x["team_a"])]
        if fx and not ctx._is_played(fx[0]):
            pending.append(r.name)
    verdict = week_verdict(
        ctx, gw, set(xi_ids + bench_ids), cap,
        picks.get("entry_history", {}).get("points"), gw_average, pending,
    )

    bank = (picks.get("entry_history", {}).get("bank") or 0) / 10.0
    total_sell, sell_values = None, None
    try:
        total_sell, sell_values = analysis.squad_sell_value(entry_id, ctx, xi + bench, ttl=ttl)
        fplapi.note("selling prices", True, "purchase history recovered")
    except fplapi.FplError as ex:
        fplapi.note("selling prices", False, str(ex)[:120])
        print(f"[transfers] unavailable: {ex}")
    moves_available = advice_supported and sell_values is not None
    free_ts = analysis.free_transfers(entry_id, next_gw, ttl=ttl)
    pair_hit = analysis.transfer_cost(2, free_ts)
    print(f"[transfers] {free_ts if free_ts is not None else '?'} free, "
          f"a pair costs {pair_hit}")
    swaps = transfers.suggest(
        ctx, xi + bench, proj, next_gw, market, baselines,
        bank=bank, limit=6, elite=elite_res, sell_values=sell_values,
    ) if moves_available else []
    for sw in swaps:
        el = sw["in"]
        sw["in_club"] = ctx.team_name(el["team"])
        sw["out_photo"] = photos.get(sw["out"].element["id"])
        sw["in_photo"] = fplapi.photo_data_uri(el)
        sw["out_shirt"] = shirts.get(
            (sw["out"].element["team"], sw["out"].pos == "GKP"))
        sw["in_shirt"] = shirts.get((el["team"], ctx.pos(el) == "GKP"))
        sw["opp"] = next_opponent(ctx, el["team"], next_gw, badges)

    pairings = transfers.pair_suggestions(
        ctx, xi + bench, proj, next_gw, market, baselines,
        bank=bank, limit=4, elite=elite_res, hit_cost=pair_hit, sell_values=sell_values,
    ) if moves_available else []
    for pr in pairings:
        for leg in pr["legs"]:
            el = leg["in"]
            leg["out_photo"] = photos.get(leg["out"].element["id"])
            leg["in_photo"] = fplapi.photo_data_uri(el)
            leg["out_shirt"] = shirts.get(
                (leg["out"].element["team"], leg["out"].pos == "GKP"))
            leg["in_shirt"] = shirts.get((el["team"], ctx.pos(el) == "GKP"))

    my_row = next((r for r in rows if r["entry"] == entry_id), None)
    my_name = my_row["entry_name"] if my_row else None
    my_xgi = analysis.squad_underlying(picks, ctx)["xgi"]
    ranked = sorted(
        ((analysis.squad_underlying(p, ctx)["xgi"], n) for n, p in by_name.items()),
        reverse=True,
    )
    xgi_note = "expected involvement of your XI"
    if ranked and my_name:
        place = next((i for i, (_v, n) in enumerate(ranked, 1) if n == my_name), None)
        if place:
            xgi_note = f"{place} of {len(ranked)} in the league"

    own = analysis.league_ownership(by_name) if by_name else {}
    tpl = template_xi(own, by_name, ctx) if own else None
    league_photos = dict(photos)
    if own and my_name:
        for pid, rec in own.items():
            if my_name in rec["owners"] and len(rec["owners"]) == 1:
                league_photos.setdefault(pid, fplapi.photo_data_uri(
                    ctx.players[pid]))
    # The handful of rival-owned scorers the card below actually shows, so
    # this is a few extra portrait requests rather than one per player in
    # the league.
    rivals_rows = rival_returns(own, by_name, ctx, my_name, set(squad_ids))
    RIVALS_WINDOW_WEEKS = 3
    rivals_window_rows = rival_returns_window(
        rows, ctx, my_name, set(squad_ids), gw,
        weeks=RIVALS_WINDOW_WEEKS, ttl=ttl)
    for row in rivals_rows + rivals_window_rows:
        league_photos.setdefault(row["id"], fplapi.photo_data_uri(
            ctx.players[row["id"]]))

    watchlist_rows = []
    if own and proj:
        watchlist_rows = differential_watchlist(
            own, ctx, proj, market, baselines, next_gw, squad_ids)
        for row in watchlist_rows:
            league_photos.setdefault(row["id"], fplapi.photo_data_uri(
                ctx.players[row["id"]]))

    # Same graceful-degradation shape ticker.fixture_ticker already uses
    # for the same reason: if proj never arrived this build, there is
    # nothing honest to recommend, so the whole card skips rather than
    # showing a set of zeroed or misleading cards.
    fh = tc = bb = wc = None
    used = {}
    chips_verified = False
    if advice_supported and total_sell is not None:
        bank_m = bank
        fh = chips.free_hit(ctx, xi, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        tc = chips.triple_captain(ctx, xi, proj, market, baselines, next_gw)
        bb = chips.bench_boost(ctx, bench, proj, market, baselines, next_gw,
                               bank=bank_m, full_squad=xi + bench, sell_values=sell_values)
        wc = chips.wildcard(ctx, xi + bench, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        try:
            used = chips.used_chips_this_half(entry_id, next_gw, ttl=ttl)
            chips_verified = True
        except fplapi.FplError as ex:
            print(f"[chips] chip history unavailable: {ex}")

    # One scoring pass over the whole league, shared by the knee-jerk card
    # and the Buy/Sell/Keep/Avoid board so the two cannot disagree with
    # each other about the same player.
    # `always` is your own fifteen: eligibility decides who is worth signing,
    # not who you already own, and dropping a flagged player from this dict
    # leaves the board holding fourteen - which is not a squad best_xi can
    # field, so every XI-based comparison it makes silently returned zero.
    lg_scores = transfers.league_scores(
        ctx, proj, next_gw, market, baselines,
        always={r.element["id"] for r in xi + bench})
    kj = transfers.kneejerk(ctx, xi + bench, lg_scores, bank=bank, sell_values=sell_values) if moves_available else None
    if kj:
        kj["photo"] = fplapi.photo_data_uri(ctx.players[kj["id"]])
    vb = transfers.verdict_board(ctx, xi + bench, lg_scores, bank=bank, sell_values=sell_values) if moves_available else None

    # The knee-jerk card states in prose that a pair reaches him, but
    # "Suggested pairs" runs its own separate top-gain search and has no
    # reason to have found this specific pairing on its own - the knee-jerk
    # target is a one-week impulse buy, not necessarily one of the best
    # multi-week upgrades in the pool. Built here, once the funder_pair
    # search above has already done the actual sell/buy legwork, and
    # dropped into the same list of cards so "how would I actually get
    # him" has a real answer to look at rather than only a sentence.
    fp = kj.get("funder_pair") if kj else None
    if fp and kj.get("ep") is not None:
        target_el = ctx.players[kj["id"]]
        repl_el = fp["replacement"]
        primary, second = fp["primary"], fp["second"]
        already_shown = any(
            {primary.element["id"], second.element["id"]}
            == {leg["out"].element["id"] for leg in p["legs"]}
            for p in pairings
        )
        if not already_shown:
            primary_gain = kj["ep"] - lg_scores.get(
                primary.element["id"], {}).get("total", 0.0)
            second_gain = fp["replacement_score"]["total"] - lg_scores.get(
                second.element["id"], {}).get("total", 0.0)
            spend = (
                (target_el["now_cost"] + repl_el["now_cost"]) / 10.0
                - sell_values[primary.element["id"]] - sell_values[second.element["id"]]
            )
            own_pool = [transfers._own_pool_row(r, lg_scores[r.element["id"]]["total"])
                        for r in xi + bench if r.element["id"] in lg_scores]
            base_value = transfers._xi_value(own_pool)
            after_pool = [p for p in own_pool if p["id"] not in
                          (primary.element["id"], second.element["id"])]
            after_pool += [transfers._candidate_pool_row(target_el, ctx, kj["ep"]),
                           transfers._candidate_pool_row(repl_el, ctx, fp["replacement_score"]["total"])]
            after_value = transfers._xi_value(after_pool)
            combined_gain = ((after_value - base_value) if after_value is not None and base_value is not None
                             else primary_gain + second_gain)
            combined_gain += transfers.BENCH_AUTOSUB_ALLOWANCE * (primary_gain + second_gain)
            pairings.append({
                "tag": f"Reaches the knee-jerk pick, {target_el['web_name']}",
                "legs": [
                    {"out": primary, "in": target_el, "gain": primary_gain,
                     "out_photo": photos.get(primary.element["id"]),
                     "in_photo": fplapi.photo_data_uri(target_el),
                     "out_shirt": shirts.get(
                         (primary.element["team"], primary.pos == "GKP")),
                     "in_shirt": shirts.get(
                         (target_el["team"], ctx.pos(target_el) == "GKP"))},
                    {"out": second, "in": repl_el, "gain": second_gain,
                     "out_photo": photos.get(second.element["id"]),
                     "in_photo": fplapi.photo_data_uri(repl_el),
                     "out_shirt": shirts.get(
                         (second.element["team"], second.pos == "GKP")),
                     "in_shirt": shirts.get(
                         (repl_el["team"], ctx.pos(repl_el) == "GKP"))},
                ],
                "gain": combined_gain,
                "after_hit": combined_gain - pair_hit,
                "bank_after": bank - spend,
            })
    # The transfer plan: which moves in which week, holding the squad's cheap
    # slots, with Bench Boost/Triple Captain timed inside it. The hero action
    # reads its first week, and the single/pair lists below are tagged with
    # when each move is best made, so the page gives one answer, not three.
    plan = None
    if moves_available:
        cap_first = None
        if cap_matrix:
            top = cap_matrix["candidates"][0]
            cap_first = next((r.element["id"] for r in owned_lineup["xi"]
                              if r.name == top["player"] and r.team == top["team"]), None)
        plan = planner.build(ctx, xi + bench, proj, market, baselines, next_gw, bank,
                             sell_values, free_ts, used if chips_verified else None,
                             captain_first=cap_first, live=scout_live)
        # Portraits for the plan's move cards: the owned side is already
        # loaded, the signings are a few requests, once each.
        for week in plan["weeks"] if plan else ():
            for move in week["moves"]:
                for pid in (move["out"], move["in"]):
                    if pid not in photos:
                        photos[pid] = fplapi.photo_data_uri(ctx.players[pid])
        timing_priors = transfers.positional_priors(ctx)
        for sw in swaps:
            sw["timing"] = planner.timing_note(sw["in"], sw["out"].element, plan, ctx, proj,
                                               market, baselines, timing_priors, next_gw,
                                               live=scout_live)
        for pr in pairings:
            for leg in pr["legs"]:
                leg["timing"] = planner.timing_note(leg["in"], leg["out"].element, plan, ctx,
                                                    proj, market, baselines, timing_priors,
                                                    next_gw, live=scout_live)
    # A genuinely different question from Free Hit's budget-capped "ideal" -
    # see chips.literal_best_xi for why reusing that number here was wrong.
    next_ideal = chips.literal_best_xi(ctx, xi, proj, market, baselines, next_gw)

    action = next_action.choose(plan, free_ts, moves_available, next_gw,
        (("freehit", "Free Hit", fh),), used if chips_verified else None)
    # The brief and preview repeat the plan's first-week moves.
    action["moves"] = [{"out": reports[move["out"]], "in": ctx.players[move["in"]]}
                       for move in action.get("moves", [])]
    chip_name = {"freehit": "Free Hit", "3xc": "Triple Captain", "bboost": "Bench Boost"}.get(action.get("chip"))
    chip_note = chip_name or ""
    if action.get("chip") == "freehit":
        chip_note += " — replacement squad is in the chip planner"
    preview_reports, preview_eps, transfer_lineup = [], {}, None
    preview_blanks = set()
    moves = action.get("moves", [])
    preview_note = "No suggested transfers to preview."
    if owned_lineup and moves:
        try:
            preview_reports = [analysis.build_player(ctx, move["in"]["id"], ttl=ttl) for move in moves]
            changed = next_squad.apply_transfers(xi + bench, preview_reports, moves, bank, sell_values)
            if changed:
                preview_eps = dict(eps_by_id)
                for r in preview_reports:
                    photos[r.element["id"]] = fplapi.photo_data_uri(r.element)
                    ep = analysis.expected_points(r, ctx, proj, next_gw, market=market, baselines=baselines)
                    if ep:
                        preview_eps[r.element["id"]] = ep
                preview_blanks = {r.element["id"] for r in changed if not any(
                    fx.get("event") == next_gw and r.element["team"] in (fx["team_h"], fx["team_a"])
                    for fx in ctx.fixtures)}
                transfer_lineup = next_squad.from_plan(changed, preview_eps, plan["weeks"][0], preview_blanks)
            preview_note = (f"Preview only · {len(moves)} transfer{'s' if len(moves) != 1 else ''} · {analysis.transfer_cost(len(moves), free_ts)}-point hit."
                            if transfer_lineup else "Transfer preview unavailable: a legal, affordable squad and supported projections are required.")
            fplapi.note("transfer preview", bool(transfer_lineup), "Recommended moves verified" if transfer_lineup else preview_note)
        except fplapi.FplError as ex:
            preview_note = "Transfer preview unavailable: incoming player history could not be loaded."
            fplapi.note("transfer preview", False, str(ex)[:120])

    def team_pitch(team, scores, incoming_ids=()):
        if not team:
            return '<p class="lineup-unavailable">Suggested XI unavailable. Supported single-fixture projections for the squad are required. Your published team remains available in Season and Last gameweek.</p>'
        # select() permits missing scores only for confirmed blanks.
        team_eps = [(r, scores.get(r.element["id"], {"total": 0.0})) for r in team["xi"] + team["bench"]]
        return pick_team_pitch(team["xi"], team["bench"], ctx, badges, shirts,
                               team["captain"], team["vice"], proj, market, next_gw, team_eps, incoming_ids)

    def team_note(team, label):
        if not team:
            return "Suggested XI unavailable: supported projections are required."
        note = f"{label} · {'–'.join(map(str, team['formation']))}"
        if label == "Transfer preview" and hit:
            note += f" · {hit}-point hit"
        return note + (f" · {chip_note}" if chip_note else "")

    def team_brief(team):
        if not team or action.get("chip") == "freehit":
            return {}
        player = next(r for r in team["xi"] if r.element["id"] == team["captain"])
        return {"captain": player.name, "captain_id": player.element["id"]}

    owned_total = next_squad.projected_total(owned_lineup, eps_by_id, blank_ids, action.get("chip"))
    transfer_total = next_squad.projected_total(transfer_lineup, preview_eps, preview_blanks, action.get("chip"))
    hit = analysis.transfer_cost(len(moves), free_ts) if transfer_lineup else 0
    week_projection = {"owned": owned_total, "transfers": transfer_total - hit if transfer_total is not None else None,
                       "gain": transfer_total - owned_total - hit if transfer_total is not None and owned_total is not None else None,
                       "hit": hit}

    dialog_eps = eps + [(r, preview_eps.get(r.element["id"])) for r in preview_reports]

    # The faces and crests the Squad tab's move and captain cards stand on.
    brief_moves = []
    for move, reason in zip(moves, [next_action.explain_move(m, ctx, next_gw) for m in moves]):
        out_el, in_el = move["out"].element, move["in"]
        brief_moves.append({
            "out_id": out_el["id"], "out_name": out_el["web_name"],
            "out_photo": photos.get(out_el["id"]),
            "in_id": in_el["id"], "in_name": in_el["web_name"],
            "in_photo": photos.get(in_el["id"]) or fplapi.photo_data_uri(in_el),
            "in_club": ctx.team_name(in_el["team"]), "in_price": in_el["now_cost"] / 10,
            "opp": next_opponent(ctx, in_el["team"], next_gw, badges),
            "reason": reason,
        })
    captains = {}
    for mode, team, scores in (("owned", owned_lineup, eps_by_id),
                               ("transfers", transfer_lineup, preview_eps)):
        if not team or action.get("chip") == "freehit":
            continue
        player = next(r for r in team["xi"] if r.element["id"] == team["captain"])
        ep = scores.get(player.element["id"]) or {}
        captains[mode] = {
            "id": player.element["id"], "name": player.name,
            "photo": photos.get(player.element["id"]),
            "opp": next_opponent(ctx, player.element["team"], next_gw, badges),
            "xp": ep.get("total"),
        }

    return {
        "ctx": ctx,
        "next_action": action,
        "plan": plan_card(plan, ctx, shirts, badges, photos),
        "deck": components.transfer_deck(swaps, pairings, pair_hit),
        "plan_data": plan,
        "captain_summary": cap_matrix["candidates"][0] if cap_matrix and advice_supported else None,
        "gw": gw,
        "team_name": meta.get("name", "My team"),
        "manager": f"{meta.get('player_first_name', '')} "
                   f"{meta.get('player_last_name', '')}".strip(),
        "entry_history": picks.get("entry_history", {}),
        "league_name": league_name,
        "league_size": len(rows),
        "my_rank": my_row["rank"] if my_row else None,
        "standings": [{"rank": r["rank"], "name": r["entry_name"], "total": r["total"],
                       "mine": r["entry"] == entry_id} for r in rows],
        # Standings carry last week's position, so the mini-league gets the
        # same movement arrow the overall rank has. Positive is a climb, to
        # match rank_move - both are "places gained", not "rank delta".
        "league_move": (
            (my_row["last_rank"] - my_row["rank"])
            if my_row and my_row.get("last_rank") else None
        ),
        "my_xgi": my_xgi,
        "xgi_note": xgi_note,
        "pitch": pitch(xi, bench, ctx, badges, shirts, cap, vice, gw=gw),
        "pick_pitch": team_pitch(owned_lineup, eps_by_id),
        "transfer_pick_pitch": team_pitch(transfer_lineup, preview_eps, {r.element["id"] for r in preview_reports}) if transfer_lineup else "",
        "owned_brief": team_brief(owned_lineup),
        "transfers_brief": team_brief(transfer_lineup),
        "week_projection": week_projection,
        "transfer_reasons": [m["reason"] for m in brief_moves],
        "brief_moves": brief_moves,
        "captains": captains,
        "chip_note": chip_note,
        "owned_lineup_note": team_note(owned_lineup, "Current squad"),
        "transfer_lineup_note": team_note(transfer_lineup, "Transfer preview"),
        "transfer_preview_note": preview_note,
        "chip_planner": chip_planner_card(fh, tc, bb, wc, used, xi, bench,
                                          ctx, badges, shirts, proj, market,
                                          next_gw, plan=plan),
        "best_xi": best_xi_card(next_ideal, ctx, set(squad_ids), next_gw) if advice_supported else "",
        "kneejerk": kneejerk_card(kj, gw),
        "verdicts": verdict_board_card(vb, next_gw),
        "captaincy": captaincy_card(cap_matrix),
        "squad_table": squad_table(xi + bench, ctx, cap, vice,
                                   proj, market, next_gw,
                                   eps_by_id=eps_by_id),
        "ticker": ticker.fixture_ticker(xi + bench, ctx, proj, next_gw,
                                        market=market),
        "fixture_runs": ticker.fixture_run_summary(xi + bench, ctx, proj,
                                                    market, next_gw, weeks=6,
                                                    badges=big_badges),
        "market": ticker.odds_insights(market_fixtures, xi, ctx, proj, next_gw),
        "leaders": components.stat_leaders(leader_groups(ctx, squad_ids), title="Season leaders"),
        "dialog": player_dialog([
            player_payload(r, ctx, proj, ep, next_gw, photos) for r, ep in dialog_eps
        ] + [
            player_payload(r, ctx, proj, None, next_gw, photos)
            for r in xi + bench if not any(r is q for q, _ in eps)
        ]),
        "findings": findings_section(
            analysis.build_findings(list(reports.values()), ctx),
            list(reports.values()), ctx, proj, market, next_gw,
            weekly_price=weekly_price,
            xi_ids={r.element["id"] for r in xi}),
        "price_watch": price_watch_card(pw),
        "scatter": scatter(scatter_pts),
        "league_table": (league_week_lede(rows, squads, ctx, entry_id, gw)
                         + league_table(rows, squads, ctx, entry_id)) if rows else "",
        "position_chart": league_position_card(
            league_position_series(histories, my_name)),
        "ownership": ownership_cards(own, by_name, ctx, my_name) if own else "",
        "carousel": ownership_carousel(own, by_name, ctx, my_name) if own else "",
        "template": template_pitch(tpl, ctx, shirts, my_name, set(squad_ids)),
        "differentials": differential_card(own, by_name, ctx, my_name, league_photos),
        "watchlist": differential_watchlist_card(
            watchlist_rows, league_photos, transfers.TRANSFER_HORIZON_WEEKS),
        "rivals": rivals_card(rivals_rows, rivals_window_rows,
                              max(0, len(by_name) - 1), league_photos,
                              weeks=RIVALS_WINDOW_WEEKS),
        "elite": elite_card(elite_res, ctx),
        "chips": chips_table(histories) if histories else "",
        "scout": scout_section(scout_pools, scout_fixtures, set(squad_ids)),
        "next_gw": next_gw,
        "projections": projections_export(ctx, proj if advice_supported else {},
                                          next_gw if advice_supported else None,
                                          market if advice_supported else {}, baselines, eps_by_id if advice_supported else {}),
        "overall_rank": meta.get("summary_overall_rank"),
        "gw_average": gw_average,
        "rank_move": rank_move,
        "verdict": verdict,
        "next_line": next_week_line(ctx, xi, eps, next_gw) if advice_supported else "",
        "projected_xi": owned_lineup["value"] if owned_lineup else None,
        "sell_value": total_sell,
        # Anyone you would want to know about before the deadline, each with
        # the reason. A tile that names a player and not what is wrong with
        # him sends you hunting through three cards to find out.
        "attention": [
            (r.name, (r.availability[0] or "predicted bench"))
            for r in xi
            if r.availability[0] or ctx.is_predicted(r.element) is False
        ],
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "generated_iso": datetime.now(timezone.utc).isoformat(),
        "source_health": dict(fplapi.HEALTH),
    }
