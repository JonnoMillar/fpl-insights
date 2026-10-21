#!/usr/bin/env python3
"""
A transfer plan across the next few gameweeks: which moves, in which week.

The single-week suggestion lists rank a move by its gain over a window, as
though it were made today. That answers the wrong question twice over:

* **Timing.** A defender with Liverpool away and City away before a kind run
  scores well over five weeks, so "buy him now" topped the list - when the
  same move made two weeks later keeps those two weeks out of the squad and
  leaves this week's free transfer for something else. A plan chooses the
  week as well as the move.
* **Squad structure.** A squad is not fifteen interchangeable slots. Most
  managers carry a few minimum-price "enablers" who exist to fund the
  starters. Upgrading one to a mid-price player only benches a better player
  than him, so every bench upgrade was really money moved from the XI to the
  bench. Here the number of cheap players is held: an enabler leaves only
  for another cheap player, or in the same week as a cheap player arrives in
  a different position (the "move the enabler to forward to fund a midfield
  upgrade" restructure, which costs two transfers for one real upgrade and
  has to earn both).

How the search works, kept deliberately simple:

* Every player gets a projected score per gameweek from the same
  bootstrap-only scorer the rest of the transfer advice uses.
* A gameweek's value is the best legal XI from the fifteen, plus the
  captain's second share, plus small weights on the bench in sub order
  (the chance each one comes on), or the whole bench on Bench Boost week.
* A beam search walks the weeks. Each week a state may roll, make one move,
  or make two, from a move list generated once from the current squad.
  Hits cost four, each move also pays a small margin (projections are
  noisy and a move that only just clears zero is a coin flip), and a free
  transfer still banked at the end is worth FT_VALUE. Later weeks are
  discounted because the projections for them are less certain.

None of this is a proof of the best plan: the move list is bounded, the
beam is finite, and the plan never sells a player it bought itself. It
reruns every build, so a plan for three weeks ahead is a default, not a
commitment - injuries and price changes will move it.
"""

import squadbuilder
import transfers

HORIZON = 8          # gameweeks scored
ACT_WEEKS = 6        # weeks a move may be planned in; a later one cannot pay back
SHOW_WEEKS = 3       # weeks of moves shown before "later gameweeks"
CHIP_LOOKAHEAD = 12  # weeks scanned for an unused chip's best remaining week
DECAY = 0.9          # per-week discount: later projections are less certain
FT_VALUE = 1.5       # a free transfer still banked at the end
# Per move, on top of any hit: projections are noisy and the best-looking
# move of many is flattered by that noise, so a move has to clear this to
# be worth a transfer. Two points let a one-week haul (Neto, form 10 on
# 0.38 xGI/90) look like a reason to move; three makes rolling the default.
TRANSFER_MARGIN = 3.0
# A hit is taken only when it is urgent, and only this week, where the news
# is known: a starter ruled out, or a signing who is clearly elite on the
# underlying numbers with a fair fixture next. A pair that merely projects
# well rolls a week and is made with two free transfers instead.
URGENT_CHANCE = 25        # chance of playing at or below this is "ruled out"
MUST_HAVE_TOP = 5         # top N in the position on xGI per 90
MUST_HAVE_MINUTES = 450   # enough football for per-90 numbers to mean much
MUST_HAVE_MAX_FDR = 3     # FPL difficulty of his next fixture
# A chip played now must beat its best later week by this much. With a
# flat bench every week looks alike, and the first tie would otherwise burn
# Bench Boost on whichever week the noise favoured, and with it the
# chance to build a bench worth boosting.
CHIP_MARGIN = 2.0
FT_CAP = 5
HIT = 4
MAX_PER_WEEK = 2

# Chance each bench slot comes on: the first outfield sub, then the next
# two, and the reserve keeper. Small, but not zero - the first sub plays
# whenever a starter does not.
BENCH_WEIGHTS = (0.21, 0.06, 0.02)
BENCH_GK_WEIGHT = 0.03

