#!/usr/bin/env python3
"""
The Premier League's own stats API - the Opta numbers FPL does not expose.

premierleague.com runs on footballapi.pulselive.com, which is open and needs
no key. It carries the full Opta stat set, of which FPL's API surfaces only a
handful. Big chances created, shots on target, successful dribbles and touches
are all there and none of them appear anywhere in FPL's own product.

The join is exact rather than fuzzy. Pulselive returns `altIds: {"opta":
"p223094"}` on every player and FPL carries the identical string in
`element["opta_code"]`, so the two link on an id - no name matching, no
accents, no initials, nothing to get wrong.

Two quirks worth knowing:

* Ids come back as floats ("128932.0"), so anything used in a URL must be cast
  to int first or the request 404s.
* The ranked endpoints only include opta ids when asked with `altIds=true`.
"""

import gzip
import json
import time
import urllib.error
import urllib.request

import fplapi

BASE = "https://footballapi.pulselive.com/football"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": "https://www.premierleague.com",
    "Referer": "https://www.premierleague.com/",
}

# Stat keys are Opta's own names. Each maps to a label and a short note saying
# why it earns its place - every one of these is absent from FPL's API.
STATS = {
    "big_chance_created": ("Big chances created", "Passes that set up a clear opening."),
    "total_att_assist": ("Chances created", "Every pass leading to a shot."),
    "total_scoring_att": ("Shots", "Total attempts at goal."),
    "ontarget_scoring_att": ("Shots on target", "Attempts forcing a save or scoring."),
    "big_chance_missed": ("Big chances missed", "Clear openings not converted."),
    "won_contest": ("Successful dribbles", "Take-ons completed."),
    "touches": ("Touches", "Overall involvement in play."),
}

COMP = 1  # Premier League


def _get(url, tries=4, timeout=45):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                raise fplapi.FplError(f"HTTP {e.code} for {url}") from e
            last = e
        except Exception as e:
            last = e
        if attempt < tries - 1:
            time.sleep(2 + 2 * attempt)
    raise fplapi.FplError(f"{url} failed after {tries} tries: {last!r}")


def _cached(url, ttl):
    path = fplapi._cache_path(url)
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    data = _get(url)
    fplapi.CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def current_comp_season(ttl=fplapi.DEFAULT_TTL):
    """Pulselive's id for the season now in progress, read off a real fixture
    rather than hardcoded so it survives the summer."""
    d = _cached(
        f"{BASE}/fixtures?comps={COMP}&pageSize=1&sort=desc&statuses=C", ttl
    )
    content = d.get("content") or []
    if not content:
        raise fplapi.FplError("no completed fixtures - cannot resolve comp season")
    return int(content[0]["gameweek"]["compSeason"]["id"])


def ranked(stat, comp_season, pages=4, page_size=100, ttl=fplapi.DEFAULT_TTL):
    """{opta_code: value} for one stat across the league.

    Leaderboard endpoints are used rather than per-player lookups because one
    request covers a hundred players; pulling this player by player would be
    600 requests against somebody else's free API."""
    out = {}
    for page in range(pages):
        url = (
            f"{BASE}/stats/ranked/players/{stat}?compSeasons={comp_season}"
            f"&comps={COMP}&pageSize={page_size}&page={page}&altIds=true"
        )
        try:
            d = _cached(url, ttl)
        except fplapi.FplError as e:
            print(f"[pulse] {stat} page {page}: {e}")
            break
        stats = d.get("stats") or {}
        rows = stats.get("content") or []
        for row in rows:
            opta = ((row.get("owner") or {}).get("altIds") or {}).get("opta")
            if opta:
                out[opta] = row.get("value")
        info = stats.get("pageInfo") or {}
        if page + 1 >= (info.get("numPages") or 0):
            break
    return out


def load(ttl=fplapi.DEFAULT_TTL, stats=None):
    """{opta_code: {stat_key: value}} for every stat in STATS.

    Returns an empty dict if Pulselive cannot be reached - the dashboard then
    simply omits these columns rather than showing zeroes that look like real
    measurements."""
    keys = stats or list(STATS)
    try:
        season = current_comp_season(ttl=ttl)
    except fplapi.FplError as e:
        print(f"[pulse] unavailable: {e}")
        return {}
    merged = {}
    for key in keys:
        for opta, value in ranked(key, season, ttl=ttl).items():
            merged.setdefault(opta, {})[key] = value
    return merged


def attach(ctx, ttl=fplapi.DEFAULT_TTL):
    """Hang Pulselive stats off the FPL player objects, keyed by opta_code.

    Stored on the element itself so every existing consumer of ctx.players
    picks it up without threading another argument through."""
    data = load(ttl=ttl)
    if not data:
        fplapi.note("Opta stats", False, "Premier League API returned nothing")
        return 0
    hits = 0
    for el in ctx.players.values():
        stats = data.get(el.get("opta_code"))
        if stats:
            el["_pulse"] = stats
            hits += 1
    fplapi.note("Opta stats", hits > 0, f"{hits} players matched")
    return hits
