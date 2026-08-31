#!/usr/bin/env python3
"""
A constrained best-team builder: given a pool of candidates, find the
highest-value legal selection within budget.

Deliberately generic - this module has no idea what "value" means (points,
xG, anything with higher-is-better semantics works), and no idea where a
candidate came from. That split is what lets Free Hit and Wildcard share
one algorithm with two different objectives (chips.py builds the pool and
picks the mode; this module just solves the selection problem).

No ILP solver dependency: a greedy value-per-cost fill, then a
hill-climbing swap pass. Both are approximations, not a proof of
optimality, and callers should say so rather than imply a solved
optimization. The one constraint this is genuinely weak against is the
3-per-club limit - a hill-climb only ever tries one swap at a time, so an
early greedy pick that locks in 3 players from one club can block a better
combination only a 2-for-2 trade would reach. Worth a sanity check against
a club-limit-relaxed run before trusting a surprising answer.
"""

CLUB_LIMIT = 3

# Correctness guard, not a performance one - this runs unattended on the
# existing build cadence. Protects against a hill-climb's real failure
# mode of two swaps flipping back and forth forever instead of converging.
MAX_SWAPS = 50

# The formations FPL itself allows: 1 GKP fixed, (DEF, MID, FWD) from this
# list, always summing to 10 outfield players.
FORMATIONS = [
    (3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2),
    (4, 5, 1), (5, 3, 2), (5, 4, 1),
]


def _by_position(pool):
    out = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for p in pool:
        out[p["pos"]].append(p)
    return out


def _greedy_fill(by_pos, quotas, budget, club_counts=None):
    """Highest value-per-cost first, respecting position quotas, budget
    and the 3-per-club cap. `club_counts` seeds club membership from
    players already picked outside this call (e.g. a bench picked before
    the XI) so the combined squad still respects the cap jointly. Returns
    None if a quota cannot be filled within budget at all."""
    club_counts = dict(club_counts or {})
    ranked = {
        pos: sorted(players, key=lambda p: -p["value"] / max(p["price"], 0.1))
        for pos, players in by_pos.items()
    }
    picks, spent = [], 0.0
    for pos, need in quotas.items():
        taken = 0
        for p in ranked[pos]:
            if taken >= need:
                break
            if spent + p["price"] > budget + 1e-9:
                continue
            if club_counts.get(p["club"], 0) >= CLUB_LIMIT:
                continue
            picks.append(p)
            spent += p["price"]
            club_counts[p["club"]] = club_counts.get(p["club"], 0) + 1
            taken += 1
        if taken < need:
            return None
    return picks


def _cheapest_fill(by_pos, quotas, club_counts=None):
    """Same shape as _greedy_fill, but cheapest-first rather than
    value-per-cost first - for Free Hit's bench, which never plays and
    only needs to be legal and affordable, not good."""
    club_counts = dict(club_counts or {})
    picks = []
    for pos, need in quotas.items():
        taken = 0
        for p in sorted(by_pos[pos], key=lambda p: p["price"]):
            if taken >= need:
                break
            if club_counts.get(p["club"], 0) >= CLUB_LIMIT:
                continue
            picks.append(p)
            club_counts[p["club"]] = club_counts.get(p["club"], 0) + 1
            taken += 1
        if taken < need:
            return None
    return picks


def _hill_climb(picks, by_pos, budget, other_club_counts=None):
    """Repeatedly swap one held player for a higher-value affordable
    replacement in the same position, until no swap improves the total or
    MAX_SWAPS is hit. `other_club_counts` covers players held outside this
    group (e.g. the bench, while climbing the XI) who still count against
    the 3-per-club cap."""
    other_club_counts = other_club_counts or {}
    picks = list(picks)
    held_ids = {p["id"] for p in picks}
    spent = sum(p["price"] for p in picks)
    own_club_counts = {}
    for p in picks:
        own_club_counts[p["club"]] = own_club_counts.get(p["club"], 0) + 1

    def total_club(club):
        return own_club_counts.get(club, 0) + other_club_counts.get(club, 0)

    converged = False
    for _ in range(MAX_SWAPS):
        best = None  # (gain, index_in_picks, candidate)
        for i, out in enumerate(picks):
            free_budget = budget - spent + out["price"]
            for cand in by_pos[out["pos"]]:
                if cand["id"] in held_ids:
                    continue
                if cand["price"] > free_budget + 1e-9:
                    continue
                cand_total = total_club(cand["club"])
                if cand["club"] == out["club"]:
                    cand_total -= 1  # the outgoing player frees his own slot
                if cand_total >= CLUB_LIMIT:
                    continue
                gain = cand["value"] - out["value"]
                if gain <= 1e-9:
                    continue
                if best is None or gain > best[0]:
                    best = (gain, i, cand)
        if best is None:
            converged = True
            break
        _gain, i, cand = best
        out = picks[i]
        held_ids.discard(out["id"])
        held_ids.add(cand["id"])
        spent += cand["price"] - out["price"]
        own_club_counts[out["club"]] -= 1
        own_club_counts[cand["club"]] = own_club_counts.get(cand["club"], 0) + 1
        picks[i] = cand
    if not converged:
        print(f"[squadbuilder] hill-climb did not converge within {MAX_SWAPS} swaps")
    return picks


