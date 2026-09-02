#!/usr/bin/env python3
"""
fpl-insights - underlying stats for your FPL squad and your mini-league.

    python cli.py team                 your 15, with per-match xG/xA
    python cli.py league               how your rivals are doing, and why
    python cli.py player haaland       one player, in detail

Everything comes from FPL's public API. No login, no scraping, no key.
"""

import sys
import json
import argparse
from pathlib import Path

import fplapi
import analysis
import report

CONFIG = Path(__file__).with_name("config.json")

DEFAULTS = {"entry_id": None, "league_id": None}


def load_config():
    if CONFIG.exists():
        try:
            return {**DEFAULTS, **json.loads(CONFIG.read_text(encoding="utf-8"))}
        except ValueError:
            print(f"warning: {CONFIG.name} is not valid JSON, ignoring", file=sys.stderr)
    return dict(DEFAULTS)


def need(value, what, flag):
    if value:
        return value
    sys.exit(
        f"No {what}. Pass {flag}, or put it in {CONFIG.name} "
        f'as {{"{what}": 1234567}}.'
    )


# --- commands -------------------------------------------------------------

def cmd_team(args, cfg):
    entry_id = need(args.entry or cfg["entry_id"], "entry_id", "--entry")
    ctx = analysis.Ctx.load(ttl=args.ttl)
    report.set_opponent_names(ctx)

    gw = args.gw or ctx.last_event_with_picks()
    picks = analysis.squad_for(entry_id, gw, ctx)
    meta = fplapi.entry(entry_id, ttl=args.ttl)
    eh = picks.get("entry_history", {})

    print(
        report.header(
            f"{meta.get('name', '?')} - {meta.get('player_first_name', '')} "
            f"{meta.get('player_last_name', '')} - GW{gw}"
        )
    )
    print(
        f"  GW points {eh.get('points', '?')}   total {eh.get('total_points', '?')}   "
        f"bench {eh.get('points_on_bench', '?')}   "
        f"hits {eh.get('event_transfers_cost', 0)}   "
        f"chip {picks.get('active_chip') or 'none'}   "
        f"squad value {eh.get('value', 0) / 10:.1f}m   "
        f"bank {eh.get('bank', 0) / 10:.1f}m"
    )

    xi_ids = [p["element"] for p in picks["picks"] if p["position"] <= 11]
    bench_ids = [p["element"] for p in picks["picks"] if p["position"] > 11]
    cap = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
    vice = next((p["element"] for p in picks["picks"] if p["is_vice_captain"]), None)

    reports = {}
    for pid in xi_ids + bench_ids:
        reports[pid] = analysis.build_player(ctx, pid, ttl=args.ttl)

    xi = [reports[i] for i in xi_ids]
    bench = [reports[i] for i in bench_ids]

    print(report.squad_table(xi, ctx, "STARTING XI", cap, vice))
    print(report.squad_table(bench, ctx, "BENCH", cap, vice))

    if not args.no_log:
        print(report.header(f"PER-MATCH LOG (last {args.matches})"))
        for r in xi + bench:
            print(report.match_log(r, args.matches))
            print()

    cap_report = report.captain_check(xi, cap)
    if cap_report:
        print(cap_report)
    bench_report = report.bench_check(picks, ctx)
    if bench_report:
        print(bench_report)

    print(report.header("FINDINGS"))
    print(report.findings(list(reports.values()), ctx))
    print()


def cmd_league(args, cfg):
    league_id = need(args.league or cfg["league_id"], "league_id", "--league")
    my_entry = args.entry or cfg["entry_id"]
    ctx = analysis.Ctx.load(ttl=args.ttl)

    data = fplapi.league_standings(league_id, ttl=args.ttl)
    rows = data["standings"]["results"]
    page = 1
    while data["standings"]["has_next"] and page < args.max_pages:
        page += 1
        data = fplapi.league_standings(league_id, page=page, ttl=args.ttl)
        rows.extend(data["standings"]["results"])

    print(report.header(f"{data['league']['name']} (league {league_id})"))
    print(f"  {len(rows)} managers")

    gw = args.gw or ctx.last_event_with_picks()
    squads, by_name, histories = {}, {}, {}
    for r in rows[: args.limit]:
        try:
            picks = analysis.squad_for(r["entry"], gw, ctx)
        except fplapi.FplError as e:
            print(f"  (could not read {r['entry_name']}: {e})", file=sys.stderr)
            continue
        squads[r["entry"]] = picks
        by_name[r["entry_name"]] = picks
        try:
            histories[r["entry_name"]] = fplapi.entry_history(r["entry"], ttl=args.ttl)
        except fplapi.FplError:
            pass

    print(report.standings_table(rows[: args.limit], squads, ctx, me=my_entry))

    my_name = next(
        (r["entry_name"] for r in rows if r["entry"] == my_entry), None
    )
    own = analysis.league_ownership(by_name)
    print(report.ownership_report(own, by_name, ctx, my_name))

    if histories:
        print(report.chips_report(histories, ctx))

    if args.squads:
        print(report.header(f"FULL SQUADS - GW{gw}"))
        for r in rows[: args.limit]:
            picks = squads.get(r["entry"])
            if not picks:
                continue
            xi = [p for p in picks["picks"] if p["position"] <= 11]
            bn = [p for p in picks["picks"] if p["position"] > 11]

            def nm(p):
                el = ctx.players.get(p["element"], {})
                tag = " (C)" if p["is_captain"] else ""
                return el.get("web_name", "?") + tag

            print(f"\n  {r['rank']}. {r['entry_name']} - {r['player_name']}")
            print(f"     XI:    {', '.join(nm(p) for p in xi)}")
            print(f"     Bench: {', '.join(nm(p) for p in bn)}")
    print()


