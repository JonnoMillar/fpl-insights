#!/usr/bin/env python3
"""
Fantasy Football Scout's fixture projections - clean sheet odds and expected
goals for every club, every gameweek.

Their projected-points *table* is members-only: for an anonymous visitor the
player rows render with names and a direction arrow but the numbers are
stripped. The page does, however, embed a small JSON blob that drives its
fixture ticker, and that blob is complete and public:

    {"ARS|1": {"cs": 57.2, "g": 2.449, "opp": "COV", "ven": "H"}, ...}

Keyed by club and gameweek, all 20 clubs across all 38 weeks:

    cs   probability of a clean sheet, as a percentage
    g    expected goals scored
    opp  opponent's three-letter code
    ven  H or A

This is a real model rather than FPL's own 1-to-5 difficulty rating, and it
runs the full season instead of the three fixtures FPL's site shows. Being a
scrape of a page's internals it is inherently fragile, so every consumer must
cope with it being empty.
"""

import json
import re

import fplapi

URL = "https://www.fantasyfootballscout.co.uk/fpl/projected-points"

# 20 clubs x 38 weeks. Well short of that means the page changed shape.
MIN_EXPECTED = 400


def projections(ttl=fplapi.DEFAULT_TTL):
    """{(club_code, gameweek): {"cs", "g", "opp", "ven"}}. Empty on failure."""
    cache = fplapi._cache_path(URL + "#projections")
    try:
        import time

        if cache.exists() and time.time() - cache.stat().st_mtime < ttl:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            return {(k.split("|")[0], int(k.split("|")[1])): v for k, v in raw.items()}
    except (ValueError, OSError, KeyError):
        pass

    try:
        html = fplapi._fetch(URL)
    except fplapi.FplError as e:
        print(f"[ffs] projections unavailable: {e}")
        fplapi.note("fixture projections", False, str(e)[:60])
        return {}

    match = re.search(
        r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S
    )
    if not match:
        print("[ffs] projections blob not found - page markup changed")
        fplapi.note("fixture projections", False, "blob missing, markup changed")
        return {}
    try:
        raw = json.loads(match.group(1))
    except ValueError as e:
        print(f"[ffs] projections blob unreadable: {e}")
        return {}
    if len(raw) < MIN_EXPECTED:
        print(f"[ffs] only {len(raw)} projection entries - ignoring")
        fplapi.note("fixture projections", False, f"only {len(raw)} entries")
        return {}

    fplapi.CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(raw), encoding="utf-8")
    out = {}
    for key, value in raw.items():
        club, _, gw = key.partition("|")
        try:
            out[(club, int(gw))] = value
        except ValueError:
            continue
    fplapi.note("fixture projections", bool(out), f"{len(out)} club-gameweeks")
    return out


def ticker(proj, club, start_gw, count=6):
    """The next `count` fixtures for one club as a list of dicts.

    Clubs are keyed by their three-letter code, which matches FPL's
    `short_name` - the one place these two sources already agree."""
    rows = []
    gw = start_gw
    while len(rows) < count and gw <= 38:
        item = proj.get((club, gw))
        if item:
            rows.append({
                "gw": gw,
                "opp": item.get("opp", "?"),
                "home": (item.get("ven") or "H").upper() == "H",
                "cs": float(item.get("cs") or 0),
                "xg": float(item.get("g") or 0),
            })
        gw += 1
    return rows


def summary(proj, club, start_gw, count=6):
    """Mean clean-sheet odds and expected goals over a run of fixtures -
    the two numbers that decide whether a defence or an attack is worth
    buying into for the next month."""
    rows = ticker(proj, club, start_gw, count)
    if not rows:
        return None
    return {
        "count": len(rows),
        "cs": sum(r["cs"] for r in rows) / len(rows),
        "xg": sum(r["xg"] for r in rows) / len(rows),
        "rows": rows,
    }