BEAM_WIDTH = 30
LAYER_KEEP = 60
SINGLES_PER_OUT = 8
CHEAP_PER_OUT = 3
CANDIDATES_PER_POS = 15
CHEAP_CANDIDATES_PER_POS = 6


def weights(n):
    return [DECAY ** i for i in range(n)]


def is_cheap(row, caps):
    return transfers.is_cheap(row["price"], row["pos"], caps)


def best_xi(pool):
    """The best formation from a fifteen of 2/5/5/3, as squadbuilder.owned_xi
    picks it, without its club check - a restructure's first leg can sit
    one over a club limit until its second leg lands, and still has to be
    scored to be ranked."""
    ranked = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for p in pool:
        ranked[p["pos"]].append(p)
    for rows in ranked.values():
        rows.sort(key=lambda p: -p["value"])
    best = None
    for d, m, fw in squadbuilder.FORMATIONS:
        xi = (ranked["GKP"][:1] + ranked["DEF"][:d]
              + ranked["MID"][:m] + ranked["FWD"][:fw])
        value = sum(p["value"] for p in xi)
        if best is None or value > best["value"]:
            best = {"formation": (d, m, fw), "xi": xi, "value": value}
    ids = {p["id"] for p in best["xi"]}
    best["bench"] = [p for p in pool if p["id"] not in ids]
    return best


