#!/usr/bin/env python3
"""
What the best managers in the world actually own.

FPL runs a global league of every entry, id 314, called "Overall". Its
standings are public and ranked, so the squads of the top managers can be read
exactly the same way a mini-league rival's can. Ownership among that group is
the single most useful number FPL does not publish: it separates "popular"
from "popular with people who are winning".

Early in a season, though, the current-season top of that table is mostly a
survivorship sample of lucky captaincy picks, not skill - two or three good
gameweeks is not evidence of judgement. So the reference set here is
"proven" managers: among the current top PROVEN_POOL_SIZE, only those whose
most recently completed season finished inside the top PROVEN_LAST_SEASON_RANK
count. That is a season-plus of track record behind the sample, at the cost
of a smaller n, which is why every figure carries its margin of error.
"""

import math

import analysis
import fplapi

OVERALL_LEAGUE = 314
PAGE = 50
PROVEN_POOL_SIZE = 250
PROVEN_LAST_SEASON_RANK = 100_000
MIN_PROVEN_MANAGERS = 50


def top_entries(count, ttl=fplapi.DEFAULT_TTL):
    """Entry ids of the top `count` managers worldwide, in rank order."""
    ids, page = [], 1
    while len(ids) < count:
        data = fplapi.league_standings(OVERALL_LEAGUE, page=page, ttl=ttl)
        rows = data["standings"]["results"]
        if not rows:
            break
        ids.extend((r["rank"], r["entry"], r["entry_name"]) for r in rows)
        if not data["standings"]["has_next"]:
            break
        page += 1
    return ids[:count]


def proven_entries(pool_size=PROVEN_POOL_SIZE, rank_cutoff=PROVEN_LAST_SEASON_RANK,
                   ttl=fplapi.DEFAULT_TTL, progress=True):
    """Managers in the current top `pool_size` whose most recently completed
    season finished inside the top `rank_cutoff` - proven, not just lucky
    this fortnight."""
    candidates = top_entries(pool_size, ttl=ttl)
    out = []
    for i, (rank, entry_id, name) in enumerate(candidates, 1):
        try:
            hist = fplapi.entry_history(entry_id, ttl=ttl)
        except fplapi.FplError:
            continue
        past = hist.get("past") or []
        last_season_rank = past[-1].get("rank") if past else None
        if last_season_rank and last_season_rank <= rank_cutoff:
            out.append((rank, entry_id, name))
        if progress and i % 50 == 0:
            print(f"[elite] checked {i}/{len(candidates)} candidates for a proven history")
    return out


def margin_of_error(n, confidence_z=1.96):
    """Worst-case 95% margin for a proportion, in percentage points."""
    return 100 * confidence_z * math.sqrt(0.25 / n) if n else 100.0


def ownership(ctx, entries, event=None, ttl=fplapi.DEFAULT_TTL, progress=True):
    """How many of `entries` own each player, and how many captain him.

    Returns (counts, captains, sampled_ok) where sampled_ok is the number of
    squads actually read - managers whose picks fail are dropped, and the
    denominator uses the successful count so a few failures do not silently
    deflate every percentage."""
    event = event or ctx.last_event_with_picks()
    counts, captains, ok = {}, {}, 0
    for i, (_rank, entry_id, _name) in enumerate(entries, 1):
        try:
            picks = fplapi.entry_picks(entry_id, event, ttl=ttl)
        except fplapi.FplError:
            continue
        ok += 1
        for p in picks.get("picks", []):
            counts[p["element"]] = counts.get(p["element"], 0) + 1
            if p["is_captain"]:
                captains[p["element"]] = captains.get(p["element"], 0) + 1
        if progress and i % 25 == 0:
            print(f"[elite] read {i}/{len(entries)} squads")
    return counts, captains, ok


def compare(ctx, squad_ids, depth=PROVEN_POOL_SIZE, event=None,
            ttl=fplapi.DEFAULT_TTL, limit=12):
    """Proven-manager ownership next to overall ownership, and where you differ.

    The gap between the two is the interesting part: a player owned by half
    the proven managers and a twentieth of everyone else is a signal, and one
    owned the other way round is a trap. Below MIN_PROVEN_MANAGERS qualifying
    managers there isn't enough of a sample to say anything, so this returns
    None rather than print noise."""
    entries = proven_entries(pool_size=depth, ttl=ttl)
    if len(entries) < MIN_PROVEN_MANAGERS:
        return {"insufficient": True}
    label = (f"top-{PROVEN_LAST_SEASON_RANK:,} finish last season, "
             f"top-{depth} now")

    counts, captains, ok = ownership(ctx, entries, event=event, ttl=ttl)
    if not ok:
        return {"insufficient": True}
    moe = margin_of_error(ok)

    rows = []
    for pid, n in counts.items():
        el = ctx.players.get(pid)
        if not el:
            continue
        elite_pct = round(100.0 * n / ok)
        overall = round(analysis.f(el.get("selected_by_percent")))
        rows.append({
            "id": pid,
            "name": el["web_name"],
            "team": ctx.team_name(el["team"]),
            "pos": ctx.pos(el),
            "price": el["now_cost"] / 10.0,
            "elite": elite_pct,
            "overall": overall,
            "edge": elite_pct - overall,
            "captains": captains.get(pid, 0),
            "captain_pct": 100.0 * captains.get(pid, 0) / ok,
            "mine": pid in set(squad_ids),
            "points": el["total_points"],
        })
    rows.sort(key=lambda r: -r["elite"])
    # A gap smaller than 2x the margin of error is indistinguishable from
    # sampling noise at 95% confidence - not worth calling a signal.
    signal = lambda r: abs(r["edge"]) >= 2 * moe
    return {
        "mode": "proven",
        "label": label,
        "managers": ok,
        "moe": moe,
        "event": event or ctx.last_event_with_picks(),
        "rows": rows,
        "most_owned": rows[:limit],
        # Owned far more by the elite than by the crowd, and not by you.
        "elite_edge": sorted(
            (r for r in rows if not r["mine"] and r["edge"] > 0 and signal(r)),
            key=lambda r: -r["edge"],
        )[:limit],
        # You own it, the elite largely do not.
        "against": sorted(
            (r for r in rows if r["mine"] and r["edge"] < 0 and signal(r)),
            key=lambda r: r["edge"],
        )[:limit],
        "captains": sorted(
            (r for r in rows if r["captains"]), key=lambda r: -r["captains"]
        )[:6],
    }
