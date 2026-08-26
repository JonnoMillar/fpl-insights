#!/usr/bin/env python3
"""
Bookmaker odds, turned into expected goals and clean-sheet probability.

Pinnacle publish a guest API with no key and no scraping: full ladders of
match totals, Asian handicaps and moneylines for the Premier League. Pinnacle
is the right book to read for this - they run on low margins and high limits,
so their line is about as close to a genuine market consensus as a single
source gets.

The derivation is the standard one:

* The **total** line whose over and under prices sit closest to even money is
  the market's expected goals for the match.
* The **handicap** line closest to even is the market's supremacy - how many
  goals better the home side is thought to be.
* Those two solve for each side:  home = (total + supremacy) / 2,
  away = (total - supremacy) / 2.
* A clean sheet is the opponent failing to score, which under a Poisson model
  with mean m is simply exp(-m).

That last step is an assumption, not a quoted price - Poisson slightly
understates 0-0 draws in real football. It is a good approximation and it is
labelled as derived rather than quoted wherever it is shown.

Why bother when Fantasy Football Scout already publish clean-sheet odds: theirs
is a model, this is a market with money behind it. Where they disagree, that
disagreement is itself information.
"""

import gzip
import json
import math
import re
import time
import urllib.error
import urllib.request

import fplapi

BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
EPL_LEAGUE = 1980
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}