class Planner:
    """The search, over plain tables so it can be tested without the API.

    rows: {id: {"pos", "club", "price"}} for every player the plan may hold;
        "price" is the buying price.
    values: {id: [projected points per week index]}, at least HORIZON long,
        longer where chip lookahead needs it.
    squad: the fifteen ids held now. sell: {id: selling price} for them.
    caps: {pos: the most a cheap player in that position costs}.
    chips: [{"key": "bboost" | "3xc", "first": i, "last": i}] in week-index
        space, one per chip still available (a chip per half, so the same
        chip may appear twice across the half boundary).
    urgent: ids whose move justifies a hit in the first week - squad
        starters ruled out, and must-have signings. No hits otherwise.
    """

    def __init__(self, rows, values, squad, sell, bank, ft, caps,
                 chips=(), horizon=HORIZON, act_weeks=ACT_WEEKS,
                 enabler_floor=None, urgent=()):
        self.rows, self.values = rows, values
        self.urgent = frozenset(urgent)
        self.squad0 = frozenset(squad)
        self.sell0 = dict(sell)
        self.bank0, self.ft0 = bank, ft
        self.caps = caps
        self.chips = list(chips)
        self.h = horizon
        self.act = min(act_weeks, horizon)
        self.w = weights(max(horizon, max((c["last"] + 1 for c in self.chips),
                                          default=0)))
        self._cache = {}
        self.enablers = self._enablers()
        self.floor = (len(self.enablers) if enabler_floor is None
                      else enabler_floor)
        self.moves = self._moves()

    # --- scoring a squad for one week ---------------------------------

    def week(self, ids, i):
        key = (ids, i)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        pool = [{"id": p, "pos": self.rows[p]["pos"],
                 "value": self.values[p][i] if i < len(self.values[p]) else 0.0}
                for p in ids]
        best = best_xi(pool)
        xi = sorted(best["xi"], key=lambda p: -p["value"])
        bench = best["bench"]
        gk = [p for p in bench if p["pos"] == "GKP"]
        outfield = sorted((p for p in bench if p["pos"] != "GKP"),
                          key=lambda p: -p["value"])
        xi_val = sum(p["value"] for p in xi)
        cap = xi[0]["value"] if xi else 0.0
        normal_bench = (sum(wt * p["value"] for wt, p in zip(BENCH_WEIGHTS, outfield))
                        + BENCH_GK_WEIGHT * sum(p["value"] for p in gk))
        out = {
            "xi": [p["id"] for p in xi],
            "bench": [p["id"] for p in gk + outfield],
            "captain": xi[0]["id"] if xi else None,
            "vice": xi[1]["id"] if len(xi) > 1 else None,
            "formation": best["formation"],
            "xi_val": xi_val, "cap_val": cap,
            "bench_full": sum(p["value"] for p in bench),
            "normal": xi_val + cap + normal_bench,
            "normal_bench": normal_bench,
        }
        self._cache[key] = out
        return out

    def score(self, ids, i, chip=None):
        wk = self.week(ids, i)
        if chip == "bboost":
            return wk["normal"] - wk["normal_bench"] + wk["bench_full"]
        if chip == "3xc":
            return wk["normal"] + wk["cap_val"]
        return wk["normal"]

    def chip_gain(self, ids, j, key):
        """A chip's extra points in week j. Not discounted like the rest:
        the discount is for uncertainty, and an uncertain later week is a
        reason to wait and see, not a reason to burn a chip early."""
        return self.score(ids, j, key) - self.score(ids, j)

    def chip_option(self, ids, played, after):
        """What each still-unplayed chip is worth if played in its best
        remaining week with this squad - so holding a chip is compared
        against playing it, not against nothing."""
        total = 0.0
        for n, c in enumerate(self.chips):
            if n in played:
                continue
            best = 0.0
            for j in range(max(c["first"], after + 1), c["last"] + 1):
                best = max(best, self.chip_gain(ids, j, c["key"]))
            total += best
        return total

    def future(self, ids, after):
        return sum(self.w[j] * self.score(ids, j) for j in range(after + 1, self.h))

    # --- structure -------------------------------------------------------

    def _enablers(self):
        """The cheap players the current squad keeps on its bench."""
        totals = {p: sum(wt * v for wt, v in zip(self.w, self.values[p][:self.h]))
                  for p in self.squad0}
        pool = [{"id": p, "pos": self.rows[p]["pos"], "value": totals[p]}
                for p in self.squad0]
        bench = [p["id"] for p in best_xi(pool)["bench"]]
        cheap = sorted((p for p in bench if is_cheap(self.rows[p], self.caps)),
                       key=lambda p: self.rows[p]["price"])
        return cheap[:transfers.MAX_ENABLERS]

    def legal(self, ids, bank):
        if bank < -1e-9 or len(ids) != 15:
            return False
        clubs = {}
        cheap = 0
        for p in ids:
            r = self.rows[p]
            clubs[r["club"]] = clubs.get(r["club"], 0) + 1
            if clubs[r["club"]] > transfers.SQUAD_LIMIT_PER_CLUB:
                return False
            cheap += is_cheap(r, self.caps)
        return cheap >= self.floor

    # --- the move list -------------------------------------------------

    def _moves(self):
        """(out, in) pairs worth trying, built once from the current squad.

        Per player: the best few replacements by their best-timed raw gain,
        plus the best few cheap players in his position whatever their gain
        - those are the enabler swaps and the downgrades that fund an
        upgrade elsewhere, neither of which looks good on its own."""
        w = self.w[:self.h]

        def horizon(p):
            return sum(wt * v for wt, v in zip(w, self.values[p][:self.h]))

        by_pos = {}
        for p, r in self.rows.items():
            if p in self.squad0:
                continue
            by_pos.setdefault(r["pos"], []).append(p)
        cands = {}
        for pos, ids in by_pos.items():
            ranked = sorted(ids, key=lambda p: -horizon(p))
            cheap = [p for p in ranked if is_cheap(self.rows[p], self.caps)]
            cands[pos] = (list(dict.fromkeys(ranked[:CANDIDATES_PER_POS]
                                             + cheap[:CHEAP_CANDIDATES_PER_POS])),
                          cheap[:CHEAP_CANDIDATES_PER_POS])

        moves = set()
        for o in self.squad0:
            pos = self.rows[o]["pos"]
            pool, cheap = cands.get(pos, ([], []))
            scored = []
            for c in pool:
                diff = [wt * (self.values[c][j] - self.values[o][j])
                        for j, wt in enumerate(w)]
                best = max(sum(diff[t:]) for t in range(self.act)) if self.act else 0.0
                scored.append((best, c))
            scored.sort(key=lambda x: -x[0])
            for gain, c in scored[:SINGLES_PER_OUT]:
                if gain > 0:
                    moves.add((o, c))
            for c in cheap[:CHEAP_PER_OUT]:
                moves.add((o, c))
        return sorted(moves)

    # --- the search ----------------------------------------------------

    def _eval(self, st, i):
        return (st["realized"] + self.future(st["ids"], i)
                + self.chip_option(st["ids"], st["played"], i)
                + FT_VALUE * st["ft"])

    def _apply(self, st, move):
        o, c = move
        if o not in st["ids"] or c in st["ids"] or c in st["sold"]:
            return None
        if o not in self.squad0:
            return None
        ids = (st["ids"] - {o}) | {c}
        return {**st, "ids": ids, "bank": st["bank"] + self.sell0[o] - self.rows[c]["price"],
                "sold": st["sold"] | {o}, "week_moves": st["week_moves"] + [move]}

    def _close_week(self, st, i, chip=None, chip_index=None):
        """Score week i for a state whose moves for that week are made."""
        n = len(st["week_moves"])
        free = st["ft"]
        hits = max(0, n - free)
        realized = (st["realized"] + self.w[i] * self.score(st["ids"], i)
                    + (self.chip_gain(st["ids"], i, chip) - CHIP_MARGIN if chip else 0.0)
                    - HIT * hits - TRANSFER_MARGIN * n)
        played = st["played"] | ({chip_index} if chip_index is not None else set())
        # An enabler swapped for another cheap player who still sits on the
        # bench is only worth it for a Bench Boost; until one is played in
        # the plan the move is pending, and a plan cannot end with one.
        xi = set(self.week(st["ids"], i)["xi"])
        dormant = sum(1 for o, c in st["week_moves"]
                      if is_cheap(self.rows[o], self.caps)
                      and is_cheap(self.rows[c], self.caps) and c not in xi)
        pending = 0 if chip == "bboost" else st["pending"] + dormant
        week = {"i": i, "moves": st["week_moves"], "hits": hits,
                "ft_before": free, "chip": chip, "bank": st["bank"]}
        nxt = {"ids": st["ids"], "bank": st["bank"], "sold": st["sold"],
               "realized": realized, "played": frozenset(played),
               "ft": min(FT_CAP, max(0, free - n) + 1),
               "weeks": st["weeks"] + [week], "week_moves": [],
               "moved": st["moved"] + n, "pending": pending}
        nxt["eval"] = self._eval(nxt, i)
        return nxt

    def run(self):
        start = {"ids": self.squad0, "bank": self.bank0, "sold": frozenset(),
                 "realized": 0.0, "played": frozenset(), "ft": self.ft0,
                 "weeks": [], "week_moves": [], "moved": 0, "pending": 0}
        beam = [start]
        for i in range(self.h):
            open_states = list(beam)
            layer1 = []
            if i < self.act:
                for st in beam:
                    for m in self.moves:
                        nxt = self._apply(st, m)
                        if nxt is not None:
                            layer1.append(nxt)
            # Second moves only from the most promising first moves, whether
            # or not those are legal yet: a restructure's first leg is often
            # over budget or one cheap player short until the second lands.
            # Ranked on their points from this week on, less the hit a
            # second move would cost, so a state with a free transfer left
            # is not crowded out by one without.
            open_states.extend(s for s in layer1 if self.legal(s["ids"], s["bank"]))
            if MAX_PER_WEEK >= 2 and layer1:
                for s in layer1:
                    s["_rank"] = (s["realized"] + self.future(s["ids"], i - 1)
                                  - (HIT if s["ft"] < 2 else 0))
                layer1.sort(key=lambda s: -s["_rank"])
                for s1 in layer1[:LAYER_KEEP]:
                    for m in self.moves:
                        if m[0] == s1["week_moves"][0][0]:
                            continue
                        s2 = self._apply(s1, m)
                        if s2 is not None and self.legal(s2["ids"], s2["bank"]):
                            open_states.append(s2)
            closed = []
            for st in open_states:
                if len(st["week_moves"]) > st["ft"] and not self.hit_ok(st["week_moves"], i):
                    continue
                closed.append(self._close_week(st, i))
                # One chip a week at most; each instance is one half's chip,
                # so its own week range already keeps it in that half.
                for n, c in enumerate(self.chips):
                    if n in st["played"] or not (c["first"] <= i <= c["last"]):
                        continue
                    closed.append(self._close_week(st, i, c["key"], n))
            beam = self._select(closed)
        return max((s for s in beam if not s["pending"]), key=lambda s: s["eval"])

    def hit_ok(self, moves, i):
        return i == 0 and any(o in self.urgent or c in self.urgent for o, c in moves)

    def _select(self, states):
        """Best BEAM_WIDTH distinct states, always keeping the best one that
        has made no move yet so "do nothing" can still win at the end."""
        uniq = {}
        for st in states:
            key = (st["ids"], st["ft"], round(st["bank"], 1), st["played"])
            if key not in uniq or st["eval"] > uniq[key]["eval"]:
                uniq[key] = st
        ranked = sorted(uniq.values(), key=lambda s: -s["eval"])
        keep = ranked[:BEAM_WIDTH]
        # Always keep a "do nothing" plan and one with nothing pending, so
        # either can still win at the end.
        for ok in (lambda s: s["moved"] == 0, lambda s: not s["pending"]):
            if not any(ok(s) for s in keep):
                keep.extend([s for s in ranked if ok(s)][:1])
        return keep


