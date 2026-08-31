#!/usr/bin/env python3
"""
Turning FPL's raw JSON into the things worth acting on.

The guiding idea: points already happened, underlying numbers say what is
likely to happen next. Almost everything here is some form of "what is this
player actually generating, per 90 minutes, and does his points total agree?"
"""

import math

from dataclasses import dataclass, field

import fplapi

# FPL awards 2 points for hitting a defensive-contribution threshold in a
# match. Defenders need 10 (clearances, blocks, interceptions, tackles);
# midfielders and forwards need 12 (the same, plus ball recoveries).
#
# Verified against the API rather than assumed: for a DEF, the
# `defensive_contribution` field equals CBI + tackles exactly (Van Hecke
# 25/26: 264 + 53 = 317), while for MID/FWD it equals CBI + tackles +
# recoveries (Haaland: 48 + 15 + 41 = 104). So the field is already composed
# correctly per position and only the threshold differs.
DEFCON_THRESHOLD = {"DEF": 10, "MID": 12, "FWD": 12}

POS_SHORT = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def per90(value, minutes):
    return (value * 90.0 / minutes) if minutes else 0.0


def f(x):
    """FPL sends the expected-goal fields as strings."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class Ctx:
    """Everything the reports read from, fetched once."""

    boot: dict
    players: dict = field(default_factory=dict)   # id -> element
    teams: dict = field(default_factory=dict)     # id -> team
    events: list = field(default_factory=list)
    fixtures: list = field(default_factory=list)
    # Photo ids Fantasy Football Scout expects to start. Empty means unknown -
    # never "nobody starts" - so every consumer must check it is non-empty.
    predicted: set = field(default_factory=set)

    @classmethod
    def load(cls, ttl=fplapi.DEFAULT_TTL):
        boot = fplapi.bootstrap(ttl=ttl)
        c = cls(boot=boot)
        c.players = {e["id"]: e for e in boot["elements"]}
        c.teams = {t["id"]: t for t in boot["teams"]}
        c.events = boot["events"]
        c.fixtures = fplapi.fixtures(ttl=ttl)
        c.predicted = fplapi.ffs_predicted_photo_ids(ttl=ttl)
        return c

    def lineups_known(self):
        return bool(self.predicted)

    def is_predicted(self, element):
        """True / False / None, where None means we have no line-up data."""
        if not self.predicted:
            return None
        return element["photo"].split(".")[0] in self.predicted

    # -- gameweek helpers --

    def current_event(self):
        for e in self.events:
            if e.get("is_current"):
                return e["id"]
        for e in self.events:
            if e.get("is_next"):
                return e["id"]
        finished = [e["id"] for e in self.events if e.get("finished")]
        return finished[-1] if finished else 1

    def last_event_with_picks(self):
        """Picks only become public once a deadline passes, so the newest
        readable gameweek is the current one if its deadline has gone, else
        the one before."""
        cur = self.current_event()
        ev = {e["id"]: e for e in self.events}
        if ev.get(cur, {}).get("is_current") or ev.get(cur, {}).get("finished"):
            return cur
        return max(1, cur - 1)

    def pos(self, element):
        return POS_SHORT.get(element["element_type"], "?")

    def team_name(self, tid):
        return self.teams[tid]["short_name"]

    # -- fixtures --

    @staticmethod
    def _is_upcoming(fx):
        """A fixture that has not been played yet.

        `finished` alone is not enough: while a gameweek is live FPL leaves it
        False on matches that have already been played, so a naive filter
        reports this afternoon's completed game as your next fixture. Checking
        `started` and `finished_provisional` too keeps played matches out."""
        return not (
            fx.get("finished")
            or fx.get("finished_provisional")
            or fx.get("started")
        )

    @classmethod
    def _is_played(cls, fx):
        """A fixture whose minutes are already in the players' season totals.

        The complement of `_is_upcoming`, and the correct thing to divide a
        club's season xG by. Anything counting matches must use this rather
        than `finished` on its own, or it divides two matches of xG by one
        match and reports a club as twice the attack it is."""
        return not cls._is_upcoming(fx)

    def next_fixtures(self, team_id, count=5, from_event=None):
        """Upcoming (opponent, is_home, difficulty, event) for a team."""
        start = from_event or self.current_event()
        out = []
        for fx in sorted(
            (x for x in self.fixtures if x.get("event") and self._is_upcoming(x)),
            key=lambda x: (x["event"], x.get("kickoff_time") or ""),
        ):
            if fx["event"] < start:
                continue
            if fx["team_h"] == team_id:
                out.append((fx["team_a"], True, fx["team_h_difficulty"], fx["event"]))
            elif fx["team_a"] == team_id:
                out.append((fx["team_h"], False, fx["team_a_difficulty"], fx["event"]))
            if len(out) >= count:
                break
        return out

    def fixture_score(self, team_id, count=5):
        """Mean FDR over the next `count` fixtures. Lower is kinder.
        Returns None when the fixture list has run out."""
        fx = self.next_fixtures(team_id, count)
        return (sum(x[2] for x in fx) / len(fx)) if fx else None

    def fixture_str(self, team_id, count=3):
        fx = self.next_fixtures(team_id, count)
        parts = []
        for opp, home, diff, _ev in fx:
            name = self.team_name(opp)
            parts.append(f"{name.upper() if home else name.lower()}({diff})")
        return " ".join(parts) if parts else "-"


# --- per-player -----------------------------------------------------------


@dataclass
class PlayerReport:
    element: dict
    pos: str
    team: str
    history: list          # this season, one row per match
    past: list             # previous seasons, totals only

    # season so far
    minutes: int = 0
    starts: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    bonus: int = 0
    xg: float = 0.0
    xa: float = 0.0
    xgi: float = 0.0
    xgc: float = 0.0
    defcon: int = 0
    defcon_hits: int = 0

    def compute(self):
        h = self.history
        self.minutes = sum(x["minutes"] for x in h)
        self.starts = sum(x["starts"] for x in h)
        self.goals = sum(x["goals_scored"] for x in h)
        self.assists = sum(x["assists"] for x in h)
        self.points = sum(x["total_points"] for x in h)
        self.bonus = sum(x["bonus"] for x in h)
        self.xg = sum(f(x["expected_goals"]) for x in h)
        self.xa = sum(f(x["expected_assists"]) for x in h)
        self.xgi = sum(f(x["expected_goal_involvements"]) for x in h)
        self.xgc = sum(f(x["expected_goals_conceded"]) for x in h)
        self.defcon = sum(x.get("defensive_contribution", 0) for x in h)
        thresh = DEFCON_THRESHOLD.get(self.pos)
        self.defcon_hits = (
            sum(1 for x in h if x.get("defensive_contribution", 0) >= thresh)
            if thresh
            else 0
        )
        return self

    # -- derived --

    @property
    def name(self):
        return self.element["web_name"]

    @property
    def price(self):
        return self.element["now_cost"] / 10.0

    @property
    def owned(self):
        return f(self.element["selected_by_percent"])

    @property
    def xgi90(self):
        return per90(self.xgi, self.minutes)

    @property
    def defcon90(self):
        return per90(self.defcon, self.minutes)

    @property
    def finishing(self):
        """Goals minus expected goals. Positive = converting above the
        model's expectation, which historically does not persist."""
        return self.goals - self.xg

    @property
    def creating(self):
        return self.assists - self.xa

    @property
    def appearances(self):
        return sum(1 for x in self.history if x["minutes"] > 0)

    @property
    def start_rate(self):
        return (self.starts / self.appearances) if self.appearances else 0.0

    @property
    def availability(self):
        """(flag, note) - injury / suspension / doubt."""
        el = self.element
        chance = el.get("chance_of_playing_next_round")
        news = (el.get("news") or "").strip()
        if el.get("status") == "a" and not news:
            return None, ""
        label = {
            "i": "INJURED",
            "s": "SUSPENDED",
            "d": "DOUBT",
            "u": "UNAVAILABLE",
            "n": "NOT IN SQUAD",
        }.get(el.get("status"), "NOTE")
        if chance is not None:
            label = f"{label} {chance}%"
        return label, news

    def set_pieces(self):
        """Set-piece duties are one of the strongest cheap edges in FPL and
        sit right there in bootstrap, unused by most tools."""
        el = self.element
        out = []
        for key, tag in (
            ("penalties_order", "pens"),
            ("direct_freekicks_order", "FK"),
            ("corners_and_indirect_freekicks_order", "corners"),
        ):
            order = el.get(key)
            if order:
                out.append(f"{tag} #{order}")
        return out

    def recent_form(self, window=5):
        """A short, glanceable read on recent output for the pick-team card:
        an attacking hot streak, a dry spell, the underlying rate behind a
        mixed record, or - this early in a season - just last week's line.
        A game with no minutes does not count as a "week"; a run is of games
        actually played, not calendar gameweeks."""
        games = sorted((x for x in self.history if x["minutes"] > 0),
                       key=lambda x: x["round"])
        recent = games[-window:]
        n = len(recent)
        if n == 0:
            return None
        if n == 1:
            h = recent[0]
            pts = h["total_points"]
            if pts >= 6:
                return {"text": f"{pts} pts last week", "hot": pts >= 10}
            xgi = f(h["expected_goal_involvements"])
            if xgi >= 0.3:
                return {"text": f"{xgi:.2f} xGI last week", "hot": False}
            return {"text": f"{pts} pt{'s' if pts != 1 else ''} last week",
                   "hot": False}
        returns = sum(1 for h in recent if h["goals_scored"] + h["assists"] > 0)
        if returns >= 2 and returns / n >= 0.6:
            return {"text": f"{returns} returns in last {n}", "hot": True}
        if returns == 0:
            return {"text": f"0 returns in last {n}", "hot": False}
        if returns == 1 and n >= 3:
            return {"text": f"1 return in last {n}", "hot": False}
        xgi_sum = sum(f(h["expected_goal_involvements"]) for h in recent)
        mins_sum = sum(h["minutes"] for h in recent)
        rate = per90(xgi_sum, mins_sum)
        return {"text": f"{rate:.2f} xGI/90 last {n}", "hot": False}

    def last_n_points(self, n=4):
        """Total points across the last n matches actually played. None
        before any minutes this season, so callers can fall back rather
        than show a misleading zero."""
        games = sorted((x for x in self.history if x["minutes"] > 0),
                       key=lambda x: x["round"])
        recent = games[-n:]
        return sum(x["total_points"] for x in recent) if recent else None

    def home_away_points(self, min_games=2):
        """(home_ppg, away_ppg) from matches played this season - either
        side is None below min_games, since a single match is noise, not
        a venue split (same reasoning as THIN_SAMPLE_MINUTES elsewhere)."""
        home = [x["total_points"] for x in self.history
                if x["minutes"] > 0 and x["was_home"]]
        away = [x["total_points"] for x in self.history
                if x["minutes"] > 0 and not x["was_home"]]
        return (
            sum(home) / len(home) if len(home) >= min_games else None,
            sum(away) / len(away) if len(away) >= min_games else None,
        )

    def last_season(self):
        """Previous-season totals, the only history the API keeps beyond the
        current campaign. Useful as a baseline while this season is short."""
        if not self.past:
            return None
        p = self.past[-1]
        return {
            "season": p["season_name"],
            "minutes": p["minutes"],
            "goals": p["goals_scored"],
            "assists": p["assists"],
            "xg": f(p.get("expected_goals")),
            "xa": f(p.get("expected_assists")),
            "xgi": f(p.get("expected_goal_involvements")),
            "defcon": p.get("defensive_contribution", 0),
            "bonus": p.get("bonus", 0),
            "points": p["total_points"],
            "starts": p.get("starts", 0),
        }

    def start_probability(self, ctx):
        """A continuous read on whether this player takes the pitch, rather
        than the three-bucket guess (start / bench / average) the rest of
        this module used to make from `ctx.is_predicted`.

        FFS's predicted lineup is the strongest signal once it exists, since
        it is someone's actual judgement call, not a rate. Before it exists
        for a gameweek, the season's own start rate stands in - a short
        injury already falls out of that rate rather than counting against
        it, because `appearances` only counts games with minutes. What it
        cannot cover is a player with barely any *current*-season history at
        all - a fresh signing, or a long injury spanning most of the season
        so far - so that case blends in last season's rate instead, the same
        way the xG/xA rates already do while this season is thin. FPL's own
        fitness flag (`chance_of_playing_next_round`) then scales the result
        down for a doubt regardless of which source set it."""
        el = self.element
        pred = ctx.is_predicted(el)
        if pred is True:
            base = 0.92
        elif pred is False:
            base = 0.10
        elif self.appearances >= THIN_APPEARANCES:
            base = self.start_rate
        else:
            ls = self.last_season()
            if ls and ls["starts"] and ls["minutes"] >= 900:
                # No per-match log survives from a past season, only season
                # totals - minutes/90 stands in for games involved in, which
                # is close enough for a fallback prior.
                prior = min(1.0, ls["starts"] / max(1.0, ls["minutes"] / 90.0))
            else:
                # No reliable anchor either way - neutral, not a guess dressed
                # up as one. A single appearance this season is not enough
                # evidence on its own to trust fully, whichever way it points.
                prior = 0.5
            base = (
                (self.appearances / THIN_APPEARANCES) * self.start_rate
                + (1 - self.appearances / THIN_APPEARANCES) * prior
                if self.appearances else prior
            )
        chance = el.get("chance_of_playing_next_round")
        fitness = (chance / 100.0) if chance is not None else 1.0
        return max(0.03, min(0.98, base * fitness))


