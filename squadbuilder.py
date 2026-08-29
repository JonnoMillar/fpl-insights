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