def baseline(planner):
    """The same squad with no transfers at all, chips still timed - what
    the plan's moves are measured against."""
    idle = Planner(planner.rows, planner.values, planner.squad0, planner.sell0,
                   planner.bank0, planner.ft0, planner.caps, planner.chips,
                   horizon=planner.h, act_weeks=0, enabler_floor=planner.floor)
    return idle.run()


# --- from the live data -------------------------------------------------

# Start chance beyond what the predicted line-up covers: his last few
# matches say what his role is now, and each week further out drifts that
# a quarter of the way back toward his season-long role - a dropped player
# often wins his place back, a new starter often loses it.
ROLE_WINDOW = 3
ROLE_REVERT = 0.75
ROLE_BOUNDS = (0.10, 0.92)   # the scorer's own benched / nailed values


def start_chances(el, ctx, live, n):
    """Start probability per week for n weeks, None where the scorer's
    own predicted-line-up reading should stand (the next week, when the
    line-up feed covers his club). All None without match history."""
    rows = (live or {}).get(el["id"])
    if not rows:
        return [None] * n
    started = [m.get("status") == "started" for m in rows]
    pred = ctx.is_predicted(el)
    known = pred is not None
    if known:
        # Next week's predicted line-up is the latest word on his role.
        started.append(pred)
    recent = sum(started[-ROLE_WINDOW:]) / len(started[-ROLE_WINDOW:])
    season = sum(started) / len(started)
    lo, hi = ROLE_BOUNDS
    out = []
    for j in range(n):
        if j == 0 and known:
            out.append(None)
            continue
        drift = 1 - ROLE_REVERT ** j
        out.append(min(hi, max(lo, recent + (season - recent) * drift)))
    return out