def build_player(ctx, player_id, ttl=fplapi.DEFAULT_TTL):
    el = ctx.players[player_id]
    s = fplapi.element_summary(player_id, ttl=ttl)
    return PlayerReport(
        element=el,
        pos=ctx.pos(el),
        team=ctx.team_name(el["team"]),
        history=s["history"],
        past=s["history_past"],
    ).compute()


# --- squads ---------------------------------------------------------------


def squad_for(entry_id, event, ctx):
    """A manager's 15 with XI/bench/captain, from the public picks endpoint."""
    picks = fplapi.entry_picks(entry_id, event)
    for p in picks["picks"]:
        p["element_obj"] = ctx.players.get(p["element"])
    return picks


def squad_sell_value(entry_id, ctx, squad_reports, ttl=fplapi.DEFAULT_TTL):
    """Real FPL sell value per player: purchase price plus half of any
    rise since (rounded down), or the current price outright if it has
    fallen - never a flat guess, since this bounds every chip-suggester
    optimizer run below.

    Purchase price comes from the manager's public transfer history (the
    exact price paid, not an estimate), falling back to a player's own
    price at gameweek 1 for anyone held since the start and never
    transferred. Both are unauthenticated, public FPL endpoints.

    Returns (total, per_player); per_player is {element_id: sell_price},
    values in millions."""
    transfers_history = fplapi.get_json(
        f"{fplapi.BASE}/entry/{entry_id}/transfers/", ttl=ttl)
    bought_at = {}
    for t in transfers_history:
        pid = t["element_in"]
        prev = bought_at.get(pid)
        if prev is None or t["event"] > prev[0]:
            bought_at[pid] = (t["event"], t["element_in_cost"])

    per_player = {}
    for r in squad_reports:
        pid = r.element["id"]
        now = r.element["now_cost"]
        if pid in bought_at:
            buy = bought_at[pid][1]
        else:
            s = fplapi.element_summary(pid, ttl=ttl)
            first = next((h for h in s.get("history", []) if h["round"] == 1), None)
            buy = first["value"] if first else now
        sell = buy + (now - buy) // 2 if now > buy else now
        per_player[pid] = sell / 10.0
    return sum(per_player.values()), per_player


