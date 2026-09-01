#!/usr/bin/env python3
"""
Thin, dependency-free client for the public FPL API.

Two things here are not incidental:

1. `curl` cannot reach fantasy.premierleague.com from this machine - the TLS
   handshake fails (curl exit 35) whether sandboxed or not, while Python's
   urllib succeeds against the same host. So everything goes through urllib.
2. Requests to GitHub and other hosts intermittently die with WinError 10054
   ("connection forcibly closed") on this network. Every fetch retries with
   backoff rather than letting one reset kill a run.

Responses are cached on disk. The FPL API is free and unauthenticated, which
is exactly why it deserves to be treated politely: a full league report would
otherwise re-download a 3 MB bootstrap for every command.
"""

import re
import gzip
import base64
import json
import time
import hashlib
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://fantasy.premierleague.com/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

CACHE_DIR = Path(__file__).with_name(".cache")

# Live data (scores, prices, ownership) moves during a gameweek; per-player
# match history only changes when a match finishes. One short TTL for
# everything is simpler and still cheap - a full refresh is ~20 requests.
DEFAULT_TTL = 900


class FplError(RuntimeError):
    pass


def _cache_path(url):
    return CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".json")


def _fetch(url, tries=4, timeout=60):
    """GET with backoff. Returns decoded text."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8")
        except urllib.error.HTTPError as e:
            # A 404 is an answer, not a glitch - retrying will not change it.
            if e.code in (404, 403):
                raise FplError(f"HTTP {e.code} for {url}") from e
            last = e
        except Exception as e:  # URLError, socket timeout, connection reset
            last = e
        if attempt < tries - 1:
            time.sleep(2 + 3 * attempt)
    raise FplError(f"{url} failed after {tries} tries: {last!r}")


def get_json(url, ttl=DEFAULT_TTL, use_cache=True):
    path = _cache_path(url)
    if use_cache and path.exists() and time.time() - path.stat().st_mtime < ttl:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass  # corrupt cache entry - refetch rather than crash
    text = _fetch(url)
    data = json.loads(text)
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return data


# --- endpoints -------------------------------------------------------------

def bootstrap(**kw):
    """Every player, team, gameweek and chip. The one call most things need."""
    return get_json(f"{BASE}/bootstrap-static/", **kw)


def element_summary(player_id, **kw):
    """Per-match history for one player: history[] is one row per fixture,
    carrying expected_goals / expected_assists / expected_goal_involvements.
    history_past[] is season totals only - the API keeps no per-match history
    for previous seasons."""
    return get_json(f"{BASE}/element-summary/{player_id}/", **kw)


def fixtures(event=None, **kw):
    url = f"{BASE}/fixtures/" + (f"?event={event}" if event else "")
    return get_json(url, **kw)


def league_standings(league_id, page=1, **kw):
    return get_json(
        f"{BASE}/leagues-classic/{league_id}/standings/?page_standings={page}", **kw
    )


def entry_picks(entry_id, event, **kw):
    """A manager's 15 for a gameweek. Public once that gameweek's deadline
    has passed - no login needed to read rivals."""
    return get_json(f"{BASE}/entry/{entry_id}/event/{event}/picks/", **kw)


def event_live(event, **kw):
    """Every player's points for one past gameweek, in a single request -
    {"elements": [{"id", "stats": {"total_points", "minutes", ...}}, ...]}.
    The cheap way to price a specific past gameweek across many players:
    one call here beats one element-summary call per player."""
    return get_json(f"{BASE}/event/{event}/live/", **kw)


def entry(entry_id, **kw):
    return get_json(f"{BASE}/entry/{entry_id}/", **kw)


def entry_history(entry_id, **kw):
    """Per-gameweek points, rank, transfers and chips for one manager."""
    return get_json(f"{BASE}/entry/{entry_id}/history/", **kw)


# --- housekeeping ---------------------------------------------------------

# Every source records whether it produced usable data on this run. The
# scrapes all fail soft - an empty set rather than an exception - which is the
# right behaviour at the point of failure but means a broken source would
# otherwise just quietly stop appearing on the page.
HEALTH = {}


def note(source, ok, detail=""):
    HEALTH[source] = {"ok": bool(ok), "detail": detail}
    return ok


def health_report():
    """One line per source: what worked, what did not."""
    if not HEALTH:
        return "no sources recorded"
    width = max(len(k) for k in HEALTH)
    lines = []
    for name, row in HEALTH.items():
        mark = "ok  " if row["ok"] else "FAIL"
        lines.append(f"  {mark}  {name.ljust(width)}  {row['detail']}")
    return "\n".join(lines)


def prune_cache(max_age_days=45):
    """Drop cache entries nobody will ask for again.

    Each gameweek adds roughly a hundred new URLs - one squad per elite
    manager, per gameweek - and those are never requested again once the week
    has passed. Left alone the directory grows all season."""
    if not CACHE_DIR.exists():
        return 0
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


# --- predicted line-ups ---------------------------------------------------

FFS_URL = "https://www.fantasyfootballscout.co.uk/team-news"

# FFS shows 20 teams x 11. Parsing far fewer means their markup moved, and
# every player would then look benched - a page full of false alarms. Below
# this we report nothing rather than something wrong.
MIN_EXPECTED_FFS = 150


def ffs_predicted_photo_ids(ttl=DEFAULT_TTL):
    """Premier League photo ids of every player Fantasy Football Scout expects
    to start the next round.

    FPL's own API says nothing about who will actually be on the pitch, which
    makes this the most valuable thing it does not have. FFS renders each
    predicted starter with a player photo whose filename is the same id FPL
    exposes in element['photo'], so the two join on a number rather than on a
    name - accents, initials and transfers cannot produce a bad match.

    Returns an empty set on any failure. Callers must treat empty as "unknown",
    never as "nobody is starting"."""
    path = _cache_path(FFS_URL)
    try:
        if path.exists() and time.time() - path.stat().st_mtime < ttl:
            return set(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        pass
    try:
        html = _fetch(FFS_URL)
    except FplError as e:
        print(f"[ffs] predicted line-ups unavailable: {e}")
        note("predicted line-ups", False, str(e)[:60])
        return set()
    ids = set(re.findall(r"photos/players/110x140/(\d+)\.png", html))
    if len(ids) < MIN_EXPECTED_FFS:
        print(f"[ffs] only parsed {len(ids)} players - markup may have changed, ignoring")
        note("predicted line-ups", False, f"only {len(ids)} parsed, expected {MIN_EXPECTED_FFS}+")
        return set()
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(sorted(ids)), encoding="utf-8")
    note("predicted line-ups", True, f"{len(ids)} starters")
    return ids


# --- club badges ----------------------------------------------------------

BADGE_URL = "https://resources.premierleague.com/premierleague/badges/50/t{code}.png"
BADGE_DIR = CACHE_DIR / "badges"


def badge_png(team_code):
    """Club badge bytes, cached on disk. Returns None if it cannot be had -
    the dashboard falls back to a lettered chip, so a missing badge costs
    nothing."""
    BADGE_DIR.mkdir(parents=True, exist_ok=True)
    path = BADGE_DIR / f"t{team_code}.png"
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    url = BADGE_URL.format(code=team_code)
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Referer": "https://fantasy.premierleague.com/"}
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if data:
                path.write_bytes(data)
                return data
        except Exception as e:
            last = e
        if attempt < 3:
            time.sleep(1 + 2 * attempt)
    print(f"[badge] {team_code} unavailable: {last!r}")
    return None


SHIRT_URL = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_{code}{gk}-66.png"
PHOTO_URL = "https://resources.premierleague.com/premierleague/photos/players/110x140/p{pid}.png"
ASSET_DIR = CACHE_DIR / "assets"


def _asset(url, name):
    """Fetch an image once and keep it on disk. None if it cannot be had."""
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / name
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA,
                              "Referer": "https://fantasy.premierleague.com/"}
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if data:
                path.write_bytes(data)
                return data
        except Exception as e:
            last = e
        if attempt < 3:
            time.sleep(1 + 2 * attempt)
    print(f"[asset] {name} unavailable: {last!r}")
    return None


def shirt_data_uri(team_code, keeper=False):
    """Club shirt, the same asset FPL puts on its own pitch. ~4 KB each."""
    gk = "_1" if keeper else ""
    data = _asset(SHIRT_URL.format(code=team_code, gk=gk), f"shirt_{team_code}{gk}.png")
    if not data:
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def photo_data_uri(photo_field, max_bytes=14000):
    """Player portrait, squeezed down before embedding.

    The Premier League serve these as 96 KB PNGs, which across a squad would
    add well over a megabyte to a page you open on a phone. Pillow, if it is
    installed, re-encodes to a small JPEG on a white ground - a portrait does
    not need alpha. Without Pillow the raw PNG is embedded instead, so the
    feature degrades rather than disappears."""
    pid = str(photo_field).split(".")[0]
    if not pid:
        return None
    raw = _asset(PHOTO_URL.format(pid=pid), f"photo_{pid}.png")
    if not raw:
        return None
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        flat = Image.new("RGB", img.size, (245, 242, 245))
        flat.paste(img, mask=img.split()[-1])
        for quality in (78, 66, 55, 45):
            buf = io.BytesIO()
            flat.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_bytes:
                break
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        print(f"[asset] could not compress photo {pid} ({e}); embedding raw")
        return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def badge_data_uri(team_code):
    data = badge_png(team_code)
    if not data:
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