def player_weeks(el, ctx, proj, market, baselines, priors, gws, live=None):
    """Projected points per gameweek; a blank week is zero.

    The scorer reads injury news only through the predicted line-up, so the
    stated chance of playing is applied to the first week here, and a
    player ruled out entirely is assumed to miss the next one too.
    ponytail: flat guess at return dates; parse the news text's "expected
    back" date if this proves too blunt."""
    out = []
    for gw, chance in zip(gws, start_chances(el, ctx, live, len(gws))):
        s = transfers.candidate_score(el, ctx, proj, gw, market, baselines, priors,
                                      p_start=chance)
        out.append(s["total"] if s else 0.0)
    status = el.get("status")
    if status in ("u", "n"):
        return [0.0] * len(out)
    chance = el.get("chance_of_playing_next_round")
    if chance is not None and out:
        out[0] *= chance / 100.0
        if chance == 0 and len(out) > 1:
            out[1] *= 0.5
    return out


def chip_instances(next_gw, used, length):
    """Bench Boost and Triple Captain still available, as week ranges.

    One of each per half; the first half's must be played by GW19. Free Hit
    and Wildcard are not planned here - see the chip planner."""
    if used is None:
        return []
    out = []
    half_end = 19 if next_gw <= 19 else 38
    for key in ("bboost", "3xc"):
        if not used.get(key):
            out.append({"key": key, "first": 0,
                        "last": min(half_end - next_gw, length - 1)})
        if next_gw <= 19 and 20 - next_gw < length:
            out.append({"key": key, "first": 20 - next_gw,
                        "last": min(38 - next_gw, length - 1)})
    return out