# --- mini-league ----------------------------------------------------------


def league_ownership(squads):
    """player_id -> {'owners', 'starters', 'captains'} across every squad.

    This is what makes a mini-league readable: raw ownership tells you what
    the whole league is riding on, and where you are actually different."""
    own = {}
    for name, picks in squads.items():
        for p in picks["picks"]:
            rec = own.setdefault(
                p["element"], {"owners": [], "captains": [], "starters": []}
            )
            rec["owners"].append(name)
            if p["position"] <= 11:
                rec["starters"].append(name)
            if p["is_captain"]:
                rec["captains"].append(name)
    return own


# --- findings --------------------------------------------------------------

# Below this many minutes, per-90 rates are noise and are labelled as such.
# Three full matches is the point where a rate stops being one good cameo.
THIN_SAMPLE_MINUTES = 270

# Below this many games actually played, a start rate is still mostly luck of
# the draw - PlayerReport.start_probability blends toward last season below it.
THIN_APPEARANCES = 4


def chip_window(next_gw, cap=8):
    """The gameweek range chip suggestions search: the rest of the current
    half - GW1-19, or GW20-38 once that resets - capped, since a
    projection further out than that is mostly noise. Returns
    (start, weeks); the caller's own search range is
    range(start, start + weeks)."""
    end = 19 if next_gw <= 19 else 38
    weeks = min(cap, max(0, end - next_gw + 1))
    return next_gw, weeks