def best_xi(pool, budget):
    """The highest-value legal starting XI within budget - formation
    chosen to maximize total XI value. The bench is filled cheaply first
    (it never plays on a Free Hit), then whatever budget remains goes
    entirely into the XI."""
    by_pos = _by_position(pool)
    best = None
    for d, m, fw in FORMATIONS:
        bench_quota = {"GKP": 1, "DEF": 5 - d, "MID": 5 - m, "FWD": 3 - fw}
        bench = _cheapest_fill(by_pos, bench_quota)
        if bench is None:
            continue
        bench_cost = sum(p["price"] for p in bench)
        bench_ids = {p["id"] for p in bench}
        bench_club_counts = {}
        for p in bench:
            bench_club_counts[p["club"]] = bench_club_counts.get(p["club"], 0) + 1

        remaining_by_pos = {
            pos: [p for p in players if p["id"] not in bench_ids]
            for pos, players in by_pos.items()
        }
        xi_quotas = {"GKP": 1, "DEF": d, "MID": m, "FWD": fw}
        xi_budget = budget - bench_cost
        picks = _greedy_fill(remaining_by_pos, xi_quotas, xi_budget, bench_club_counts)
        if picks is None:
            continue
        picks = _hill_climb(picks, remaining_by_pos, xi_budget, bench_club_counts)

        value = sum(p["value"] for p in picks)
        cost = sum(p["price"] for p in picks) + bench_cost
        if best is None or value > best["value"]:
            best = {"formation": (d, m, fw), "xi": picks, "bench": bench,
                    "value": value, "cost": cost}
    return best


def _floor_cost(by_pos, quotas):
    """The cheapest a set of quotas can possibly be filled for, ignoring the
    club cap. A lower bound, which is all a budget reserve needs."""
    total = 0.0
    for pos, need in quotas.items():
        prices = sorted(p["price"] for p in by_pos.get(pos, []))
        if len(prices) < need:
            return None
        total += sum(prices[:need])
    return total


# Headroom on top of the bench's floor price, so the XI cannot spend the
# squad down to the point where the only affordable bench is the four
# cheapest men in the game and the club cap then makes even that illegal.
BENCH_CUSHION = 1.5


def best_squad(pool, budget, bench_reserve_frac=0.12):
    """The highest-value legal 15 within budget: the XI hill-climbed for
    value the same as best_xi, the bench filled by the same value-per-cost
    rule from what's left rather than pure minimum price - a Wildcard
    squad has to survive more than one week, so its bench should be able
    to play if called on.

    The reserve held back for that bench is the greater of a flat fraction
    and what a legal bench actually costs. The fraction alone was not safe:
    at a 99.9m budget it held back 12.0m while the four cheapest bench slots
    could not be filled for less than 17.5m, so every formation failed its
    bench fill and the whole recommendation returned None - silently, since
    the caller renders nothing rather than an error. Whether that happened
    depended on how much of the XI budget the hill-climb chose to spend,
    which is to say on the pool's values, which is to say it broke without
    anything about this function changing."""
    by_pos = _by_position(pool)
    best = None
    for d, m, fw in FORMATIONS:
        xi_quotas = {"GKP": 1, "DEF": d, "MID": m, "FWD": fw}
        bench_quotas = {"GKP": 1, "DEF": 5 - d, "MID": 5 - m, "FWD": 3 - fw}
        floor = _floor_cost(by_pos, bench_quotas)
        if floor is None:
            continue
        reserve = max(budget * bench_reserve_frac, floor + BENCH_CUSHION)
        xi_budget = budget - reserve
        if xi_budget <= 0:
            continue
        picks = _greedy_fill(by_pos, xi_quotas, xi_budget)
        if picks is None:
            continue
        picks = _hill_climb(picks, by_pos, xi_budget)
        xi_cost = sum(p["price"] for p in picks)

        held_ids = {p["id"] for p in picks}
        club_counts = {}
        for p in picks:
            club_counts[p["club"]] = club_counts.get(p["club"], 0) + 1
        remaining_by_pos = {
            pos: [p for p in players if p["id"] not in held_ids]
            for pos, players in by_pos.items()
        }
        bench = _greedy_fill(remaining_by_pos, bench_quotas,
                             budget - xi_cost, club_counts)
        if bench is None:
            continue

        value = sum(p["value"] for p in picks)
        cost = xi_cost + sum(p["price"] for p in bench)
        if best is None or value > best["value"]:
            best = {"formation": (d, m, fw), "xi": picks, "bench": bench,
                    "value": value, "cost": cost}
    return best
