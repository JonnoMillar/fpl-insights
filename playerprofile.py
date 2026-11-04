"""The player profile: one view for every player face on the page.

Every portrait, shirt card and player name carries `data-player="<id>"`, and
profile.js opens the same dialog from any of them. So every player who
appears anywhere needs a record, not just the owned fifteen. `build` makes a
compact record for everyone; `island` keeps only the ids the rendered page
actually hooks, plus the Scout pools (whose rows scout.js draws in the
browser), and fails the build if a face is left unhooked or a hook has no
record.
"""

import re
from html.parser import HTMLParser

import analysis
import pulse
import scout
import transfers
from cards_common import script_json

# Five season figures per position, each read against that position's own
# pool: (row field, label, number format, lower is better).
TILES = {
    "GKP": [("saves90", "Saves per 90", "2", False), ("xgc90", "xGC per 90", "2", True),
            ("csRate", "Clean-sheet rate", "pct", False), ("startRate", "Start rate", "pct", False),
            ("bonus90", "Bonus per 90", "2", False)],
    "DEF": [("defconHitRate", "DefCon hit rate", "pct", False), ("xgi90", "xGI per 90", "2", False),
            ("xgc90", "xGC per 90", "2", True), ("startRate", "Start rate", "pct", False),
            ("bonus90", "Bonus per 90", "2", False)],
    "MID": [("xg90", "xG per 90", "2", False), ("xa90", "xA per 90", "2", False),
            ("defcon90", "DefCon per 90", "1", False), ("startRate", "Start rate", "pct", False),
            ("bonus90", "Bonus per 90", "2", False)],
    "FWD": [("xg90", "xG per 90", "2", False), ("xa90", "xA per 90", "2", False),
            ("startRate", "Start rate", "pct", False), ("minutesPerStart", "Minutes per start", "0", False),
            ("bonus90", "Bonus per 90", "2", False)],
}

# What the match strip marks under each bar: DefCon hit or miss, goals and
# assists. A forward earns nothing for a clean sheet, so no outline there.
STRIP = {"GKP": ([], True), "DEF": (["defcon"], True),
         "MID": (["ga", "defcon"], True), "FWD": (["ga"], False)}

FIXTURE_WEEKS = 6
STATUS = {"unplayed": 0, "subbedOn": 1, "started": 2}
CARD = {"none": 0, "yellow": 1, "red": 2}
EP_PARTS = ("goals", "assists", "defence", "saves", "appearance", "defcon", "bonus", "gc", "cards")


def _r(v, n=2):
    return round(float(v or 0), n)


def club_fixtures(ctx, proj, start_gw, weeks=FIXTURE_WEEKS):
    """{team id: next `weeks` cells}, each checked against FPL's own fixture
    list: a week FPL has no fixture in is a blank, one with two fixtures or a
    projection for a different opponent or venue is unavailable (doubles are
    not modelled), and only a single agreeing fixture gets ratings."""
    short_to_id = {t["short_name"]: tid for tid, t in ctx.teams.items()}
    out = {}
    for tid, t in ctx.teams.items():
        cells = []
        for row in scout.fixture_rows(t["short_name"], proj, start_gw, weeks):
            actual = [fx for fx in ctx.fixtures if fx.get("event") == row["gw"]
                      and tid in (fx["team_h"], fx["team_a"])]
            if not actual:
                cells.append({"gw": row["gw"], "blank": 1})
                continue
            fx = actual[0]
            home = fx["team_h"] == tid
            opp = fx["team_a"] if home else fx["team_h"]
            if (len(actual) != 1 or row.get("blank") or short_to_id.get(row["opp"]) != opp
                    or row["home"] != home):
                cells.append({"gw": row["gw"], "na": 1})
                continue
            cells.append({"gw": row["gw"], "opp": opp, "h": int(home),
                          "cs": row["cleanSheetRating"], "at": row["attackRating"]})
        out[tid] = cells
    return out