FREE_TRANSFER_CAP = 5


def free_transfers(entry_id, next_gw, ttl=fplapi.DEFAULT_TTL):
    """How many free transfers are banked going into `next_gw`.

    FPL does not publish this without a login, so it is replayed from the
    per-gameweek transfer counts in the public history: one free transfer is
    granted each gameweek from GW2, unused ones roll over, and the bank is
    capped at five. Nothing accrues for GW1, where transfers are unlimited
    before the deadline anyway.

    Returns None rather than a guess when the history cannot be read, so
    callers can fall back to assuming a hit rather than quietly asserting a
    free transfer that may not exist.

    One thing it cannot see: transfers already made for `next_gw` itself.
    Those only reach the public history once that deadline passes, so
    immediately after making a move this still reports the pre-move figure."""
    try:
        history = fplapi.entry_history(entry_id, ttl=ttl)
    except fplapi.FplError:
        return None
    used = {ev["event"]: ev.get("event_transfers", 0)
            for ev in history.get("current", [])}
    banked = 1  # granted for GW2, the first week a transfer can be saved
    for gw in range(2, next_gw):
        if gw not in used:
            continue
        banked = min(FREE_TRANSFER_CAP, banked - used[gw] + 1)
        banked = max(0, banked)
    return min(FREE_TRANSFER_CAP, banked)


def transfer_cost(count, free, per_hit=4):
    """Points cost of making `count` transfers holding `free` free ones."""
    if free is None:
        free = 1
    return max(0, count - free) * per_hit


def _finding(key, title, tone, items, note=""):
    return {"key": key, "title": title, "tone": tone, "items": items, "note": note}