def cmd_player(args, cfg):
    ctx = analysis.Ctx.load(ttl=args.ttl)
    report.set_opponent_names(ctx)
    q = args.name.lower()
    matches = [
        e
        for e in ctx.players.values()
        if q in e["web_name"].lower()
        or q in f"{e['first_name']} {e['second_name']}".lower()
    ]
    if not matches:
        sys.exit(f"No player matching {args.name!r}")
    if len(matches) > 8:
        sys.exit(f"{len(matches)} players match {args.name!r} - be more specific")

    for el in matches:
        r = analysis.build_player(ctx, el["id"], ttl=args.ttl)
        print(report.header(f"{r.name} - {r.pos}, {r.team}, {r.price:.1f}m"))
        flag, news = r.availability
        if flag:
            print(f"  {flag}  {news}")
        print(
            f"  owned by {r.owned:.1f}%   form {el['form']}   "
            f"points/game {el['points_per_game']}   total {el['total_points']}"
        )
        sp = r.set_pieces()
        if sp:
            print(f"  set pieces: {', '.join(sp)}")
        print(f"  next 5: {ctx.fixture_str(el['team'], 5)}")
        print(
            f"\n  This season: {r.minutes} min, {r.goals}G {r.assists}A, "
            f"xG {r.xg:.2f}, xA {r.xa:.2f}, xGI {r.xgi:.2f} "
            f"({r.xgi90:.2f}/90), {r.points} pts"
        )
        ls = r.last_season()
        if ls:
            print(
                f"  {ls['season']}:   {ls['minutes']} min, {ls['goals']}G "
                f"{ls['assists']}A, xG {ls['xg']:.2f}, xA {ls['xa']:.2f}, "
                f"xGI {ls['xgi']:.2f} "
                f"({analysis.per90(ls['xgi'], ls['minutes']):.2f}/90), "
                f"{ls['points']} pts"
            )
        print()
        print(report.match_log(r, args.matches))
        print()


def cmd_dashboard(args, cfg):
    entry_id = need(args.entry or cfg["entry_id"], "entry_id", "--entry")
    league_id = args.league or cfg["league_id"]
    import dashboard

    data = dashboard.build(entry_id, league_id, ttl=args.ttl, gw=args.gw,
                           elite_depth=args.elite)
    out = Path(args.out).resolve()
    out.write_text(dashboard.render(data, standalone=True), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB)")

    if args.artifact:
        frag = out.with_name(out.stem + "-artifact.html")
        frag.write_text(dashboard.render(data, standalone=False), encoding="utf-8")
        print(f"wrote {frag}  (body-only, for publishing as an Artifact)")

    removed = fplapi.prune_cache()
    if removed:
        print(f"pruned {removed} stale cache entries")
    print("\nsources this run:")
    print(fplapi.health_report())

    if args.open:
        import webbrowser

        webbrowser.open(out.as_uri())


# --- entry point ----------------------------------------------------------

def main(argv=None):
    # FPL player names contain accents; the Windows console default codepage
    # mangles them into UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    cfg = load_config()
    # --ttl lives on a shared parent so it works either before or after the
    # subcommand; argparse otherwise rejects `team --ttl 0`, which is the
    # order everyone types.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ttl", type=int, default=fplapi.DEFAULT_TTL,
                        help="cache lifetime in seconds (0 forces a refresh)")

    p = argparse.ArgumentParser(prog="fpl-insights", description=__doc__,
                                parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("team", help="your squad with per-match xG/xA",
                       parents=[common])
    t.add_argument("--entry", type=int)
    t.add_argument("--gw", type=int)
    t.add_argument("--matches", type=int, default=6, help="matches per player in the log")
    t.add_argument("--no-log", action="store_true", help="skip the per-match log")
    t.set_defaults(func=cmd_team)

    l = sub.add_parser("league", help="mini-league standings and ownership",
                       parents=[common])
    l.add_argument("--league", type=int)
    l.add_argument("--entry", type=int)
    l.add_argument("--gw", type=int)
    l.add_argument("--limit", type=int, default=25, help="managers to analyse")
    l.add_argument("--max-pages", type=int, default=4)
    l.add_argument("--squads", action="store_true", help="print every squad in full")
    l.set_defaults(func=cmd_league)

    d = sub.add_parser("dashboard", help="build the HTML dashboard", parents=[common])
    d.add_argument("--entry", type=int)
    d.add_argument("--league", type=int)
    d.add_argument("--gw", type=int)
    d.add_argument("--out", default="dashboard.html")
    d.add_argument("--elite", type=int, default=250, metavar="N",
                   help="how many current top-ranked managers to check for a "
                        "proven (top-100k last season) history (0 disables it)")
    d.add_argument("--open", action="store_true", help="open it in your browser")
    d.add_argument("--artifact", action="store_true",
                   help="also write a body-only copy for publishing as an Artifact")
    d.set_defaults(func=cmd_dashboard)

    pl = sub.add_parser("player", help="one player in detail", parents=[common])
    pl.add_argument("name")
    pl.add_argument("--matches", type=int, default=10)
    pl.set_defaults(func=cmd_player)

    args = p.parse_args(argv)
    try:
        args.func(args, cfg)
    except fplapi.FplError as e:
        sys.exit(f"FPL API error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