def _matches(ms):
    """Season_live rows as short arrays: [gw, opp, home, status] for a match
    he missed, then minutes, points, goals, assists, DefCon, DefCon hit,
    clean sheet, card, xG, xA and BPS for one he played."""
    out = []
    for m in ms:
        row = [m["gw"], m["opp"] or "", None if m["home"] is None else int(m["home"]),
               STATUS[m["status"]]]
        if m["status"] != "unplayed":
            row += [m["minutes"], m["points"], m["goals"], m["assists"], m["defcon"],
                    None if m["defconHit"] is None else int(m["defconHit"]),
                    int(m["cleanSheet"]), CARD[m["card"]], m["xg"], m["xa"], m["bps"]]
        out.append(row)
    return out


def _xp(score, model):
    """One week's expected points with its parts, from either scorer."""
    if not score:
        return None
    return {"t": _r(score["total"]), "o": score.get("opponent"), "h": int(bool(score.get("home"))),
            "cs": round(score.get("cs") or 0), "txg": _r(score.get("team_xg")) or None,
            "parts": [_r(score.get(k)) for k in EP_PARTS], "m": model}


def build(ctx, live, proj, next_gw, market, baselines, priors, badges, eps=None,
          reports=None, pools=None):
    """Records for every player plus the shared tables the view reads.

    `eps` ({id: analysis.expected_points}) are the owned squad's and the
    previewed signings' match-history scores, the same figures the pitch
    shows; everyone else gets transfers.candidate_score, the figure the Scout
    table shows. `reports` supply last season, which only match history has.
    `pools` are the Scout pools, whose ids are always kept. `badges` are the
    small crests, shipped once each for the fixture and opponent cells."""
    eps, reports = eps or {}, reports or {}
    rows = {}
    for pos in TILES:
        for r in scout.raw_rows(ctx, pos, live, min_minutes=0):
            el = ctx.players[r["id"]]
            mins = r["minutes"]
            r["saves90"] = round(analysis.per90(el.get("saves", 0), mins), 2)
            r["csRate"] = round(el.get("clean_sheets", 0) / r["starts"], 3) if r["starts"] else 0.0
            rows[r["id"]] = r

    # Position averages and percentiles over everyone with enough minutes
    # for a rate to mean anything - the same floor the Scout leaders use.
    tiles_meta, pct = {}, {}
    for pos, tiles in TILES.items():
        pool = [r for r in rows.values() if ctx.pos(ctx.players[r["id"]]) == pos
                and r["minutes"] >= scout.RATE_MIN_MINUTES]
        meta = []
        for field, label, fmt, invert in tiles:
            vals = [r[field] for r in pool]
            meta.append([label, fmt, round(sum(vals) / len(vals), 3) if vals else None, field])
            for r in pool:
                p = scout.percentile_rank(vals, r[field])
                pct.setdefault(r["id"], {})[field] = round(100 - p if invert else p)
        tiles_meta[pos] = meta

    # Archetypes against the Scout explorer's default pool, as its table
    # shows them on first load.
    archetypes = {}
    for pos, data in (pools or {}).items():
        cfg = scout.POSITIONS[pos]
        shown = [dict(r) for r in scout._apply_filters(data["rows"], scout.DEFAULT_FILTERS)]
        for r in scout.apply_derivations(shown, cfg.archetypes):
            if r["archetypes"]:
                archetypes[r["id"]] = [cfg.archetype_labels[a] for a in r["archetypes"]]

    players = {}
    for pid, r in rows.items():
        el = ctx.players[pid]
        pos = ctx.pos(el)
        rep = reports.get(pid) or analysis.PlayerReport(el, pos, ctx.team_name(el["team"]), [], [])
        flag, news = rep.availability
        if pid in eps:
            xp = _xp(eps[pid], "history")
        elif next_gw and next_gw <= 38:
            xp = _xp(transfers.candidate_score(el, ctx, proj, next_gw, market, baselines, priors),
                     "season")
        else:
            xp = None
        last = rep.last_season() if pid in reports else None
        p = pct.get(pid, {})
        players[pid] = {
            "n": el["web_name"], "t": el["team"], "p": pos, "cd": el.get("code"),
            "c": el["now_cost"] / 10, "pc": round(el.get("cost_change_start", 0) / 10, 1),
            "o": r["ownership"], "tr": r["priceChangeMomentum"],
            "f": flag or "", "nw": news, "pr": ctx.is_predicted(el),
            "sp": [[k, el.get(f)] for k, f in (("penalties", "penalties_order"),
                                               ("free-kicks", "direct_freekicks_order"),
                                               ("corners", "corners_and_indirect_freekicks_order"))
                   if el.get(f)],
            "ar": archetypes.get(pid, []),
            "v": [r[field] for field, *_ in TILES[pos]],
            "q": [p.get(field) for field, *_ in TILES[pos]],
            "x": xp,
            "m": _matches(r["matches"]),
            "e": {"pts": el.get("total_points", 0), "b": el.get("bonus", 0), "min": r["minutes"],
                  "st": r["starts"], "tm": r["teamMatches"], "g": r["goals"], "a": r["assists"],
                  "xg": _r(el.get("expected_goals")), "xa": _r(el.get("expected_assists")),
                  "xgi": _r(el.get("expected_goal_involvements")), "xgi90": r["xgi90"],
                  "dc": el.get("defensive_contribution", 0), "dc90": r["defcon90"],
                  "dch": r["defconHits"], "dcn": r["defconHitN"],
                  "cs": el.get("clean_sheets", 0), "sv": el.get("saves", 0),
                  "dct": analysis.DEFCON_THRESHOLD.get(pos) or 0},
            "op": {k: v for k, v in (el.get("_pulse") or {}).items() if v},
            "ls": ({"pts": last["points"], "min": last["minutes"], "g": last["goals"],
                    "a": last["assists"], "xgi": _r(last["xgi"], 1)} if last else None),
        }
    return {
        "players": players,
        "always": sorted({r["id"] for data in (pools or {}).values() for r in data["rows"]}),
        "teams": {tid: [t["short_name"], badges.get(tid)] for tid, t in ctx.teams.items()},
        "tiles": tiles_meta,
        "strip": STRIP,
        "fixtures": club_fixtures(ctx, proj, next_gw) if next_gw and next_gw <= 38 else {},
        "opta": {k: v[0] for k, v in pulse.STATS.items()},
    }