def build_findings(reports, ctx):
    """Structured findings, shared by the terminal report and the dashboard.

    Every item is an observation with its evidence attached, not a
    recommendation - nothing here knows your transfers, chips or risk
    appetite, and a confident 'SELL' from a five-line heuristic would be worth
    less than the number it is built on.

    Returns a list of {key, title, tone, note, items}."""
    out = []

    thin = [r for r in reports if r.minutes < THIN_SAMPLE_MINUTES]
    if thin:
        out.append(
            _finding(
                "sample",
                "Sample size",
                "info",
                [
                    f"{len(thin)} of {len(reports)} players are under "
                    f"{THIN_SAMPLE_MINUTES} minutes this season. Per-90 rates are "
                    f"volatile; last-season baselines are shown below."
                ],
            )
        )

    flags = []
    for r in reports:
        label, news = r.availability
        if label:
            flags.append(f"{r.name} - {label}. {news}".strip())
    if flags:
        out.append(_finding("availability", "Availability", "bad", flags))

    hot = sorted((r for r in reports if r.finishing > 0.8), key=lambda x: -x.finishing)
    if hot:
        out.append(
            _finding(
                "hot",
                "Scoring above expected",
                "warn",
                [f"{r.name} - {r.goals} goals from {r.xg:.2f} xG (+{r.finishing:.2f})"
                 for r in hot],
                note="Historically does not persist.",
            )
        )

    cold = sorted((r for r in reports if r.finishing < -0.8), key=lambda x: x.finishing)
    if cold:
        out.append(
            _finding(
                "cold",
                "Scoring below expected",
                "good",
                [f"{r.name} - {r.goals} goals from {r.xg:.2f} xG ({r.finishing:.2f})"
                 for r in cold],
                note="The chances are being created. Hold or buy.",
            )
        )

    dc = []
    for r in reports:
        t = DEFCON_THRESHOLD.get(r.pos)
        if not t or not r.minutes:
            continue
        rate = r.defcon90
        if rate >= t:
            dc.append(
                f"{r.name} - {rate:.1f} per 90 against a threshold of {t}, hit in "
                f"{r.defcon_hits} of {r.appearances} matches"
            )
        elif rate >= t * 0.8:
            dc.append(
                f"{r.name} - {rate:.1f} per 90 against a threshold of {t}, borderline "
                f"({r.defcon_hits} of {r.appearances})"
            )
    if dc:
        out.append(
            _finding("defcon", "Defensive contribution", "neutral", dc,
                     note="2 points per match at the threshold.")
        )

    sp = [f"{r.name} - {', '.join(r.set_pieces())}" for r in reports if r.set_pieces()]
    if sp:
        out.append(_finding("setpieces", "Set-piece duties", "neutral", sp))

    rot = [
        f"{r.name} - started {r.starts} of {r.appearances} appearances, "
        f"{r.minutes / r.appearances:.0f} minutes per appearance"
        for r in reports
        if r.appearances >= 2 and r.start_rate < 0.75
    ]
    if rot:
        out.append(_finding("rotation", "Rotation risk", "warn", rot))

    kind, hard = {}, {}
    for r in reports:
        near = ctx.fixture_score(r.element["team"], 3)
        if near is None:
            continue
        if near <= 2.4:
            kind[r.team] = f"{r.team} - kind run, average difficulty {near:.1f} over the next 3"
        elif near >= 3.6:
            hard[r.team] = f"{r.team} - hard run, average difficulty {near:.1f} over the next 3"
    if kind or hard:
        out.append(
            _finding("fixtures", "Fixture swings", "neutral",
                     sorted(kind.values()) + sorted(hard.values()))
        )

    if ctx.lineups_known():
        benched, starting = [], 0
        for r in reports:
            if ctx.is_predicted(r.element):
                starting += 1
            else:
                benched.append(f"{r.name} ({r.team}) - not in the predicted eleven")
        if benched:
            out.append(
                _finding(
                    "lineups", "Predicted line-ups", "warn", benched,
                    note=f"{starting} of {len(reports)} of your squad are predicted to "
                         f"start. Fantasy Football Scout re-tunes these after each "
                         f"press conference, so they sharpen closer to the deadline.",
                )
            )

    # Big chances come from the Premier League's own Opta feed, not FPL.
    # A missed big chance is the cleanest "he should have scored" evidence
    # there is - stronger than xG alone, because it counts clear openings
    # rather than summing every half-shot.
    missed, created = [], []
    for r in reports:
        ps = r.element.get("_pulse") or {}
        bcm, bcc = ps.get("big_chance_missed"), ps.get("big_chance_created")
        sot, shots = ps.get("ontarget_scoring_att"), ps.get("total_scoring_att")
        if bcm:
            extra = f", {shots:g} shots ({sot:g} on target)" if shots else ""
            missed.append(f"{r.name} - {bcm:g} big {'chance' if bcm == 1 else 'chances'} missed{extra}")
        if bcc:
            created.append(f"{r.name} - {bcc:g} big {'chance' if bcc == 1 else 'chances'} created")
    if missed:
        out.append(_finding("bcm", "Big chances missed", "good", missed,
                            note="Clear openings not taken. The chances are arriving."))
    if created:
        out.append(_finding("bcc", "Big chances created", "good", created,
                            note="Passes that set up a clear opening."))

    moves = []
    for r in reports:
        change = r.element.get("cost_change_start", 0)
        if abs(change) >= 1:
            moves.append(
                f"{r.name} - {'risen' if change > 0 else 'fallen'} "
                f"{abs(change) / 10:.1f}m since season start, now {r.price:.1f}m"
            )
    if moves:
        out.append(_finding("price", "Price movement", "neutral", moves))

    base = []
    for r in reports:
        if r.minutes >= THIN_SAMPLE_MINUTES:
            continue
        ls = r.last_season()
        if not ls or ls["minutes"] < 900:
            continue
        returns = ls["goals"] + ls["assists"]
        delta = returns - ls["xgi"]
        # Last season's gap between actual returns and expected ones is the
        # cleanest read on whether a player is a genuine over-performer or was
        # simply lucky. One season is short, but it is what the API keeps.
        verdict = ""
        if delta >= 3:
            verdict = (f" He beat his expected numbers by {delta:.1f}, so some of "
                       f"that was finishing rather than chances.")
        elif delta <= -3:
            verdict = (f" He fell {abs(delta):.1f} short of his expected numbers, "
                       f"so the chances were there but the finishing was not.")
        base.append(
            f"{r.name} - {ls['points']} points last season. "
            f"{returns} goals and assists from {ls['xgi']:.1f} expected, "
            f"across {ls['minutes']:,} minutes.{verdict}"
        )
    if base:
        out.append(
            _finding(
                "baseline", "How they did last season", "info", base,
                note="One gameweek says almost nothing, so here is a full season "
                     "of each player for comparison. Expected numbers are goals "
                     "and assists a player's chances were worth.",
            )
        )

    return out


# --- expected points ------------------------------------------------------