def ruled_out(el):
    chance = el.get("chance_of_playing_next_round")
    return (el.get("status") in ("i", "s", "u", "n")
            or (chance is not None and chance <= URGENT_CHANCE))


def urgent_ids(ctx, squad, rows, caps, next_gw):
    """Players whose move may justify a hit this week.

    Selling: a starter-priced squad player ruled out - an injured enabler
    on the bench is no emergency. Buying: top MUST_HAVE_TOP in his
    position on xGI per 90 over MUST_HAVE_MINUTES+, with a next fixture of
    FPL difficulty MUST_HAVE_MAX_FDR or easier. Goalkeepers and defenders
    never qualify on numbers: their points are mostly clean sheets, which
    is the fixture, not the player.
    ponytail: xGI per 90 only; add defensive contributions if a defender
    ever clearly deserves a hit."""
    out = {p for p in squad
           if ruled_out(ctx.players[p]) and not is_cheap(rows[p], caps)}
    by_pos = {}
    for p in rows:
        el = ctx.players[p]
        if ruled_out(el) or el.get("minutes", 0) < MUST_HAVE_MINUTES:
            continue
        if rows[p]["pos"] in ("MID", "FWD"):
            by_pos.setdefault(rows[p]["pos"], []).append(el)
    for els in by_pos.values():
        els.sort(key=lambda el: -float(el.get("expected_goal_involvements_per_90") or 0))
        for el in els[:MUST_HAVE_TOP]:
            if el["id"] in squad:
                continue
            nxt = ctx.next_fixtures(el["team"], 1, next_gw)
            if nxt and nxt[0][3] == next_gw and nxt[0][2] <= MUST_HAVE_MAX_FDR:
                out.add(el["id"])
    return out


def _display_points(planner, ids, i, chip):
    wk = planner.week(ids, i)
    pts = wk["xi_val"] + wk["cap_val"] * (2 if chip == "3xc" else 1)
    if chip == "bboost":
        pts += wk["bench_full"]
    return pts


def _total(planner, state):
    """Undiscounted projected points of a finished plan, after hits."""
    ids = planner.squad0
    total = 0.0
    for wk in state["weeks"]:
        for o, c in wk["moves"]:
            ids = (ids - {o}) | {c}
        total += _display_points(planner, ids, wk["i"], wk["chip"]) - HIT * wk["hits"]
    return total


def build(ctx, squad_reports, proj, market, baselines, next_gw, bank,
          sell_values, free_ts, used=None, captain_first=None, live=None):
    """The plan for the dashboard, or None when it cannot be trusted:
    unknown selling prices or free transfers, or no gameweeks left."""
    if sell_values is None or free_ts is None or next_gw > 38:
        return None
    h = min(HORIZON, 39 - next_gw)
    length = max(h, min(CHIP_LOOKAHEAD, 39 - next_gw))
    gws = list(range(next_gw, next_gw + length))
    priors = transfers.positional_priors(ctx)
    squad = {r.element["id"] for r in squad_reports}

    rows, values = {}, {}
    for el in ctx.players.values():
        pid = el["id"]
        if pid not in squad and not transfers._eligible(el, ctx):
            continue
        weeks = player_weeks(el, ctx, proj, market, baselines, priors, gws, live)
        if pid not in squad and sum(weeks[:h]) <= 0:
            continue
        rows[pid] = {"pos": ctx.pos(el), "club": ctx.team_name(el["team"]),
                     "price": el["now_cost"] / 10.0}
        values[pid] = weeks

    caps = transfers.price_caps(ctx)
    planner = Planner(rows, values, squad, sell_values, bank, free_ts,
                      caps, chip_instances(next_gw, used, length),
                      horizon=h, urgent=urgent_ids(ctx, squad, rows, caps, next_gw))
    best = planner.run()
    idle = baseline(planner)
    return describe(planner, best, idle, gws, ctx, proj, captain_first)