HOOK = re.compile(r'data-player="(\d+)"')
PORTRAIT_CLASSES = {"cut", "face", "df-photo", "rv-photo"}
# Faces inside a control that only navigates to a view where the same player's
# hooked portrait stands: a week tile shows its stage, a deck index entry its
# card. A button cannot hold a second button.
NAV_CONTROLS = {"wk", "deck-idx"}


class _Faces(HTMLParser):
    """Every portrait image on a page, with the player hook it sits under.
    A blank placeholder is not a portrait: it shows no one."""
    VOID = {"img", "br", "hr", "input", "meta", "link", "source", "wbr", "area", "col"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.faces = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        hook = a.get("data-player")
        if tag == "img" and classes & PORTRAIT_CLASSES:
            owner = hook or next((h for _t, h, _n in reversed(self.stack) if h), None)
            nav = any(n for _t, _h, n in self.stack)
            self.faces.append((tag, " ".join(sorted(classes)), owner, nav))
        if tag not in self.VOID:
            self.stack.append((tag, hook, bool(classes & NAV_CONTROLS)))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def unhooked(html):
    """Portraits that open nothing: (tag, classes) for each."""
    p = _Faces()
    p.feed(html)
    return [(tag, cls) for tag, cls, owner, nav in p.faces if not owner and not nav]


def island(html, profiles):
    """The profile data the page needs, as its script element. Raises if a
    portrait opens nothing or a hook has no record, so a broken page is
    never published."""
    if not profiles:
        return ""
    missing = unhooked(html)
    if missing:
        raise ValueError(f"portraits without a player hook: {missing[:5]}")
    ids = {int(i) for i in HOOK.findall(html)} | set(profiles["always"])
    absent = sorted(i for i in ids if i not in profiles["players"])
    if absent:
        raise ValueError(f"player hooks without a profile record: {absent[:10]}")
    data = {k: v for k, v in profiles.items() if k not in ("players", "always")}
    data["players"] = {i: profiles["players"][i] for i in sorted(ids)}
    return f'<script type="application/json" id="profile-data">{script_json(data)}</script>'