# FPL's scoring, by position.
GOAL_POINTS = {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}
CS_POINTS = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
ASSIST_POINTS = 3
DEFCON_POINTS = 2


# --- bonus ---------------------------------------------------------------

# What each event is worth in FPL's Bonus Points System.
GOAL_BPS = {"GKP": 12, "DEF": 12, "MID": 18, "FWD": 24}
ASSIST_BPS = 9
CS_BPS = {"GKP": 12, "DEF": 12}

# Bonus is not earned directly - the three highest BPS scores in a match take
# 3, 2 and 1. So the mapping from a player's BPS to the bonus he actually
# collects is a saturating curve, and this one is fitted rather than guessed:
# least squares over eleven players across all four positions, using last
# season's BPS per match against bonus per match. SSE 0.12.
#
#     bonus = 2.5 / (1 + exp(-(bps - 28.5) / 6.5))
BONUS_L, BONUS_MID, BONUS_K = 2.5, 28.5, 6.5


def bonus_from_bps(bps):
    try:
        return BONUS_L / (1.0 + math.exp(-(bps - BONUS_MID) / BONUS_K))
    except OverflowError:
        return 0.0 if bps < BONUS_MID else BONUS_L


def other_bps_per90(el, ctx, minutes):
    """BPS a player earns from everything that is not a goal, assist or clean
    sheet - tackles, recoveries, key passes, crosses, saves, big chances
    created, minus cards and goals conceded.

    Backed out of his actual BPS rather than modelled: subtract what his
    recorded events were worth and whatever is left is his baseline
    involvement. That is the part which makes a busy midfielder collect bonus
    on a quiet day."""
    if not minutes:
        return 0.0
    pos = ctx.pos(el)
    events = (
        el.get("goals_scored", 0) * GOAL_BPS.get(pos, 12)
        + el.get("assists", 0) * ASSIST_BPS
        + el.get("clean_sheets", 0) * CS_BPS.get(pos, 0)
    )
    return max(0.0, per90(max(0.0, el.get("bps", 0) - events), minutes))


def expected_bonus(pos, share, exp_goals, exp_assists, cs_prob, other_bps90,
                   minutes):
    """Expected bonus points, built from the same parts as the rest of the
    projection.

    Averaging BPS first and mapping once would be wrong: the curve bends, so a
    striker who either scores or does nothing is not the same as one who
    reliably does something middling. Instead the plausible match outcomes are
    enumerated - nought, one or two goals, an assist or not, a clean sheet or
    not - each scored for BPS and mapped to bonus, then weighted by how likely
    it is. That is why a forward with a real chance of scoring now carries
    expected bonus even when he has none on record."""
    if share <= 0:
        return 0.0
    appearance_bps = 6.0 if minutes >= 60 else 3.0
    base = appearance_bps + other_bps90 * share
    goal_bps = GOAL_BPS.get(pos, 12)
    cs_bps = CS_BPS.get(pos, 0) if minutes >= 60 else 0

    # Poisson for goals, Bernoulli for the rest.
    lam = max(0.0, exp_goals)
    p_goals = []
    for k in range(3):
        p = math.exp(-lam) * lam ** k / math.factorial(k)
        p_goals.append(p)
    p_goals.append(max(0.0, 1.0 - sum(p_goals)))  # 3+, treated as 3
    p_assist = min(0.95, max(0.0, 1.0 - math.exp(-max(0.0, exp_assists))))
    p_cs = min(1.0, max(0.0, cs_prob))

    total = 0.0
    for goals, pg in enumerate(p_goals):
        if pg <= 0.0005:
            continue
        for assisted, pa in ((1, p_assist), (0, 1.0 - p_assist)):
            if pa <= 0.0005:
                continue
            for clean, pc in ((1, p_cs), (0, 1.0 - p_cs)):
                if cs_bps == 0 and clean == 1:
                    continue
                weight = pg * pa * (pc if cs_bps else (1.0 if clean == 0 else 0.0))
                if weight <= 0.0005:
                    continue
                bps = base + goals * goal_bps + assisted * ASSIST_BPS + clean * cs_bps
                total += weight * bonus_from_bps(bps)
    return total


def team_attack_baselines(ctx, league_avg=1.45):
    """Each club's own expected goals per match so far, blended toward the
    league average while the season is short.

    This is the denominator the market number gets compared against. Scaling a
    player's rate by market_xg / league_average would double-count his club's
    quality - his own rate already reflects playing for a good side. Dividing
    by his club's own norm isolates the part that is about this fixture."""
    totals, played = {}, {}
    for el in ctx.players.values():
        totals[el["team"]] = totals.get(el["team"], 0.0) + f(el.get("expected_goals"))
    for fx in ctx.fixtures:
        # `finished` alone undercounts: FPL holds it False until bonus is
        # confirmed, so a round played yesterday does not register and every
        # club's season xG gets divided by too few matches. That inflated
        # every baseline, and since the baseline is the denominator of the
        # fixture multiplier, it quietly flattened the multiplier for the
        # whole league.
        if ctx._is_played(fx):
            for side in ("team_h", "team_a"):
                played[fx[side]] = played.get(fx[side], 0) + 1
    out = {}
    for tid in ctx.teams:
        n = played.get(tid, 0)
        if not n:
            out[tid] = league_avg
            continue
        own = totals.get(tid, 0.0) / n
        weight = min(1.0, n / 6.0)   # trust the club's own number only slowly
        out[tid] = max(0.4, weight * own + (1 - weight) * league_avg)
    return out


