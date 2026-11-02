"""
Your season as a manager: what each transfer has returned, where the
armband went, and what the bench and chips left behind.

Everything is read back from finished gameweeks only. A gameweek still being
played would let a captain who has not kicked a ball yet look like a miss.

The maths is kept apart from the fetching so tests can feed it plain dicts:
`transfer_ledger`, `captaincy` and `chip_returns` take the public API's own
shapes (entry transfers, entry history, picks) plus {gw: {player: points}}.
"""

import fplapi

# A finished gameweek's live data never changes again.
FINISHED_TTL = 60 * 60 * 24 * 30
# Form before a move: points per gameweek over this many weeks before it.
FORM_WEEKS = 4
HIT = 4


def points_by_gw(lives):
    """{gw: event_live payload} -> {gw: {player_id: points}}. Double
    gameweeks arrive already summed in the live stats."""
    return {gw: {el["id"]: (el.get("stats") or {}).get("total_points", 0)
                 for el in live.get("elements", [])}
            for gw, live in lives.items()}


def transfer_ledger(transfers, history, points, chips=()):
    """One row per transfer: the signing's points against the sold player's
    over every finished week the signing was held, less any hit.

    A signing is held from the transfer's gameweek until the week before he
    is sold again; a Free Hit squad reverts, so its moves last one week. Hits
    land on the last transfers made in a week - the first ones used the free
    transfers. Moves with no finished week yet are left out."""
    weeks = sorted(points)
    free_hit = {c["event"] for c in chips if c.get("name") == "freehit"}
    cost = {h["event"]: h.get("event_transfers_cost", 0) for h in history}
    moves = sorted(transfers, key=lambda t: (t["event"], t.get("time", "")))

    paid = set()
    for gw in {t["event"] for t in moves}:
        week = [i for i, t in enumerate(moves) if t["event"] == gw]
        n_paid = cost.get(gw, 0) // HIT
        if n_paid:
            paid.update(week[-n_paid:])

    rows = []
    for i, t in enumerate(moves):
        start, pin, pout = t["event"], t["element_in"], t["element_out"]
        sold = next((u["event"] for u in moves[i + 1:] if u["element_out"] == pin), None)
        end = start if start in free_hit else (sold - 1 if sold else weeks[-1] if weeks else start)
        held = [gw for gw in weeks if start <= gw <= end]
        if not held:
            continue
        pts_in = sum(points[gw].get(pin, 0) for gw in held)
        pts_out = sum(points[gw].get(pout, 0) for gw in held)
        before = [gw for gw in weeks if start - FORM_WEEKS <= gw < start]
        hit = HIT if i in paid else 0
        rows.append({
            "gw": start, "in": pin, "out": pout,
            "in_cost": t.get("element_in_cost"), "out_cost": t.get("element_out_cost"),
            "weeks": len(held), "first": held[0], "last": held[-1],
            "pts_in": pts_in, "pts_out": pts_out, "hit": hit,
            "net": pts_in - pts_out - hit,
            "form_before": (sum(points[gw].get(pin, 0) for gw in before) / len(before)
                            if before else None),
            "form_after": pts_in / len(held),
        })
    return rows


def captaincy(picks_by_gw, points, minutes):
    """Per finished week: whose armband scored, against the best scorer in
    your starting XI. The armband passes to the vice when the captain does
    not play. `lost` is in final points, so it counts the multiplier."""
    rows = []
    for gw in sorted(picks_by_gw):
        if gw not in points:
            continue
        picks = picks_by_gw[gw]["picks"]
        pts, mins = points[gw], minutes.get(gw, {})
        cap = next((p for p in picks if p["is_captain"]), None)
        vice = next((p for p in picks if p["is_vice_captain"]), None)
        if not cap:
            continue
        # After auto-subs the multiplier can sit on the vice, so take the
        # week's largest: 3 in a Triple Captain week, else 2.
        mult = max([2] + [p.get("multiplier", 0) for p in picks])
        chosen = cap["element"]
        if not mins.get(chosen) and vice and mins.get(vice["element"]):
            chosen = vice["element"]
        xi = [p["element"] for p in picks if p["position"] <= 11]
        best = max(xi, key=lambda pid: (pts.get(pid, 0), pid == chosen))
        rows.append({
            "gw": gw, "captain": chosen, "cap_pts": pts.get(chosen, 0),
            "best": best, "best_pts": pts.get(best, 0), "mult": mult,
            "lost": (pts.get(best, 0) - pts.get(chosen, 0)) * (mult - 1),
        })
    return rows


def chip_returns(history, chips, cap_rows):
    """What each chip added: Triple Captain the extra multiple of the
    armband's score, Bench Boost the bench's points. Wildcard and Free Hit
    have no direct counterfactual here, so they carry only their week."""
    bench = {h["event"]: h.get("points_on_bench", 0) for h in history}
    cap = {r["gw"]: r["cap_pts"] for r in cap_rows}
    out = []
    for c in chips:
        gw, name = c["event"], c["name"]
        gain = cap.get(gw) if name == "3xc" else bench.get(gw) if name == "bboost" else None
        out.append({"name": name, "gw": gw, "gain": gain})
    return out


def review(entry_id, ctx, ttl=fplapi.DEFAULT_TTL):
    """Fetch and assemble the season review. Raises fplapi.FplError when a
    source is missing; the caller fails soft."""
    finished = [e["id"] for e in ctx.events if e.get("finished")]
    if not finished:
        return None
    history = fplapi.entry_history(entry_id, ttl=ttl)
    transfers = fplapi.get_json(f"{fplapi.BASE}/entry/{entry_id}/transfers/", ttl=ttl)
    lives = {gw: fplapi.event_live(gw, ttl=FINISHED_TTL) for gw in finished}
    points = points_by_gw(lives)
    minutes = {gw: {el["id"]: (el.get("stats") or {}).get("minutes", 0)
                    for el in live.get("elements", [])} for gw, live in lives.items()}
    played = [h for h in history.get("current", []) if h["event"] in points]
    picks = {h["event"]: fplapi.entry_picks(entry_id, h["event"], ttl=FINISHED_TTL)
             for h in played}
    chips = [c for c in history.get("chips", []) if c["event"] in points]

    ledger = transfer_ledger(transfers, played, points, chips)
    caps = captaincy(picks, points, minutes)
    boosted = {c["event"] for c in chips if c["name"] == "bboost"}

    ids = {r["in"] for r in ledger} | {r["out"] for r in ledger}
    ids |= {r[k] for r in caps for k in ("captain", "best")}
    players = {}
    for pid in ids:
        el = ctx.players.get(pid)
        players[pid] = {"name": el["web_name"] if el else "Unknown",
                        "photo": fplapi.photo_data_uri(el) if el else None}
    return {
        "upto": max(points),
        "ledger": ledger,
        "captaincy": caps,
        "chips": chip_returns(played, chips, caps),
        "bench": sum(h.get("points_on_bench", 0) for h in played if h["event"] not in boosted),
        "hits": sum(h.get("event_transfers_cost", 0) for h in played),
        "players": players,
    }
