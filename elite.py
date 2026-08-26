#!/usr/bin/env python3
"""
What the best managers in the world actually own.

FPL runs a global league of every entry, id 314, called "Overall". Its
standings are public and ranked, so the squads of the top managers can be read
exactly the same way a mini-league rival's can. Ownership among that group is
the single most useful number FPL does not publish: it separates "popular"
from "popular with people who are winning".

On scale, honestly: exact ownership for the top 10,000 would need roughly
10,200 requests - two hundred pages of standings plus one squad lookup each.
That is not a reasonable thing to do to somebody's free API, and it would take
half an hour. So there are two modes:

* **exact** - every manager in the top N (default 100). ~N requests.
* **sampled** - a systematic sample spread evenly across the top N, which
  estimates ownership rather than measuring it. 500 managers sampled from the
  top 10,000 puts the margin of error near +/-4.4 points at 95% confidence,
  which is far finer than any decision this feeds.

Sampled results are always labelled as estimates and carry their margin.
"""

import math

import analysis
import fplapi

OVERALL_LEAGUE = 314
PAGE = 50


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


def sampled_entries(depth, sample, ttl=fplapi.DEFAULT_TTL):
    """A systematic sample of `sample` managers spread across the top `depth`.

    Systematic rather than random: taking every Kth rank guarantees even
    coverage of the whole range, where a random draw could clump into the top
    few hundred and quietly bias the answer toward elite play."""
    step = max(1, depth // sample)
    wanted = set(range(1, depth + 1, step))
    pages = sorted({(r - 1) // PAGE + 1 for r in wanted})
    out = []
    for page in pages:
        try:
            data = fplapi.league_standings(OVERALL_LEAGUE, page=page, ttl=ttl)
        except fplapi.FplError as e:
            print(f"[elite] standings page {page}: {e}")
            continue
        for r in data["standings"]["results"]:
            if r["rank"] in wanted:
                out.append((r["rank"], r["entry"], r["entry_name"]))
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


def compare(ctx, squad_ids, depth=100, sample=None, event=None,
            ttl=fplapi.DEFAULT_TTL, limit=12):
    """Elite ownership next to overall ownership, and where you differ.

    The gap between the two is the interesting part: a player owned by half
    the top managers and a twentieth of everyone else is a signal, and one
    owned the other way round is a trap."""
    if sample:
        entries = sampled_entries(depth, sample, ttl=ttl)
        mode, label = "sampled", f"sample of {len(entries)} from the top {depth:,}"
    else:
        entries = top_entries(depth, ttl=ttl)
        mode, label = "exact", f"every manager in the top {depth:,}"

    counts, captains, ok = ownership(ctx, entries, event=event, ttl=ttl)
    if not ok:
        return None
    moe = margin_of_error(ok) if mode == "sampled" else 0.0

    rows = []
    for pid, n in counts.items():
        el = ctx.players.get(pid)
        if not el:
            continue
        elite_pct = 100.0 * n / ok
        overall = analysis.f(el.get("selected_by_percent"))
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
    return {
        "mode": mode,
        "label": label,
        "managers": ok,
        "moe": moe,
        "event": event or ctx.last_event_with_picks(),
        "rows": rows,
        "most_owned": rows[:limit],
        # Owned far more by the elite than by the crowd, and not by you.
        "elite_edge": sorted(
            (r for r in rows if not r["mine"] and r["edge"] > 0),
            key=lambda r: -r["edge"],
        )[:limit],
        # You own it, the elite largely do not.
        "against": sorted(
            (r for r in rows if r["mine"] and r["edge"] < 0),
            key=lambda r: r["edge"],
        )[:limit],
        "captains": sorted(
            (r for r in rows if r["captains"]), key=lambda r: -r["captains"]
        )[:6],
    }