def expected_points(r, ctx, proj, gw, market=None, baselines=None,
                    league_avg_xg=1.45):
    """A player's expected points for one gameweek.

    FPL publish `ep_next`, but it is not usable: 26 distinct values across 515
    players, a maximum of 4.0 for anyone including Haaland, and identical to
    `ep_this` for 578 of 612. So this is built here, from parts that are all
    free and all explainable.

    Where the betting market has priced the fixture it is preferred over the
    model, for both halves of the calculation:

      clean sheet   the market's implied probability, derived from the
                    opponent's expected goals; Scout's model only as fallback
      attack        the market's expected goals for this club in this match,
                    against the club's own seasonal norm, giving a multiplier
                    applied to the player's own xG and xA rates separately
      bonus         his own bonus per 90, which is the part FPL's own
                    projection ignores entirely and which is worth a point a
                    game to a premium

    A market line has money behind it and a model does not, which is the whole
    argument for preferring it. Everything still carries a source label so a
    number that came from a model is never mistaken for one that was priced.
    """
    el = r.element
    club = ctx.team_name(el["team"])
    fixture = proj.get((club, gw))
    mk = (market or {}).get(club)
    if not fixture and not mk:
        return None

    # A continuous read on whether he plays, not three fixed guesses - a
    # start earns close to what he plays when he does start; missing the XI
    # still carries a chance of a late cameo rather than a hard zero.
    start_prob = r.start_probability(ctx)
    avg_start_minutes = min(90.0, r.minutes / r.starts) if r.starts else 75.0
    minutes = start_prob * avg_start_minutes + (1 - start_prob) * 8.0
    minutes = max(0.0, min(90.0, minutes))
    share = minutes / 90.0

    # --- fixture quality, market first ---
    baseline = (baselines or {}).get(el["team"], league_avg_xg)
    # `market` only ever prices the imminent round, so it is only trustworthy
    # when the opponent it names matches the fixture actually being asked
    # about here - otherwise a call for a later gameweek would silently reuse
    # next week's market line for every week after it. Same guard ticker.py
    # already applies for the same reason.
    mk_matches = bool(mk and fixture and mk.get("opp") == fixture.get("opp"))
    if mk_matches:
        team_xg, xg_source = mk["xg"], "market"
    elif fixture:
        team_xg, xg_source = float(fixture.get("g") or league_avg_xg), "model"
    elif mk:
        team_xg, xg_source = mk["xg"], "market"
    else:
        team_xg, xg_source = league_avg_xg, "average"
    # Bounded: one strange line should not triple a projection.
    fixture_mult = max(0.5, min(2.0, team_xg / baseline)) if baseline else 1.0

    # --- clean sheet, market first ---
    if mk_matches:
        cs_prob, cs_source = mk["cs"] / 100.0, "market"
    elif fixture:
        cs_prob, cs_source = float(fixture.get("cs") or 0) / 100.0, "model"
    elif mk:
        cs_prob, cs_source = mk["cs"] / 100.0, "market"
    else:
        cs_prob, cs_source = 0.0, "none"

    # --- the player's own rates, blended with last season while thin ---
    xg90, xa90 = per90(r.xg, r.minutes), per90(r.xa, r.minutes)
    other_bps90 = other_bps_per90(el, ctx, r.minutes)
    ls = r.last_season()
    if r.minutes < THIN_SAMPLE_MINUTES and ls and ls["minutes"] >= 900:
        blend = r.minutes / THIN_SAMPLE_MINUTES
        xg90 = blend * xg90 + (1 - blend) * per90(ls["xg"], ls["minutes"])
        xa90 = blend * xa90 + (1 - blend) * per90(ls["xa"], ls["minutes"])

    exp_goals = xg90 * share * fixture_mult
    exp_assists = xa90 * share * fixture_mult
    goals_pts = exp_goals * GOAL_POINTS.get(r.pos, 4)
    assists_pts = exp_assists * ASSIST_POINTS
    attack = goals_pts + assists_pts

    # Clean-sheet points need 60 minutes, so a fringe player earns none.
    defence = cs_prob * CS_POINTS.get(r.pos, 0) * (1.0 if share > 0.65 else 0.0)
    appearance = 2.0 * share if minutes >= 60 else 1.0 * share
    hit_rate = (r.defcon_hits / r.appearances) if r.appearances else 0.0
    defcon = hit_rate * DEFCON_POINTS * share
    bonus = expected_bonus(r.pos, share, exp_goals, exp_assists, cs_prob,
                           other_bps90, minutes)

    total = attack + defence + appearance + defcon + bonus
    return {
        "total": total,
        "attack": attack,
        "goals": goals_pts,
        "assists": assists_pts,
        "defence": defence,
        "appearance": appearance,
        "defcon": defcon,
        "bonus": bonus,
        "exp_goals": exp_goals,
        "exp_assists": exp_assists,
        "minutes": minutes,
        "cs": cs_prob * 100,
        "cs_source": cs_source,
        "team_xg": team_xg,
        "xg_source": xg_source,
        "baseline": baseline,
        "fixture_mult": fixture_mult,
        # The fixture itself - who and where - is always this gameweek's own
        # truth, not something only the market can price, so it comes from
        # `fixture` whenever one exists; `mk` only fills in on the rare
        # fixture the model has no row for at all.
        "opponent": fixture.get("opp") if fixture else mk["opp"],
        "home": (fixture.get("ven") or "H").upper() == "H" if fixture else mk["home"],
    }


