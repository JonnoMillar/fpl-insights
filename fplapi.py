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


def _parse_ffs_predicted(html):
    """{photo_id: FFS club name} for every predicted starter on the page.

    Each club's block is `<li class="team-news-item" ...><h2>Club Name</h2>
    ...<div class="scout-picks-pitch">...player photos...</div>...</li>` -
    split on those blocks first so every photo id is attributed to the club
    heading it actually appeared under, then pull ids out of each block."""
    out = {}
    blocks = re.split(r'(?=<li class="team-news-item")', html)
    for block in blocks:
        # The text before the first club is page chrome - its sidebar
        # widgets (watchlists, the app promo) carry player photos too, and
        # were read as starters for a club called "Download the FFScout app".
        if not block.startswith('<li class="team-news-item"'):
            continue
        heading = re.search(r'<h2[^>]*>\s*(.*?)\s*</h2>', block, re.S)
        if not heading:
            continue
        club = re.sub(r"\s+", " ", heading.group(1)).strip()
        if not club:
            continue
        for pid in re.findall(r"photos/players/110x140/(\d+)\.png", block):
            out[pid] = club
    return out


def ffs_predicted_photo_ids(ttl=DEFAULT_TTL):
    """{photo id: FFS club name} for every player Fantasy Football Scout
    expects to start the next round.

    FPL's own API says nothing about who will actually be on the pitch, which
    makes this the most valuable thing it does not have. FFS renders each
    predicted starter with a player photo whose filename is the same id FPL
    exposes in element['photo'], so the two join on a number rather than on a
    name. That join alone is not enough, though: a player who has transferred
    since FFS last refreshed the page still carries his old photo id, and
    would silently join under his former club. The caller must compare the
    returned club name against the player's *current* FPL club before trusting
    the match - see analysis.Ctx.is_predicted.

    Returns an empty dict on any failure. Callers must treat empty as
    "unknown", never as "nobody is starting"."""
    path = _cache_path(FFS_URL)
    try:
        if path.exists() and time.time() - path.stat().st_mtime < ttl:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(cached, dict):
                note("predicted line-ups", True, f"{len(cached)} cached starters")
                return cached
    except (ValueError, OSError):
        pass
    try:
        html = _fetch(FFS_URL)
    except FplError as e:
        print(f"[ffs] predicted line-ups unavailable: {e}")
        note("predicted line-ups", False, str(e)[:60])
        return {}
    mapping = _parse_ffs_predicted(html)
    if len(mapping) < MIN_EXPECTED_FFS:
        print(f"[ffs] only parsed {len(mapping)} players - markup may have changed, ignoring")
        note("predicted line-ups", False, f"only {len(mapping)} parsed, expected {MIN_EXPECTED_FFS}+")
        return {}
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(mapping), encoding="utf-8")
    note("predicted line-ups", True, f"{len(mapping)} starters")
    return mapping


# --- club badges ----------------------------------------------------------

# The 200px source. The 50px one was upscaled into every crest bigger than
# 25 CSS pixels on a 2x screen, which is why the fixture-run tiles looked soft.
BADGE_URL = "https://resources.premierleague.com/premierleague/badges/100/t{code}@x2.png"
BADGE_DIR = CACHE_DIR / "badges"


def badge_png(team_code):
    """Club badge bytes, cached on disk. Returns None if it cannot be had -
    the dashboard falls back to a lettered chip, so a missing badge costs
    nothing."""
    BADGE_DIR.mkdir(parents=True, exist_ok=True)
    path = BADGE_DIR / f"t{team_code}@x2.png"
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
# Current official FPL ElementPhoto source; uses element.code, without a p
# prefix. Do not fall back to the legacy path's potentially old-club photo.
PHOTO_URL = "https://resources.premierleague.com/premierleague25/photos/players/110x140/{pid}.png"
ASSET_DIR = CACHE_DIR / "assets"


def _asset(url, name, ttl=None):
    """Cache an image; refresh version-sensitive assets and back off failures."""
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / name
    retry = path.with_suffix(path.suffix + ".retry")
    cached = path.exists() and path.stat().st_size > 0
    if cached and (ttl is None or time.time() - path.stat().st_mtime < ttl):
        return path.read_bytes()
    if retry.exists() and time.time() - retry.stat().st_mtime < 86400:
        return path.read_bytes() if cached else None
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
                retry.unlink(missing_ok=True)
                return data
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                print(f"[asset] {name} unavailable: HTTP {e.code}; using fallback")
                path.unlink(missing_ok=True)
                retry.touch()
                return None
            last = e
        except Exception as e:
            last = e
        if attempt < 3:
            time.sleep(1 + 2 * attempt)
    print(f"[asset] {name} unavailable: {last!r}")
    retry.touch()
    return path.read_bytes() if cached else None


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
    installed, re-encodes to WebP, which keeps the transparency the page's
    cut-outs stand on (players sit on coloured cards, so a flattened
    background would show as a box) and is still smaller than a JPEG. Without
    WebP support it falls back to a JPEG on the mist ground; without Pillow
    the raw PNG is embedded, so the feature degrades rather than disappears."""
    if isinstance(photo_field, dict):
        pid = ("placeholder" if photo_field.get("has_temporary_code") else
               str(photo_field.get("code") or str(photo_field.get("photo", "")).split(".")[0]))
        club = str(photo_field.get("team_code", photo_field.get("team", "")))
    else:
        pid = str(photo_field).split(".")[0]
        club = ""
    if not pid:
        return None
    raw = _asset(PHOTO_URL.format(pid=pid), f"portrait25_{pid}_{club}.png", ttl=7 * 86400)
    if not raw and pid != "placeholder":
        raw = _asset(PHOTO_URL.format(pid="placeholder"), "portrait25_placeholder.png", ttl=7 * 86400)
    if not raw:
        return None
    try:
        import io

        from PIL import Image, features

        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        if features.check("webp"):
            for quality in (72, 60, 48):
                buf = io.BytesIO()
                img.save(buf, format="WEBP", quality=quality, method=6)
                if buf.tell() <= max_bytes:
                    break
            return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        flat = Image.new("RGB", img.size, (244, 242, 245))
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


def badge_data_uri(team_code, size=96):
    """Crest at `size` pixels, enough for twice its largest CSS size.

    Most crests sit at 24-48 CSS pixels and appear dozens of times on the
    page, so they get a small copy; only the big fixture-run tiles ask for
    the full 200. WebP keeps the transparency; without Pillow the source PNG
    is embedded as is."""
    data = badge_png(team_code)
    if not data:
        return None
    try:
        import io

        from PIL import Image, features

        if features.check("webp"):
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=90, method=6)
            return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        print(f"[badge] could not resize {team_code} ({e}); embedding raw")
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
