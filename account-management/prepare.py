"""Read-only initial-squad comparison, isolated from dashboard build outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import analysis
import ffs
import fplapi
import odds
import planner
import scout
import squadbuilder
import transfers

QUOTAS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}


def validate_squad(rows, budget=1000):
    """Budget is integer tenths; validate actual prices, never rounded totals."""
    if len(rows) != 15 or len({p["id"] for p in rows}) != 15:
        raise ValueError("A squad needs fifteen distinct players")
    if Counter(p["pos"] for p in rows) != QUOTAS:
        raise ValueError("Wrong position quotas")
    if max(Counter(p["club"] for p in rows).values()) > 3:
        raise ValueError("More than three players from a club")
    if sum(p["cost"] for p in rows) > budget:
        raise ValueError("Squad exceeds budget")
    if any(type(p["cost"]) is not int or p["cost"] <= 0 for p in rows):
        raise ValueError("Prices must be positive integer tenths")
    if any(not math.isfinite(x) or x < 0 for p in rows for x in p["weeks"]):
        raise ValueError("Invalid projection")


def check_window(ctx, proj, gws):
    """Blanks are valid zeroes; missing/mismatched estimates and doubles fail."""
    for gw in gws:
        if not any(x.get("event") == gw for x in ctx.fixtures):
            raise ValueError(f"GW{gw}: whole-round fixture coverage unavailable")
        for tid in ctx.teams:
            fixtures = [x for x in ctx.fixtures if x.get("event") == gw
                        and tid in (x["team_h"], x["team_a"])]
            if len(fixtures) > 1:
                raise ValueError(f"GW{gw}: doubles require a separate review")
            if not fixtures:
                continue
            fx = fixtures[0]
            home = fx["team_h"] == tid
            opp = ctx.team_name(fx["team_a"] if home else fx["team_h"])
            row = proj.get((ctx.team_name(tid), gw))
            if not row or row.get("opp") != opp or row.get("ven") != ("H" if home else "A"):
                raise ValueError(f"GW{gw} {ctx.team_name(tid)}: fixture coverage invalid")
            if (not math.isfinite(float(row["g"])) or float(row["g"]) < 0
                    or not math.isfinite(float(row["cs"])) or not 0 <= float(row["cs"]) <= 100):
                raise ValueError(f"GW{gw}: invalid fixture estimates")


def score_squad(rows, horizon=8, discount=0.9):
    validate_squad(rows)
    if horizon < 1 or any(len(p["weeks"]) < horizon for p in rows):
        raise ValueError("Projection horizon incomplete")
    weeks, total = [], 0.0
    for j in range(horizon):
        pool = [{**p, "price": p["cost"] / 10, "value": p["weeks"][j]} for p in rows]
        chosen = squadbuilder.owned_xi(pool)
        xi = chosen["xi"]
        cap_order = sorted(xi, key=lambda p: (-p["value"], p["id"]))
        reserve = next(p for p in chosen["bench"] if p["pos"] == "GKP")
        bench = sorted((p for p in chosen["bench"] if p["pos"] != "GKP"),
                       key=lambda p: (-p["value"], p["id"]))
        bench_value = sum(w * p["value"] for w, p in zip(planner.BENCH_WEIGHTS, bench))
        bench_value += planner.BENCH_GK_WEIGHT * reserve["value"]
        value = chosen["value"] + cap_order[0]["value"] + bench_value
        weeks.append({"xi": [p["id"] for p in xi],
                      "captain": cap_order[0]["id"], "vice": cap_order[1]["id"],
                      "bench": [reserve["id"]] + [p["id"] for p in bench],
                      "formation": chosen["formation"], "xi_xp": round(chosen["value"], 2),
                      "captain_xp": round(cap_order[0]["value"], 2),
                      "weighted_bench_xp": round(bench_value, 2), "total": round(value, 2)})
        total += discount ** j * value
    return {"objective": round(total, 3), "weeks": weeks}


def improve(rows, candidates, horizon):
    """Improve a seed using its actual XI/captain/bench objective, not raw sum.

    shortcut: single swaps cannot cross every budget/club barrier; retain
    multiple independent seeds and disclose that no global optimum is proved.
    """
    rows = list(rows)
    current = score_squad(rows, horizon)["objective"]
    for _ in range(20):
        held = {p["id"] for p in rows}
        cost = sum(p["cost"] for p in rows)
        clubs = Counter(p["club"] for p in rows)
        best = None
        for i, outgoing in enumerate(rows):
            for incoming in candidates:
                if (incoming["pos"] != outgoing["pos"] or incoming["id"] in held
                        or cost - outgoing["cost"] + incoming["cost"] > 1000
                        or clubs[incoming["club"]] - (incoming["club"] == outgoing["club"]) >= 3):
                    continue
                trial = rows[:i] + [incoming] + rows[i + 1:]
                value = score_squad(trial, horizon)["objective"]
                if value > current + 0.001 and (best is None or value > best[0]):
                    best = value, trial
        if best is None:
            return rows
        current, rows = best
    raise ValueError("Squad refinement did not converge")


def self_check():
    rows = []
    for pos, n in QUOTAS.items():
        for _ in range(n):
            i = len(rows)
            rows.append({"id": i + 1, "pos": pos, "club": str(i // 3),
                         "cost": 50, "weeks": [2.0] * 8})
    score = score_squad(rows)
    assert score["weeks"][0]["xi_xp"] == 22
    assert score["weeks"][0]["captain_xp"] == 2
    assert len(score["weeks"][0]["bench"]) == 4
    upgrade = {**rows[2], "id": 100, "weeks": [9.0] * 8}
    improved = improve(rows, rows + [upgrade], 8)
    assert 100 in {p["id"] for p in improved}
    assert score_squad(improved)["objective"] > score["objective"]
    for change in (lambda r: r.__setitem__(1, dict(r[0])),
                   lambda r: r[0].update(cost=400),
                   lambda r: [p.update(club="same") for p in r],
                   lambda r: r[0].update(pos="DEF"),
                   lambda r: r[0].update(weeks=[float("nan")] * 8),
                   lambda r: r[0].update(cost=-1)):
        copy = [{**p, "weeks": list(p["weeks"])} for p in rows]
        change(copy)
        try:
            validate_squad(copy)
        except ValueError:
            pass
        else:
            raise AssertionError("Bad squad accepted")
    toy = analysis.Ctx(boot={}, teams={1: {"short_name": "A"}, 2: {"short_name": "B"}})
    toy.fixtures = [{"event": 9, "team_h": 1, "team_a": 2}]
    fixture_proj = {("A", 9): {"opp": "B", "ven": "H", "g": 1.5, "cs": 30},
                    ("B", 9): {"opp": "A", "ven": "A", "g": 1.2, "cs": 20}}
    check_window(toy, fixture_proj, [9])
    for mode in ("missing", "venue", "double", "empty", "probability"):
        fx = [{"event": 9, "team_h": 1, "team_a": 2}]
        pr = {k: dict(v) for k, v in fixture_proj.items()}
        if mode == "missing":
            pr.pop(("A", 9))
        elif mode == "venue":
            pr[("A", 9)]["ven"] = "A"
        elif mode == "double":
            fx *= 2
        elif mode == "empty":
            fx = []
        else:
            pr[("A", 9)]["cs"] = 101
        toy.fixtures = fx
        try:
            check_window(toy, pr, [9])
        except ValueError:
            pass
        else:
            raise AssertionError(f"Bad fixture coverage accepted: {mode}")
    print("Self-check passed: legal scoring, beneficial upgrade, six invalid squads and five fixture boundaries")


def main(ttl):
    fplapi.CACHE_DIR = HERE / ".cache"
    fplapi.CACHE_DIR.mkdir(exist_ok=True)
    ctx = analysis.Ctx.load(ttl=ttl)
    if not ctx.predicted:
        raise ValueError("Predicted lineups unavailable; manual minutes review required")
    gw = ctx.next_event()
    if not gw:
        raise ValueError("No upcoming gameweek")
    deadline = next(e["deadline_time"] for e in ctx.events if e["id"] == gw)
    if datetime.fromisoformat(deadline.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
        raise ValueError("Next-gameweek deadline is stale")
    gws = list(range(gw, min(39, gw + 8)))
    proj = ffs.projections(ttl=ttl)
    check_window(ctx, proj, gws)
    try:
        market = odds.by_club(ctx, ttl=ttl)
    except fplapi.FplError as ex:
        print(f"Market unavailable; FFS fallback: {ex}")
        market = {}
    live = scout.season_live(ctx, gw - 1, ttl=ttl)
    if not fplapi.HEALTH.get("Scout history", {}).get("ok"):
        raise ValueError("Historical gameweek coverage incomplete; comparison withheld")
    baselines = analysis.team_attack_baselines(ctx)
    priors = transfers.positional_priors(ctx)
    candidates, watch = [], []
    for el in ctx.players.values():
        if el.get("minutes", 0) < 180 or el.get("starts", 0) < 2:
            continue
        points = planner.player_weeks(el, ctx, proj, market, baselines, priors, gws, live)
        recent = (live.get(el["id"]) or [])[-3:]
        row = {"id": el["id"], "name": el["web_name"], "pos": ctx.pos(el),
               "club": ctx.team_name(el["team"]), "cost": el["now_cost"],
               "minutes": el["minutes"], "starts": el.get("starts", 0),
               "recent_starts": sum(x["status"] == "started" for x in recent),
               "predicted": ctx.is_predicted(el), "status": el.get("status"),
               "chance": el.get("chance_of_playing_next_round"),
               "news": el.get("news"), "news_added": el.get("news_added"),
               "xgi90": el.get("expected_goal_involvements_per_90"),
               "penalties_order": el.get("penalties_order"),
               "weeks": points, "recent": recent}
        if (row["status"] != "a" or row["predicted"] is False
                or row["recent_starts"] < 2
                or (row["chance"] is not None and row["chance"] < 100)):
            watch.append(row)
        else:
            candidates.append(row)
    if any(sum(p["pos"] == pos for p in candidates) < n for pos, n in QUOTAS.items()):
        raise ValueError("Insufficient fit, established starters")
    by_id = {p["id"]: p for p in candidates}
    captains = sorted(candidates, key=lambda p: -sum(p["weeks"][:4]))[:5]
    proposals = {}
    for horizon in (4, 6, 8):
        horizon = min(horizon, len(gws))
        for budget in (99.5, 100.0):
            for captain in [None] + captains:
                pool = [{**p, "price": p["cost"] / 10,
                         "value": sum(0.9 ** j * x for j, x in enumerate(p["weeks"][:horizon]))
                         * (2 if captain and p["id"] == captain["id"] else 1)}
                        for p in candidates]
                seed = squadbuilder.best_squad(pool, budget)
                if not seed:
                    continue
                ids = tuple(sorted(p["id"] for p in seed["xi"] + seed["bench"]))
                rows = [by_id[i] for i in ids]
                result = score_squad(rows, len(gws))
                proposals[ids] = {"players": list(ids), "cost": sum(p["cost"] for p in rows),
                                  "seed_horizon": horizon, "seed_budget": budget,
                                  "captain_seed": captain["name"] if captain else None, **result}
    if not proposals:
        raise ValueError("Builder found no legal squad")
    # Compare structural alternatives rather than treating one local optimum as truth.
    structures = {"balanced-no-12m": [p["id"] for p in candidates if p["cost"] >= 120]}
    for p in candidates:
        if p["club"] == "CHE" and p["pos"] == "MID" and p["cost"] >= 65:
            structures[f"without-{p['name']}"] = [p["id"]]
    for label, excluded in structures.items():
        seed = squadbuilder.best_squad([
            {**p, "price": p["cost"] / 10,
             "value": sum(0.9 ** j * x for j, x in enumerate(p["weeks"]))}
            for p in candidates if p["id"] not in excluded], 100.0)
        if seed:
            ids = tuple(sorted(p["id"] for p in seed["xi"] + seed["bench"]))
            proposals[ids] = {"players": list(ids), "cost": sum(by_id[i]["cost"] for i in ids),
                              "seed_horizon": len(gws), "seed_budget": 100,
                              "captain_seed": label, "excluded": excluded,
                              **score_squad([by_id[i] for i in ids], len(gws))}
    for proposal in list(proposals.values()):
        allowed = [p for p in candidates if p["id"] not in proposal.get("excluded", [])]
        rows = improve([by_id[i] for i in proposal["players"]], allowed, len(gws))
        ids = tuple(sorted(p["id"] for p in rows))
        proposals[ids] = {"players": list(ids), "cost": sum(p["cost"] for p in rows),
                          "seed_horizon": proposal["seed_horizon"],
                          "seed_budget": proposal["seed_budget"],
                          "captain_seed": proposal["captain_seed"], "refined": True,
                          "excluded": proposal.get("excluded", []),
                          **score_squad(rows, len(gws))}
    ranked = sorted(proposals.values(), key=lambda s: -s["objective"])
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "gameweek": gw, "deadline_utc": deadline, "gws": gws,
              "fixture_rows": len(ctx.fixtures), "player_rows": len(ctx.players),
              "source_health": fplapi.health_report(), "market_clubs": len(market),
              "source_cache_times_utc": {p.name: datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()
                                         for p in fplapi.CACHE_DIR.glob("*.json")
                                         if len(p.stem) == 20 and all(c in "0123456789abcdef" for c in p.stem)},
              "rules_settings": ctx.boot.get("game_settings"), "chips": ctx.boot.get("chips"),
              "events": ctx.events, "candidate_count": len(candidates),
              "players": candidates, "watch": watch, "proposals": ranked,
              "model": "existing candidate_score + planner minutes; heuristic seeds; no transfers or chips"}
    (HERE / ".cache" / "preparation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    top = ranked[0]
    print(json.dumps({"gw": gw, "deadline": deadline, "candidates": len(candidates),
                      "squads_compared": len(ranked), "objective": top["objective"],
                      "cost": top["cost"] / 10,
                      "squad": [{"name": by_id[i]["name"], "club": by_id[i]["club"],
                                 "pos": by_id[i]["pos"], "price": by_id[i]["cost"] / 10,
                                 "xp": [round(x, 2) for x in by_id[i]["weeks"][:4]]}
                                for i in top["players"]],
                      "health": report["source_health"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ttl", type=int, default=900)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        main(args.ttl)