# A planned move's note says waiting avoided something only when the
# incoming player would genuinely have scored less than the outgoing one in
# the weeks skipped - otherwise the week is simply when a transfer is free.
WAIT_NOTE_MIN = 1.0


def describe(planner, best, idle, gws, ctx=None, proj=None, captain_first=None):
    """The finished plan as plain data for the page.

    `captain_first` is the captain the page already recommends for the
    first week. The plan's own pick uses the transfer scorer, which can
    differ from the captaincy card's history-backed one; one page naming
    two captains for the same week would be a contradiction, so the first
    week defers to the card whenever that player starts in the plan."""
    def name(p):
        return ctx.players[p]["web_name"] if ctx else str(p)

    def fixture(p, gw):
        if not ctx or not proj:
            return None
        row = proj.get((planner.rows[p]["club"], gw))
        if not row:
            return None
        return {"opp": row.get("opp"), "home": (row.get("ven") or "H").upper() == "H"}

    chip_at = {w["i"]: w["chip"] for w in best["weeks"]}
    ids = planner.squad0
    bought_at = {}
    weeks = []
    for wk in best["weeks"]:
        i, before = wk["i"], ids
        for o, c in wk["moves"]:
            ids = (ids - {o}) | {c}
            bought_at[c] = i
        detail = planner.week(ids, i)
        group_gain = sum(
            _display_points(planner, ids, j, chip_at.get(j))
            - _display_points(planner, before, j, chip_at.get(j))
            for j in range(i, planner.h)) - HIT * wk["hits"]
        moves = []
        for o, c in wk["moves"]:
            early = sum(planner.values[c][j] - planner.values[o][j] for j in range(i))
            moves.append({
                "out": o, "in": c, "out_name": name(o), "in_name": name(c),
                "pos": planner.rows[c]["pos"],
                "sell": planner.sell0[o], "price": planner.rows[c]["price"],
                "in_club": planner.rows[c]["club"], "out_club": planner.rows[o]["club"],
                # Why this week's hit was allowed, when it was.
                "urgent": (None if not wk["hits"] else "out" if o in planner.urgent
                           else "in" if c in planner.urgent else None),
                "out_cheap": is_cheap(planner.rows[o], planner.caps),
                "in_cheap": is_cheap(planner.rows[c], planner.caps),
                # His own points against the man he replaces, from this
                # week to the end of the plan - not the XI effect, which is
                # the week's `gain`.
                "own_gain": sum(planner.values[c][j] - planner.values[o][j]
                                for j in range(i, planner.h)),
                "waited": ({"loss": -early, "from_gw": gws[0], "to_gw": gws[i - 1],
                            "fixtures": [fixture(c, gws[j]) for j in range(i)]}
                           if i and early <= -WAIT_NOTE_MIN else None),
            })
        captain, vice = detail["captain"], detail["vice"]
        cap_val = detail["cap_val"]
        if i == 0 and captain_first in detail["xi"] and captain_first != captain:
            vice = captain
            captain = captain_first
            cap_val = planner.values[captain][i]
        chip = wk["chip"]
        points = (detail["xi_val"] + cap_val * (2 if chip == "3xc" else 1)
                  + (detail["bench_full"] if chip == "bboost" else 0.0))
        weeks.append({
            "gw": gws[i], "moves": moves, "hits": wk["hits"],
            "ft_before": wk["ft_before"],
            "ft_after": min(FT_CAP, max(0, wk["ft_before"] - len(moves)) + 1),
            "bank": wk["bank"], "chip": chip,
            "xi": detail["xi"], "bench": detail["bench"],
            "captain": captain, "vice": vice,
            "formation": detail["formation"],
            "points": points, "bench_points": detail["bench_full"],
            "gain": group_gain if moves else None,
            "player_points": {p: planner.values[p][i] for p in ids},
            "fixtures": {p: fixture(p, gws[i]) for p in ids},
            "new": {p for p, at in bought_at.items() if at == i},
            "bought": set(bought_at),
        })

    # Chips the plan holds past its last week: where they are projected to
    # be worth most, so "not in the plan" never reads as "never".
    held = []
    for n, c in enumerate(planner.chips):
        if n in best["played"] or c["last"] < planner.h:
            continue
        options = [(planner.chip_gain(ids, j, c["key"]), j)
                   for j in range(max(c["first"], planner.h), c["last"] + 1)]
        if options:
            gain, j = max(options)
            held.append({"key": c["key"], "gw": gws[j], "gain": gain})
    total, base = _total(planner, best), _total(planner, idle)
    return {
        "start_gw": gws[0], "end_gw": gws[planner.h - 1],
        "weeks": weeks, "total": total, "baseline": base, "gain": total - base,
        "enablers": [{"id": p, "name": name(p), "pos": planner.rows[p]["pos"],
                      "price": planner.rows[p]["price"]}
                     for p in planner.enablers],
        "caps": dict(planner.caps),
        "chips_modelled": bool(planner.chips),
        "held_chips": held,
        "baseline_chips": [(gws[w["i"]], w["chip"]) for w in idle["weeks"] if w["chip"]],
        "show_weeks": SHOW_WEEKS,
        "margin": TRANSFER_MARGIN, "ft_value": FT_VALUE, "chip_margin": CHIP_MARGIN,
    }


