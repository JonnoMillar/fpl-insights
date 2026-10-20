#!/usr/bin/env python3
"""
Renders the squad and mini-league reports as a single self-contained HTML page.

This module assembles the page: build() gathers the data and the cards, render()
wraps them in the shell. The cards live in one module per tab (cards_squad,
cards_planning, cards_league, cards_scout), and the styles and page script in
dashboard.css and dashboard.js.

Colour is FPL's own - the deep purple and the bright green the game is
actually recognised by - because a tool read alongside the site it draws from
should look related to it. What changed is how that colour is spent.

The page used to open on a 135-degree three-stop gradient, purple bleeding
through lilac into green. That is the default hero of every generated
dashboard, and it was the thing that made this one look generated. It is
gone. Purple is now structure and ink, green is one accent used flat, and
the character comes from type and layout instead of from a colour wash:

* Type is Archivo across its width axis - expanded for headings, normal for
  body, so the contrast comes from width rather than from a second family -
  with IBM Plex Mono on every figure, tabular, so columns of stats align on
  the digit the way a results service does.
* One delta chip carries every number that has a good or bad reading, rather
  than each card inventing its own arrow.
* Findings read as a mono subject tag beside ordinary prose, not as a bold
  black line with grey underneath it, which is the pattern that made every
  card on the page look like every other card.

Two constraints worth keeping in mind when editing:

* Green is a fill, never type. #01fc7a is 1.35:1 on white, so anything that
  lands on text uses --accent-ink / --good-ink instead.
* Difficulty pills always carry a visible opponent and number. Several steps
  on the ramp are too close in luminance to carry meaning by fill alone, so
  the label does the work and the colour only makes a run visible down a
  column.

Light only. There is no dark theme and no toggle - the page is read in
daylight before a deadline, and carrying a second full palette meant every
new colour had to be drawn twice and kept in step.
"""

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
import scout
import ticker
import transfers
from analysis import f
from cards_common import e
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


CSS = (Path(__file__).with_name("dashboard.css")).read_text(encoding="utf-8")

SCATTER_JS = (Path(__file__).with_name("scatter.js")).read_text(encoding="utf-8")
PLAYERVIEW_JS = (Path(__file__).with_name("playerview.js")).read_text(encoding="utf-8")
CAPTAINCY_JS = (Path(__file__).with_name("captaincy.js")).read_text(encoding="utf-8")
LEAGUECHART_JS = (Path(__file__).with_name("leaguechart.js")).read_text(encoding="utf-8")
TICKER_JS = (Path(__file__).with_name("ticker.js")).read_text(encoding="utf-8")
SCOUT_JS = (Path(__file__).with_name("scout.js")).read_text(encoding="utf-8")

JS = (Path(__file__).with_name("dashboard.js")).read_text(encoding="utf-8")

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
        '<rect width="32" height="32" rx="7" fill="#37003c"/>'
        '<path d="M7 22l6-7 5 4 7-10" fill="none" stroke="#01fc7a" '
        'stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>'
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


# --- page -----------------------------------------------------------------

def source_notice(d):
    missing = [f"{name}: {row['detail']}" for name, row in d.get("source_health", {}).items()
               if not row["ok"]]
    if not missing:
        return ""
    return ('<p class="data-status data-warning" role="status">Some data is unavailable. '
            + e("; ".join(missing)) + '</p>')