# Pinnacle spell clubs out; FPL abbreviate. Only the ones a normalised string
# comparison would not already get right.
ALIASES = {
    "manchestercity": "MCI",
    "manchesterunited": "MUN",
    "newcastleunited": "NEW",
    "tottenhamhotspur": "TOT",
    "wolverhamptonwanderers": "WOL",
    "brightonhovealbion": "BHA",
    "westhamunited": "WHU",
    "nottinghamforest": "NFO",
    "leedsunited": "LEE",
    "leicestercity": "LEI",
    "ipswichtown": "IPS",
    "afcbournemouth": "BOU",
    "coventrycity": "COV",
    "hullcity": "HUL",
    "sheffieldunited": "SHU",
    "crystalpalace": "CRY",
    "astonvilla": "AVL",
    "norwichcity": "NOR",
    "stokecity": "STK",
    "cardiffcity": "CAR",
}


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _get(url, ttl=fplapi.DEFAULT_TTL):
    path = fplapi._cache_path(url)
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
            fplapi.CACHE_DIR.mkdir(exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as e:
            last = e
            time.sleep(2 + 2 * attempt)
    raise fplapi.FplError(f"{url} failed: {last!r}")


def american_to_prob(price):
    """American odds to an implied probability, vig included."""
    if price is None:
        return None
    price = float(price)
    if price > 0:
        return 100.0 / (price + 100.0)
    return -price / (-price + 100.0)


def _fair_line(rows, key_a, key_b):
    """The line whose two sides are priced closest to even.

    A bookmaker quotes many lines; the one where both sides are near even money
    is the one they actually think is the middle of the distribution. Picking
    that beats averaging across a ladder that is deliberately skewed at the
    ends."""
    best, best_gap = None, 9e9
    for line, prices in rows.items():
        pa, pb = prices.get(key_a), prices.get(key_b)
        if pa is None or pb is None:
            continue
        qa, qb = american_to_prob(pa), american_to_prob(pb)
        if not qa or not qb:
            continue
        gap = abs(qa - qb)
        if gap < best_gap:
            best, best_gap = line, gap
    return best


def devig(*probs):
    """Strip the bookmaker's margin from a set of prices on one market.

    Quoted probabilities always sum to more than one - that overround is the
    margin. Dividing through by the sum gives the fair probabilities the book
    is implying, which is what a projection should use."""
    total = sum(p for p in probs if p)
    if not total:
        return list(probs)
    return [(p / total if p else 0.0) for p in probs]


def _specials(matchups, markets_by_id):
    """Team-level special markets, keyed by matchup.

    Pinnacle attach these as child matchups of the fixture. Two are worth far
    more than the derivation they replace:

    * "<Team> To Score?" - the No price is, after de-vigging, a *quoted*
      clean-sheet probability for the opponent. Better than assuming Poisson,
      which understates nil-nils.
    * "<Team> Goals" - an over/under ladder on one side's goals, which is that
      side's expected goals straight from the market rather than solved out of
      a total and a handicap.
    """
    out = {}
    for child in matchups:
        parent = child.get("parentId")
        if not parent:
            continue
        desc = (child.get("special") or {}).get("description") or ""
        if "1st Half" in desc:
            continue
        rows = markets_by_id.get(child["id"]) or []
        names = {p.get("id"): p.get("name")
                 for p in child.get("participants", []) if p.get("id") is not None}
        slot = out.setdefault(parent, {"to_score": {}, "team_goals": {}, "btts": None})

        if desc.endswith("To Score?") and not desc.startswith("Both"):
            team = desc[: -len(" To Score?")].strip()
            yes = no = None
            for row in rows:
                for price in row.get("prices", []):
                    label = names.get(price.get("participantId"))
                    if label == "Yes":
                        yes = american_to_prob(price.get("price"))
                    elif label == "No":
                        no = american_to_prob(price.get("price"))
            if yes and no:
                fair_yes, fair_no = devig(yes, no)
                slot["to_score"][team] = {"scores": fair_yes, "blank": fair_no}
        elif desc.startswith("Both Teams To Score"):
            yes = no = None
            for row in rows:
                for price in row.get("prices", []):
                    label = names.get(price.get("participantId"))
                    if label == "Yes":
                        yes = american_to_prob(price.get("price"))
                    elif label == "No":
                        no = american_to_prob(price.get("price"))
            if yes and no:
                slot["btts"] = devig(yes, no)[0]
        elif desc.endswith(" Goals"):
            team = desc[: -len(" Goals")].strip()
            ladder = {}
            for row in rows:
                for price in row.get("prices", []):
                    pts = price.get("points")
                    if pts is None:
                        continue
                    label = (names.get(price.get("participantId")) or
                             price.get("designation") or "")
                    ladder.setdefault(pts, {})[label.lower()] = price.get("price")
            line = _fair_line(ladder, "over", "under")
            if line is not None:
                slot["team_goals"][team] = line
    return out


def league_fixtures(ttl=fplapi.DEFAULT_TTL):
    """Upcoming Premier League fixtures with market expected goals.

    Returns [{home, away, kickoff, total, supremacy, home_xg, away_xg,
    home_cs, away_cs}] using FPL's three-letter club codes."""
    try:
        matchups = _get(f"{BASE}/leagues/{EPL_LEAGUE}/matchups", ttl=ttl)
        markets = _get(f"{BASE}/leagues/{EPL_LEAGUE}/markets/straight", ttl=ttl)
    except fplapi.FplError as e:
        print(f"[odds] unavailable: {e}")
        fplapi.note("bookmaker odds", False, str(e)[:60])
        return []

    markets_by_id = {}
    for row in markets:
        markets_by_id.setdefault(row.get("matchupId"), []).append(row)
    extras = _specials(matchups, markets_by_id)

    games = {}
    for m in matchups:
        if m.get("parentId"):
            continue
        parts = m.get("participants") or []
        if len(parts) != 2:
            continue
        names = [p.get("name") or "" for p in parts]
        if names[0] in ("Yes", "Over", "Under", "No"):
            continue
        games[m["id"]] = {
            "home": names[0], "away": names[1],
            "kickoff": (m.get("startTime") or "")[:16],
            "totals": {}, "spreads": {}, "moneyline": {},
            "extra": extras.get(m["id"], {}),
        }

    for row in markets:
        game = games.get(row.get("matchupId"))
        if not game or row.get("period") != 0:
            continue
        prices = row.get("prices") or []
        if row.get("type") == "total":
            for p in prices:
                pts = p.get("points")
                if pts is not None:
                    game["totals"].setdefault(pts, {})[p.get("designation")] = p.get("price")
        elif row.get("type") == "moneyline":
            for p in prices:
                d = p.get("designation")
                if d in ("home", "away", "draw"):
                    game["moneyline"][d] = p.get("price")
        elif row.get("type") == "spread":
            for p in prices:
                if p.get("designation") == "home" and p.get("points") is not None:
                    game["spreads"].setdefault(abs(p["points"]), {})["home"] = p.get("price")
                    game["spreads"][abs(p["points"])]["sign"] = (
                        1 if p["points"] < 0 else -1
                    )
                elif p.get("designation") == "away" and p.get("points") is not None:
                    game["spreads"].setdefault(abs(p["points"]), {})["away"] = p.get("price")

    out = []
    for game in games.values():
        total = _fair_line(game["totals"], "over", "under")
        spread = _fair_line(game["spreads"], "home", "away")
        if total is None:
            continue
        sign = game["spreads"].get(spread, {}).get("sign", 1) if spread else 1
        supremacy = (spread or 0.0) * sign

        extra = game.get("extra") or {}
        tg = extra.get("team_goals") or {}
        # A quoted team-goals line beats solving one out of the total and the
        # handicap, so prefer it and fall back only when it is absent.
        home_xg = tg.get(game["home"], max(0.15, (total + supremacy) / 2.0))
        away_xg = tg.get(game["away"], max(0.15, (total - supremacy) / 2.0))

        ts = extra.get("to_score") or {}
        home_cs = ts.get(game["away"], {}).get("blank")
        away_cs = ts.get(game["home"], {}).get("blank")
        cs_source = "quoted" if (home_cs is not None and away_cs is not None) else "poisson"
        if home_cs is None:
            home_cs = math.exp(-away_xg)
        if away_cs is None:
            away_cs = math.exp(-home_xg)

        ml = game.get("moneyline") or {}
        probs = devig(*[american_to_prob(ml.get(k)) for k in ("home", "draw", "away")])
        win = {"home": probs[0], "draw": probs[1], "away": probs[2]} if any(probs) else {}

        out.append({
            "home": _club(game["home"]), "away": _club(game["away"]),
            "home_name": game["home"], "away_name": game["away"],
            "kickoff": game["kickoff"],
            "total": total, "supremacy": supremacy,
            "home_xg": round(home_xg, 2), "away_xg": round(away_xg, 2),
            "home_cs": round(100 * home_cs, 1), "away_cs": round(100 * away_cs, 1),
            "cs_source": cs_source,
            "btts": round(100 * extra["btts"], 1) if extra.get("btts") else None,
            "win": {k: round(100 * v, 1) for k, v in win.items()} if win else None,
        })
    quoted = sum(1 for f_ in out if f_["cs_source"] == "quoted")
    fplapi.note("bookmaker odds", bool(out),
                f"{len(out)} fixtures, {quoted} with quoted clean sheets")
    return out


_CLUB_LOOKUP = {}


def build_club_lookup(ctx):
    """Map Pinnacle club names onto FPL's three-letter codes."""
    _CLUB_LOOKUP.clear()
    for team in ctx.teams.values():
        _CLUB_LOOKUP[_norm(team["name"])] = team["short_name"]
        _CLUB_LOOKUP[_norm(team["short_name"])] = team["short_name"]
    _CLUB_LOOKUP.update(ALIASES)


def _club(name):
    key = _norm(name)
    if key in _CLUB_LOOKUP:
        return _CLUB_LOOKUP[key]
    # Fall back to the longest known name that is a prefix of this one, which
    # catches "Brighton" against "Brighton & Hove Albion" and similar.
    for known in sorted(_CLUB_LOOKUP, key=len, reverse=True):
        if known and (key.startswith(known) or known.startswith(key)):
            return _CLUB_LOOKUP[known]
    return name[:3].upper()


def by_club(ctx, ttl=fplapi.DEFAULT_TTL):
    """{club_code: {"xg", "cs", "opp", "home", "kickoff"}} for the next match."""
    build_club_lookup(ctx)
    out = {}
    for fx in sorted(league_fixtures(ttl=ttl), key=lambda f: f["kickoff"]):
        for side, other, xg, cs, home in (
            ("home", "away", fx["home_xg"], fx["home_cs"], True),
            ("away", "home", fx["away_xg"], fx["away_cs"], False),
        ):
            club = fx[side]
            if club in out:
                continue  # keep only the soonest fixture per club
            out[club] = {
                "xg": xg, "cs": cs, "opp": fx[other],
                "home": home, "kickoff": fx["kickoff"],
                "total": fx["total"], "supremacy": round(fx["supremacy"], 2),
            }
    return out
