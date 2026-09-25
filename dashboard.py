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

def render(d, standalone=True):
    ctx = d["ctx"]
    title = d["team_name"]
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
        # "up 1.5m" beside "1,218,139 overall" read as a contradiction - two
        # millions, one a movement and one a position, neither saying which.
        # The chip says what it is.
        ("Total", eh.get("total_points", "-"),
         f"rank {d['overall_rank']:,}" if d.get("overall_rank") else "points",
         rank_chip, ""),
        ("League", f"{d['my_rank']}/{d['league_size']}" if d["my_rank"] else "-",
         e(d["league_name"]), lg_chip, ""),
        ("Projected", f"{projected:.1f}" if projected else "-",
         f"your XI, GW{d['next_gw']}", "", ""),
        ("Needs a look", len(attention),
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
        f'<div class="tile {tone}"><div class="k">{e(k)}</div>'
        f'<div class="v tnum">{e(v)}{chip}</div><div class="n">{n}</div></div>'
        for k, v, n, chip, tone in tiles
    )
    # Two one-liners, one for each direction the page can be read in. The
    # Pick team view swaps them; see the .pkview handler.
    verdict = d.get("verdict") or ""
    ahead = d.get("next_line") or ""
    verdict_html = (
        (f'<p class="hero-line" data-pkview="back">{verdict}</p>'
         if verdict else "")
        + (f'<p class="hero-line" data-pkview="pk" hidden>{ahead}</p>'
           if ahead else "")
    )

    body = f"""
<header class="topbar"><div class="topbar-in">
  <span class="wordmark"><span class="dot"></span>FPL Insights</span>
  <span class="gw-chip">Gameweek {d['gw']}</span>
  <span class="stamp">{e(d['generated'])}</span>
</div>
<div class="railwrap" hidden><nav class="rail" aria-label="Sections on this tab"></nav></div>
</header>

<div class="wrap">
  <section class="hero">
    <h1>{e(title)}</h1>
    <div class="mgr">{e(d['manager'])} &middot; {e(d['league_name'])}</div>
    {verdict_html}
    <div class="tiles">{tile_html}</div>
  </section>

  <div class="tabs tabbar" role="tablist">
    <button class="tab" role="tab" aria-selected="true" data-panel="p-squad">Squad</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-market">Planning</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-league">Mini-league</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-scout">Scout</button>
  </div>

  <div class="panel" id="p-squad" role="tabpanel">
    <section class="card">
      <div class="card-head"><h2>Starting XI</h2>
        <span class="sub" data-pkview="ov">Season points, points per game and season xGI on each card - click one to bring it forward. <b>Looking back:</b> a faded crest means he did not play in GW{d['gw']}. <b>Looking forward:</b> a green dot means Fantasy Football Scout predict him to start GW{d['next_gw']}, red means they do not.</span>
        <span class="sub" data-pkview="gw" hidden>GW{d['gw']} points on each card, with points per game and season xGI beside them. A faded crest means he did not play that week.</span>
        <span class="sub" data-pkview="pk" hidden>Next fixture and a read on recent form on each card, shaded by clean-sheet odds for keepers and defenders and by expected goals for everyone else.</span>
      </div>
      <div class="pkview tabbar" role="tablist" aria-label="Pitch view">
        <button class="pkbtn" role="tab" aria-selected="true" data-view="ov">Overview</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="pk">Pick team</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="gw">Gameweek {d['gw']}</button>
        <div class="statsel" role="group" aria-label="Bring a figure forward">
          <button class="stbtn" data-stat="p" aria-pressed="true">points</button>
          <button class="stbtn" data-stat="g" aria-pressed="false">per game</button>
          <button class="stbtn" data-stat="x" aria-pressed="false">xGI</button>
        </div>
        <button class="epbtn" aria-pressed="false" hidden>predicted points</button>
      </div>
      <div class="pkpanel" data-view="ov">{d['pitch']}</div>
      <div class="pkpanel" data-view="pk" hidden>{d['pick_pitch']}</div>
    </section>
    <details class="card collapsible">
      <summary class="card-head"><h2>Squad detail{components.info_btn()}</h2>
        <span class="sub" hidden>Click a column heading to sort. xP is projected points for GW{d['next_gw']} - the one forward-looking column, so you can sort the underlying numbers against what the model expects from them. Next 3 fixtures rated out of ten, higher is better; CAPITALS are home.</span>
      </summary>
      {d['squad_table']}
    </details>
    <div class="chapter"><h2>What the numbers say</h2>
      <span class="sub">Nine readings of the same fifteen players.</span></div>
    <section>{d['findings']}</section>
  </div>

  <div class="panel" id="p-market" role="tabpanel" hidden>
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
    {d['chip_planner']}
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
  expected goals are Opta's, as used by FPL &middot; {e(d['generated'])}</p>
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
    head = f"<title>{e(title)}</title>{FAVICON}{fonts}<style>{CSS}</style>"
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

    matched = pulse.attach(ctx, ttl=ttl)
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
        uri = fplapi.photo_data_uri(r.element["photo"])
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
    next_gw = min(38, (ctx.current_event() or 1) + 1)
    baselines = analysis.team_attack_baselines(ctx)
    # One event_live call per gameweek so far, shared across every position -
    # see scout.season_live. Fails soft like the other optional sections
    # (odds, elite) rather than taking the whole page down with it. xp uses
    # transfers.candidate_score, the same bootstrap-only scorer chips.py
    # uses for market-wide candidate pools (see shared-scorer-architecture
    # memory) - priors computed once here, never inside the per-position loop.
    try:
        scout_live = scout.season_live(ctx, ctx.current_event() or 1, ttl=ttl)
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
    cap_matrix = captaincy.matrix(ctx, xi, eps_by_id)

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
    free_ts = analysis.free_transfers(entry_id, next_gw, ttl=ttl)
    pair_hit = analysis.transfer_cost(2, free_ts)
    print(f"[transfers] {free_ts if free_ts is not None else '?'} free, "
          f"a pair costs {pair_hit}")
    swaps = transfers.suggest(
        ctx, xi + bench, proj, next_gw, market, baselines,
        bank=bank, limit=6, elite=elite_res,
    )
    for sw in swaps:
        el = sw["in"]
        sw["in_club"] = ctx.team_name(el["team"])
        sw["out_photo"] = photos.get(sw["out"].element["id"])
        sw["in_photo"] = fplapi.photo_data_uri(el["photo"])
        sw["out_shirt"] = shirts.get(
            (sw["out"].element["team"], sw["out"].pos == "GKP"))
        sw["in_shirt"] = shirts.get((el["team"], ctx.pos(el) == "GKP"))

    pairings = transfers.pair_suggestions(
        ctx, xi + bench, proj, next_gw, market, baselines,
        bank=bank, limit=4, elite=elite_res, hit_cost=pair_hit,
    )
    for pr in pairings:
        for leg in pr["legs"]:
            el = leg["in"]
            leg["out_photo"] = photos.get(leg["out"].element["id"])
            leg["in_photo"] = fplapi.photo_data_uri(el["photo"])
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
                    ctx.players[pid]["photo"]))
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
            ctx.players[row["id"]]["photo"]))

    watchlist_rows = []
    if own and proj:
        watchlist_rows = differential_watchlist(
            own, ctx, proj, market, baselines, next_gw, squad_ids)
        for row in watchlist_rows:
            league_photos.setdefault(row["id"], fplapi.photo_data_uri(
                ctx.players[row["id"]]["photo"]))

    # Same graceful-degradation shape ticker.fixture_ticker already uses
    # for the same reason: if proj never arrived this build, there is
    # nothing honest to recommend, so the whole card skips rather than
    # showing a set of zeroed or misleading cards.
    fh = tc = bb = wc = None
    used = {}
    total_sell = None
    if proj:
        bank_m = (picks.get("entry_history", {}).get("bank") or 0) / 10.0
        try:
            total_sell, _per_player = analysis.squad_sell_value(
                entry_id, ctx, xi + bench, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[chips] sell value unavailable, falling back to "
                  f"current price: {ex}")
            total_sell = sum(r.price for r in xi + bench)
        fh = chips.free_hit(ctx, xi, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        tc = chips.triple_captain(ctx, xi, proj, market, baselines, next_gw)
        bb = chips.bench_boost(ctx, bench, proj, market, baselines, next_gw,
                               bank=bank_m)
        wc = chips.wildcard(ctx, xi + bench, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        try:
            used = chips.used_chips_this_half(entry_id, next_gw, ttl=ttl)
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
    kj = transfers.kneejerk(ctx, xi + bench, lg_scores, bank=bank)
    vb = transfers.verdict_board(ctx, xi + bench, lg_scores, bank=bank)

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
                - primary.price - second.price
            )
            pairings.append({
                "tag": f"Reaches the knee-jerk pick, {target_el['web_name']}",
                "legs": [
                    {"out": primary, "in": target_el, "gain": primary_gain,
                     "out_photo": photos.get(primary.element["id"]),
                     "in_photo": fplapi.photo_data_uri(target_el["photo"]),
                     "out_shirt": shirts.get(
                         (primary.element["team"], primary.pos == "GKP")),
                     "in_shirt": shirts.get(
                         (target_el["team"], ctx.pos(target_el) == "GKP"))},
                    {"out": second, "in": repl_el, "gain": second_gain,
                     "out_photo": photos.get(second.element["id"]),
                     "in_photo": fplapi.photo_data_uri(repl_el["photo"]),
                     "out_shirt": shirts.get(
                         (second.element["team"], second.pos == "GKP")),
                     "in_shirt": shirts.get(
                         (repl_el["team"], ctx.pos(repl_el) == "GKP"))},
                ],
                "gain": primary_gain + second_gain,
                "bank_after": bank - spend,
            })
    # A genuinely different question from Free Hit's budget-capped "ideal" -
    # see chips.literal_best_xi for why reusing that number here was wrong.
    next_ideal = chips.literal_best_xi(ctx, xi, proj, market, baselines, next_gw)

    return {
        "ctx": ctx,
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
        "pick_pitch": pick_team_pitch(xi, bench, ctx, badges, shirts, cap,
                                      vice, proj, market, next_gw, eps),
        "chip_planner": chip_planner_card(fh, tc, bb, wc, used, xi, bench,
                                          ctx, badges, shirts, proj, market,
                                          next_gw),
        "best_xi": best_xi_card(next_ideal, ctx, set(squad_ids), next_gw),
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
            f"gameweeks (plus a small form/xGI nudge). Selling price is taken as "
            f"current price - read these as prompts, not instructions.",
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
            player_payload(r, ctx, proj, ep, next_gw, photos) for r, ep in eps
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
        "overall_rank": meta.get("summary_overall_rank"),
        "gw_average": gw_average,
        "rank_move": rank_move,
        "verdict": verdict,
        "next_line": next_week_line(ctx, xi, eps, next_gw),
        "projected_xi": sum(
            ep["total"] for r, ep in eps
            if r.element["id"] in set(xi_ids)
        ) or None,
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
    }