def timing_note(in_el, out_el, plan, ctx, proj, market, baselines, priors,
                next_gw, weeks=transfers.TRANSFER_HORIZON_WEEKS, live=None):
    """One line on when a listed move is best made: the week the plan makes
    it, or the week it starts paying when the incoming player's next few
    fixtures are clearly worse than the outgoing one's. "" when neither."""
    moves = [(w["gw"], m) for w in (plan or {}).get("weeks", []) for m in w["moves"]]
    for gw, m in moves:
        if (m["out"], m["in"]) == (out_el["id"], in_el["id"]):
            return f"In the transfer plan for GW{gw}."
    # The plan spends the same player another way: say so, rather than
    # leave two answers to one question side by side.
    for gw, m in moves:
        if m["out"] == out_el["id"]:
            return (f"The transfer plan sells {out_el['web_name']} differently: "
                    f"GW{gw}, for {m['in_name']}.")
        if m["in"] == in_el["id"]:
            return (f"The transfer plan signs {in_el['web_name']} for "
                    f"{m['out_name']} in GW{gw} instead.")
    gws = [g for g in range(next_gw, next_gw + weeks) if g <= 38]
    a = player_weeks(in_el, ctx, proj, market, baselines, priors, gws, live)
    b = player_weeks(out_el, ctx, proj, market, baselines, priors, gws, live)
    deltas = [x - y for x, y in zip(a, b)]
    t = max(range(min(3, len(deltas))), key=lambda k: (sum(deltas[k:]), -k))
    loss = -sum(deltas[:t])
    if t == 0 or loss < WAIT_NOTE_MIN:
        return ""
    fixtures = []
    for g in gws[:t]:
        row = proj.get((ctx.team_name(in_el["team"]), g))
        fixtures.append(f"{row['opp']} ({(row.get('ven') or 'H').upper()})" if row else "blank")
    return (f"Better from GW{gws[t]}: {in_el['web_name']} projects {loss:.1f} fewer than "
            f"{out_el['web_name']} before then ({', '.join(fixtures)}).")