def windowed_ep(r, ctx, proj, market, baselines, start_gw, weeks=8):
    """A player's expected points summed across a run of gameweeks, not
    just one - the building block every chip recommendation is scored
    from. Returns (total, per_gw); per_gw is [(gw, ep_dict), ...] for
    whichever gameweeks actually had a projection, since a blank gameweek
    is skipped rather than scored as zero, matching expected_points
    itself."""
    per_gw = []
    for gw in range(start_gw, start_gw + weeks):
        ep = expected_points(r, ctx, proj, gw, market=market, baselines=baselines)
        if ep:
            per_gw.append((gw, ep))
    total = sum(ep["total"] for _gw, ep in per_gw)
    return total, per_gw


# --- market ---------------------------------------------------------------

def _pct(el):
    try:
        return float(el.get("price_change_percent"))
    except (TypeError, ValueError):
        return 0.0


def price_watch(ctx, squad_ids=(), limit=10, min_owned=0.3):
    """Who is about to change price.

    FPL exposes the progress of each player towards a price change:
    `price_change_percent` is how far along they are, signed - positive rises,
    negative falls - and the change fires at 100. `price_change_projections`
    carries the same figure forecast 0, 1 and 2 days ahead. A player already
    past 100 is due to move at the next daily recalculation.

    This is the one genuinely time-sensitive thing in the API: it is only
    useful before the change, which is exactly when a static table is not.

    `min_owned` drops the long tail of near-unowned players whose percentages
    swing wildly on tiny transfer counts."""
    squad = set(squad_ids)
    rows = []
    for el in ctx.players.values():
        pct = _pct(el)
        if pct == 0:
            continue
        if f(el.get("selected_by_percent")) < min_owned and el["id"] not in squad:
            continue
        proj = el.get("price_change_projections") or []
        by_offset = {p["offset"]: p for p in proj}
        d2 = by_offset.get(2) or by_offset.get(1) or by_offset.get(0)
        rows.append({
            "element": el,
            "name": el["web_name"],
            "team": ctx.team_name(el["team"]),
            "pos": ctx.pos(el),
            "price": el["now_cost"] / 10.0,
            "pct": pct,
            "projected": float(d2["projected_percent"]) if d2 else pct,
            "likelihood": d2["likelihood"] if d2 else 0,
            "net_transfers": el.get("transfers_in_event", 0) - el.get("transfers_out_event", 0),
            "owned_by_you": el["id"] in squad,
            "owned": f(el.get("selected_by_percent")),
            "imminent": abs(pct) >= 100,
        })
    risers = sorted((r for r in rows if r["pct"] > 0), key=lambda r: -r["pct"])[:limit]
    fallers = sorted((r for r in rows if r["pct"] < 0), key=lambda r: r["pct"])[:limit]
    return {
        "risers": risers,
        "fallers": fallers,
        # The two that actually demand a decision before the deadline.
        "your_fallers": [r for r in fallers if r["owned_by_you"]],
        "rising_not_owned": [r for r in risers if not r["owned_by_you"]],
    }


def market_scatter_points(ctx, squad_ids=(), min_minutes=60):
    """Every player with enough minutes to have a meaningful rate, as
    (price, xGI per 90) - the raw material for the value scatter.

    Read off bootstrap totals rather than per-player history so this stays a
    single request for the whole league of 600-odd players."""
    squad = set(squad_ids)
    pts = []
    for el in ctx.players.values():
        mins = el.get("minutes", 0)
        if mins < min_minutes:
            continue
        pos = ctx.pos(el)
        if pos == "GKP":
            continue  # a keeper's xGI is structurally ~0; it would just skew the axis
        xgi90 = per90(f(el.get("expected_goal_involvements")), mins)
        pts.append({
            "id": el["id"],
            "name": el["web_name"],
            "team": ctx.team_name(el["team"]),
            "pos": pos,
            "price": el["now_cost"] / 10.0,
            "xgi90": xgi90,
            "minutes": mins,
            "points": el["total_points"],
            "owned": f(el.get("selected_by_percent")),
            "mine": el["id"] in squad,
        })
    return pts


def squad_underlying(picks, ctx):
    """Season xGI and DefCon of a manager's starting XI, from bootstrap
    totals. Answers 'is this rival's score built on something repeatable, or
    on one lucky captain haul?' without 15 extra API calls per manager."""
    xi = [p for p in picks["picks"] if p["position"] <= 11]
    xgi = mins = defcon = 0.0
    for p in xi:
        el = ctx.players.get(p["element"])
        if not el:
            continue
        xgi += f(el["expected_goal_involvements"])
        mins += el["minutes"]
        defcon += el.get("defensive_contribution", 0)
    return {"xgi": xgi, "minutes": mins, "defcon": defcon}