def render(d, standalone=True):
    ctx = d["ctx"]
    title = d["team_name"]
    next_label = f"GW{d['next_gw']}" if d["next_gw"] <= 38 else "no upcoming gameweek"
    eh = d["entry_history"]

    # What belongs here is what you would act on, not what happened. Squad
    # value and points-on-bench were retrospective, and XI xGI was the weakest
    # number on the page - a season total over one match, never adjusted for
    # minutes. Replaced by the two forward-looking things: what the squad is
    # projected to score, and who is not going to play.
    projected = d.get("projected_xi")
    attention = d.get("attention") or []

    # A score with no average beside it, and a rank with no direction, are
    # both half a fact. Both go in as delta chips - the same component the
    # rest of the page uses - deliberately smaller than the figure they
    # qualify, so the tile still reads as one number at a glance.
    # The average belongs beside the score as a number, not as a difference
    # from it - "89 against a 79 average" is a comparison anyone makes
    # instantly, where "10 v avg" made them do the arithmetic backwards to
    # find out what the average even was.
    avg = d.get("gw_average")
    gw_note = f"GW{d['gw']} &middot; {avg} average" if avg else f"GW{d['gw']}"

    move = d.get("rank_move")
    rank_chip = ""
    if move:
        # Positive means the rank number fell, which is a climb.
        rank_chip = (f'<span class="delta delta-{"up" if move > 0 else "down"}">'
                     f'{compact_rank(move)}</span>')
    lg_move = d.get("league_move")
    lg_chip = ""
    if lg_move:
        lg_chip = (f'<span class="delta delta-{"up" if lg_move > 0 else "down"}">'
                   f'{abs(lg_move)}</span>')

    # Two of the six tiles get a tone - not all of them, since a hero row
    # in six different colours would just be noise. These are the two
    # where the number alone already answers "good or bad", so the colour
    # repeats a judgement the reader is about to make anyway rather than
    # asserting a new one: the gameweek score against the average sitting
    # right beside it, and whether anything actually needs the manager's
    # attention this week.
    gw_pts = eh.get("points")
    gw_tone = ""
    if isinstance(gw_pts, (int, float)) and avg:
        gw_tone = "tile-good" if gw_pts >= avg else "tile-bad"
    attn_tone = "tile-warn" if attention else "tile-good"

    tiles = [
        ("Gameweek", eh.get("points", "-"), gw_note, "", gw_tone),
        ("Projected", f"{projected:.1f}" if projected else "-",
         f"best owned XI, {next_label}", "", ""),
        # "up 1.5m" beside "1,218,139 overall" read as a contradiction - two
        # millions, one a movement and one a position, neither saying which.
        # The chip says what it is.
        ("Total", eh.get("total_points", "-"),
         f"rank {d['overall_rank']:,}" if d.get("overall_rank") else "points",
         rank_chip, ""),
        ("League", f"{d['my_rank']}/{d['league_size']}" if d["my_rank"] else "-",
         e(d["league_name"]), lg_chip, ""),
        ("XI needs a look", len(attention),
         "; ".join(f"{nm} &mdash; {why}" for nm, why in attention[:2])
         + ("&hellip;" if len(attention) > 2 else "")
         if attention else "nobody flagged", "", attn_tone),
        # Sell value, not list value. What the squad would cost to buy today
        # is not what you can spend: FPL gives back purchase price plus half
        # of any rise, which is the number the chip planner already budgets
        # against, and two different squad values on one page is one too many.
        ("In the bank", f"{eh.get('bank', 0) / 10:.1f}m",
         (f"squad sells for {d['sell_value']:.1f}m"
          if d.get("sell_value") else
          f"squad {eh.get('value', 0) / 10:.1f}m"), "", ""),
    ]
    tile_html = "".join(
        f'<div class="tile {"tile-primary" if k in ("Gameweek", "Projected") else "tile-secondary"} {tone}"><div class="k">{e(k)}</div>'
        f'<div class="v tnum">{e(v)}{chip}</div><div class="n">{n}</div></div>'
        for k, v, n, chip, tone in tiles
    )
    # The review stays put when the pitch changes period.
    verdict = d.get("verdict") or ""
    verdict_html = f'<p class="hero-line">{verdict}</p>' if verdict else ""
    action = d.get("next_action") or {}
    captain = d.get("captain_summary")
    action_html = ""
    if action:
        target = action.get("target")
        action_title = (f'<a data-dashboard-jump href="#{e(target)}">{e(action["label"])} <span aria-hidden="true">↗</span></a>'
                        if target else e(action["label"]))
        captain_title = (f'<a data-dashboard-jump href="#captaincy">Captain {e(captain["player"])} <span aria-hidden="true">↗</span></a>'
                         if captain else "Captain advice unavailable")
        captain_note = (f'{captain["ep_total"]:.1f} expected points · {e(captain["opponent"])} '
                        f'({"H" if captain["home"] else "A"}) · see why'
                        if captain else "Waiting for supported fixture projections.")
        action_html = f'''<div class="hero-actions" aria-label="Suggested next steps">
          <div><span class="hero-eyebrow">{e(next_label)} · suggested action</span><h3>{action_title}</h3></div>
          <div><span class="hero-eyebrow">Suggested owned XI · captain</span><h3>{captain_title}</h3></div>
        </div><details class="hero-reasons"><summary>Why these suggestions</summary>
          <p>{e(action['detail'])}</p><p>{captain_note}</p>
        </details><p class="hero-caveat">Model prompts, based on your last published squad. <a data-dashboard-jump href="#action-method">How this is chosen</a> · <a data-dashboard-jump href="#chip-planner">Review chips</a></p>'''

    hero_html = f'''<section class="hero" aria-labelledby="review-title">
      <div class="hero-identity"><h2 class="hero-title" id="review-title">{e(title)}</h2>
      <div class="mgr">{e(d['manager'])} &middot; {e(d['league_name'])}</div></div>
      <div class="hero-review">{verdict_html}<div class="tiles">{tile_html}</div></div>
      <div class="hero-decision">{action_html}</div>
    </section>'''

    body = f"""
<header class="topbar"><div class="topbar-in">
  <span class="wordmark"><span class="dot"></span>FPL Insights</span>
  <span class="gw-chip">Gameweek {d['gw']}</span>
  <span class="stamp">{e(d['generated'])}</span>
</div>
<div class="railwrap" hidden><nav class="rail" aria-label="Sections on this tab"></nav></div>
</header>

<div class="wrap">
  <section class="product-intro" aria-labelledby="product-purpose">
    <h1 id="product-purpose">The numbers behind your FPL decisions.</h1>
    <p>Jonno Millar's public Fantasy Premier League squad and mini-league, analysed from player statistics, fixtures and market odds.</p>
    <div class="intro-links">
      <a href="https://github.com/JonnoMillar/fpl-insights">Source code <span aria-hidden="true">↗</span></a>
      <details class="about-methods">
        <summary>About &amp; methods</summary>
        <div class="about-copy">
          <p>Built by Jonno Millar to turn the numbers behind the points into captain, transfer and chip decisions. Explore the published squad, compare mini-league results, or use Scout to find and compare players.</p>
          <p>Player statistics come from the public Fantasy Premier League API, including Opta's expected goals and expected assists. Their sum, expected goal involvement (xGI), describes the quality of chances a player takes and creates. Fixtures, market odds and predicted line-ups inform the analysis.</p>
          <p>Projections are estimates. Advice uses the last published squad and bank, so check your actual team before acting. Double-gameweek planning is unsupported. Snapshots refresh on a best-effort schedule; their age and any unavailable sources are shown below.</p>
          <a href="https://github.com/JonnoMillar/fpl-insights#how-it-works">Read about the data and approach <span aria-hidden="true">↗</span></a>
        </div>
      </details>
    </div>
  </section>
  <div class="tabs tabbar" role="tablist" aria-label="Dashboard sections">
    <button class="tab" role="tab" aria-selected="true" data-panel="p-squad">Squad</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-market">Planning</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-league">Mini-league</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-scout">Scout</button>
  </div>

  <p class="data-status" role="status" data-generated="{e(d.get('generated_iso', ''))}">
    Snapshot: {e(d['generated'])}. Squad and bank reflect the last published picks.</p>
{source_notice(d)}
  <div class="panel" id="p-squad" role="tabpanel">
    <div class="squad-overview">
    {hero_html}
    <section class="card squad-pitch">
      <div class="card-head"><h2>Starting XI{components.info_btn()}</h2>
        <span class="subvis">Tap a player for the full breakdown.</span>
        <span class="sub" hidden>Season and Last gameweek use your last published team. Next gameweek selects the best legal XI from your owned squad, then lets you preview the recommended transfers. xP is projected points before captain or chip multipliers. C is captain, V is vice-captain, and IN marks an incoming transfer. A faded crest means no minutes in GW{d['gw']}.</span>
      </div>
      <div class="pkview tabbar" role="tablist" aria-label="Pitch view">
        <button class="pkbtn" role="tab" aria-selected="true" data-view="ov">Season</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="pk">Next gameweek</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="gw">Last gameweek</button>
      </div>
      <div class="pitch-controls">
        <p class="pitch-metric" aria-live="polite">Season · points</p>
        <div class="statsel" role="group" aria-label="Figure shown on the pitch">
          <button class="stbtn" data-stat="p" aria-pressed="true">points</button>
          <button class="stbtn" data-stat="g" aria-pressed="false">per game</button>
          <button class="stbtn" data-stat="x" aria-pressed="false">xGI</button>
        </div>
        <button class="epbtn" aria-pressed="false" hidden>predicted points</button>
      </div>
      <div class="pitch-context" aria-live="polite">
        <p data-pkview="ov">Last published squad · season figures</p>
        <p data-pkview="gw" hidden>Last published squad · GW{d['gw']} points</p>
        <div data-pkview="pk" hidden>
          <div class="lineup-summaries">
            <p data-lineup="owned">{e(d.get('owned_lineup_note', 'Suggested XI unavailable: supported projections are required.'))}</p>
            <p data-lineup="transfers" hidden>{e(d.get('transfer_lineup_note', 'Transfer preview unavailable.'))}</p>
          </div>
          <button type="button" class="lineup-toggle" role="switch" aria-checked="false" {'disabled' if not d.get('transfer_pick_pitch') else ''}>Apply suggested transfers</button>
          <p class="lineup-preview-note">{e(d.get('transfer_preview_note', 'No suggested transfers to preview.'))}</p>
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
    <div class="chapter"><h2>What the numbers say</h2>
      <span class="sub">Nine readings of the same fifteen players.</span></div>
    <section>{d['findings']}</section>
  </div>

  <div class="panel" id="p-market" role="tabpanel" hidden>
    <details class="card action-method" id="action-method"><summary class="card-head"><h2>How the suggested action is chosen</h2></summary>
      <div class="card-body"><p>Single moves and jointly evaluated pairs use the same five-gameweek XI gain, after transfer hits. We suggest a move above a two-point margin; a pair must also beat the best single move by two points. Otherwise, roll. This is a conservative heuristic, not a calibrated guarantee, and does not price the future value of banked transfers.</p>
      <p>A chip is highlighted only when its existing planner identifies a strong next-gameweek opportunity and its availability is verified. Chip timing is judged separately from transfer gains. Wildcard covers a longer window: review that case in the chip planner. Double gameweeks remain unsupported. Check your actual squad, bank and free transfers before acting.</p></div>
    </details>
    <div class="chapter"><h2>This week</h2>
      <span class="sub">What the fixtures are priced at, and what you missed.</span></div>
    {d['market']}
    {d['best_xi']}
    {d['kneejerk']}

    <div class="chapter"><h2>Your moves</h2>
      <span class="sub">Who to sell, who to buy, and who takes the armband.</span></div>
    {d['verdicts']}
    {d['transfers']}
    {d['pairings']}
    {d['captaincy']}

    <div class="chapter"><h2>Chips and the weeks ahead</h2>
      <span class="sub">Where the fixtures turn, and which chip that is worth.</span></div>
    {d['chip_planner'] or '<section class="card" id="chip-planner" tabindex="-1"><div class="card-head"><h2>Chip planner unavailable</h2><span class="subvis">Supported fixture projections and recovered selling prices are required. Check the source status above.</span></div></section>'}
    {d['ticker']}
    {d['fixture_runs']}

    <div class="chapter"><h2>The wider market</h2>
      <span class="sub">Everyone else's squad, and what it is doing to prices.</span></div>
    {d['leaders']}
    {d['price_watch']}
    {d['scatter']}
    {d['elite']}
  </div>

  <div class="panel" id="p-league" role="tabpanel" hidden>
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

    <div class="chapter"><h2>What the league owns</h2>
      <span class="sub">The squad everyone converges on, and where you leave it.</span></div>
    {d['template']}
    {d['carousel']}
    {d['differentials']}
    {d['watchlist']}

    <div class="chapter"><h2>How they are playing it</h2>
      <span class="sub">Who is scoring against you, and how the eight of you differ.</span></div>
    {d['rivals']}
    <section>{d['ownership']}</section>
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
  <p class="foot">Built from the public Fantasy Premier League API &middot;
  expected goals are Opta's, as used by FPL &middot; {e(d['generated'])}
  &middot; <a href="https://github.com/JonnoMillar/fpl-insights">source and
  phone alerts</a></p>
</div>
"""
    # Archivo is requested across its width axis as well as its weight axis -
    # the expanded headings are the point, and asking only for weights would
    # silently render them at normal width.
    fonts = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        "family=Archivo:wdth,wght@62..125,400..700&"
        "family=IBM+Plex+Mono:wght@400;500;600&display=swap\">"
    )
    head = f"<title>FPL Insights · {e(title)}</title>{FAVICON}{SOCIAL_META}{fonts}<style>{CSS}</style>"
    page = (
        f"{head}{body}<script>{JS}</script><script>{SCATTER_JS}</script>"
        f"<script>{PLAYERVIEW_JS}</script><script>{CAPTAINCY_JS}</script>"
        f"<script>{LEAGUECHART_JS}</script><script>{TICKER_JS}</script>"
        f"<script>{SCOUT_JS}</script>"
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
        f"<script>{SCOUT_JS}</script></body></html>"
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

    badges = {}
    for tid, t in ctx.teams.items():
        uri = fplapi.badge_data_uri(t["code"])
        if uri:
            badges[tid] = uri

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
        scout_pools, scout_fixtures = {}, []
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
    # A genuinely different question from Free Hit's budget-capped "ideal" -
    # see chips.literal_best_xi for why reusing that number here was wrong.
    next_ideal = chips.literal_best_xi(ctx, xi, proj, market, baselines, next_gw)

    action = next_action.choose(swaps, pairings, free_ts, moves_available, next_gw,
        (("freehit", "Free Hit", fh), ("3xc", "Triple Captain", tc), ("bboost", "Bench Boost", bb)),
        used if chips_verified else None)
    chip_name = {"freehit": "Free Hit", "3xc": "Triple Captain", "bboost": "Bench Boost"}.get(action.get("chip"))
    chip_note = f"Suggested chip: {chip_name}" if chip_name else "No chip suggested"
    if action.get("chip") == "freehit":
        chip_note += " — replacement squad is in the chip planner"
    preview_reports, preview_eps, transfer_lineup = [], {}, None
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
                transfer_lineup = next_squad.select(changed, preview_eps, preview_blanks)
            preview_note = (f"Preview only · {len(moves)} transfer{'s' if len(moves) != 1 else ''} · {analysis.transfer_cost(len(moves), free_ts)}-point hit. Check your actual squad and bank."
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
        captain = next(r.name for r in team["xi"] if r.element["id"] == team["captain"])
        return f"{label} · {'–'.join(map(str, team['formation']))} · Captain {captain} · {chip_note}"

    dialog_eps = eps + [(r, preview_eps.get(r.element["id"])) for r in preview_reports]

    return {
        "ctx": ctx,
        "next_action": action,
        "captain_summary": cap_matrix["candidates"][0] if cap_matrix and advice_supported else None,
        "gw": gw,
        "team_name": meta.get("name", "My team"),
        "manager": f"{meta.get('player_first_name', '')} "
                   f"{meta.get('player_last_name', '')}".strip(),
        "entry_history": picks.get("entry_history", {}),
        "league_name": league_name,
        "league_size": len(rows),
        "my_rank": my_row["rank"] if my_row else None,
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
        "owned_lineup_note": team_note(owned_lineup, "Best owned XI"),
        "transfer_lineup_note": team_note(transfer_lineup, "With suggested transfers"),
        "transfer_preview_note": preview_note,
        "chip_planner": chip_planner_card(fh, tc, bb, wc, used, xi, bench,
                                          ctx, badges, shirts, proj, market,
                                          next_gw),
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
                                                    market, next_gw, weeks=6),
        "market": ticker.odds_insights(market_fixtures, xi, ctx, proj, next_gw),
        "pairings": components.pairing_cards(
            pairings,
            "Two out, two in - moves a single transfer cannot reach, because "
            "one sale funds the other and two sales from a club free a slot. "
            "Same shape, within budget, three per club respected. "
            + (f"You have {free_ts} free transfer{'s' if free_ts != 1 else ''}, "
               f"so this pair costs {pair_hit}."
               if free_ts is not None else
               "Free-transfer count unavailable, so a pair is priced at 4."),
            hit=pair_hit),
        "leaders": components.stat_leaders(leader_groups(ctx, squad_ids)),
        "transfers": components.transfer_cards(
            swaps,
            f"Same position, affordable on {bank:.1f}m in the bank, ranked by "
            f"projected gain over the next {transfers.TRANSFER_HORIZON_WEEKS} "
            f"gameweeks (plus a small form/xGI nudge). Selling price comes from "
            f"recovered purchase history - read these as prompts, not instructions.",
            # How many of these you can actually take is the first thing you
            # need and it used to live only in a collapsed note on a different
            # card. It belongs on the face of the card that lists the moves.
            lede=(f"You have {free_ts} free transfer"
                  f"{'s' if free_ts != 1 else ''} this week. Each further move "
                  f"costs 4 points."
                  if free_ts is not None else
                  "Free-transfer count unavailable - price any move beyond "
                  "your first at 4 points.")),
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
            (r.name, (r.availability[0] or "not in the predicted XI"))
            for r in xi
            if r.availability[0] or ctx.is_predicted(r.element) is False
        ],
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "generated_iso": datetime.now(timezone.utc).isoformat(),
        "source_health": dict(fplapi.HEALTH),
    }
